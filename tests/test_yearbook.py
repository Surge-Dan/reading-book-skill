import json
import os
import sys
import tempfile
import unittest
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "reading-yearbook-skill"
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from yearbook_core import (  # noqa: E402
    build_gateway_payload,
    build_profiles,
    classify_evidence,
    normalize_yearbook,
    score_books,
)
from run_yearbook import finalize_yearbook, generate_preview  # noqa: E402
from build_deep_distill import distill_text, load_legal_text  # noqa: E402
from export_cards import find_browser_executable  # noqa: E402
from collect_weread_data import collection_status, select_candidate_books  # noqa: E402
from validate_yearbook import validate_output  # noqa: E402


class CoreRulesTests(unittest.TestCase):
    def test_gateway_payload_keeps_business_fields_at_top_level(self):
        payload = build_gateway_payload("/user/notebooks", {"count": 20, "lastSort": 9})
        self.assertEqual(payload["api_name"], "/user/notebooks")
        self.assertEqual(payload["skill_version"], "1.0.4")
        self.assertEqual(payload["count"], 20)
        self.assertNotIn("params", payload)

    def test_evidence_levels_do_not_overstate_thin_activity(self):
        self.assertEqual(classify_evidence(0, 0, 0, False), "E0")
        self.assertEqual(classify_evidence(20, 1, 0, False), "E1")
        self.assertEqual(classify_evidence(85, 3, 1, False), "E2")
        self.assertEqual(classify_evidence(1, 0, 0, True), "E3")

    def test_normalization_filters_activity_to_requested_year(self):
        raw = {
            "source_mode": "sample",
            "shelf": {
                "books": [
                    {"bookId": "in", "title": "年内", "author": "甲", "readUpdateTime": 1780000000},
                    {"bookId": "out", "title": "年外", "author": "乙", "readUpdateTime": 1700000000},
                ]
            },
            "stats": {"totalReadTime": 100, "readDays": 2, "readTimes": {}},
            "book_details": {
                "in": {"progress": {"book": {"progress": 50, "recordReadingTime": 100}}, "bookmarks": [], "reviews": []},
                "out": {"progress": {"book": {"progress": 50, "recordReadingTime": 100}}, "bookmarks": [], "reviews": []},
            },
        }
        result = normalize_yearbook(raw, 2026)
        self.assertEqual([book["book_id"] for book in result["books"]], ["in"])

    def test_normalization_excludes_cross_year_annotations_and_books_without_activity(self):
        ts_2026 = int(datetime(2026, 2, 1, tzinfo=timezone.utc).timestamp())
        ts_2023 = int(datetime(2023, 2, 1, tzinfo=timezone.utc).timestamp())
        raw = {
            "source_mode": "live",
            "shelf": {"books": [
                {"bookId": "mixed", "title": "跨年", "author": "甲", "readUpdateTime": ts_2026},
                {"bookId": "none", "title": "无活动", "author": "乙"},
            ]},
            "stats": {},
            "book_details": {
                "mixed": {"progress": {"book": {"progress": 20, "updateTime": ts_2026}}, "bookmarks": {"updated": [
                    {"bookmarkId": "old", "markText": "旧划线", "createTime": ts_2023},
                    {"bookmarkId": "new", "markText": "新划线", "createTime": ts_2026}
                ]}, "reviews": []},
                "none": {"progress": {}, "bookmarks": [], "reviews": []},
            },
        }
        result = normalize_yearbook(raw, 2026)
        self.assertEqual([book["book_id"] for book in result["books"]], ["mixed"])
        self.assertEqual([item["source_id"] for item in result["books"][0]["highlights"]], ["new"])

    def test_collection_never_claims_live_verified_before_final_validation(self):
        self.assertEqual(collection_status(errors=[], truncated=False), "implemented_unverified")
        self.assertEqual(collection_status(errors=[], truncated=True), "partial_unverified")
        self.assertEqual(collection_status(errors=[{"error": "x"}], truncated=False), "partial_unverified")

    def test_live_collection_limits_detail_calls_to_year_candidates(self):
        ts_2026 = int(datetime(2026, 5, 1, tzinfo=timezone.utc).timestamp())
        ts_2024 = int(datetime(2024, 5, 1, tzinfo=timezone.utc).timestamp())
        shelf = {"books": [{"bookId": "current", "readUpdateTime": ts_2026}, {"bookId": "old", "readUpdateTime": ts_2024}]}
        notebooks = {"books": [{"bookId": "noted", "sort": ts_2026, "book": {"bookId": "noted", "title": "笔记书"}}]}
        stats = {"readLongest": [{"book": {"bookId": "ranked", "title": "年度排行书"}, "readTime": 600}]}
        result = select_candidate_books(2026, shelf, notebooks, stats, scan_all=False)
        self.assertEqual({item["bookId"] for item in result}, {"current", "noted", "ranked"})

    def test_scoring_selects_at_least_one_book_and_three_candidates_when_possible(self):
        books = []
        for index in range(10):
            books.append(
                {
                    "book_id": str(index),
                    "title": f"书{index}",
                    "progress": index * 10,
                    "reading_seconds": index * 500,
                    "highlights": [{"text": "证据"}] * index,
                    "thoughts": [{"text": "想法"}] * (index // 2),
                    "bookmark_count": index,
                    "topics": ["决策" if index > 5 else "生活"],
                    "reusability_hint": index / 10,
                }
            )
        scored = score_books(books)
        self.assertEqual(sum(1 for book in scored if book["selected"]), 2)
        self.assertEqual(sum(1 for book in scored if book["book_of_year_candidate"]), 3)
        self.assertGreaterEqual(scored[0]["score"], scored[-1]["score"])

    def test_profiles_cite_only_available_evidence(self):
        book = {
            "book_id": "b1",
            "title": "一本书",
            "author": "作者",
            "intro": "讨论如何看见问题并做出选择。",
            "evidence_level": "E1",
            "highlights": [{"text": "先看事实", "source_id": "hl-1"}],
            "thoughts": [],
            "topics": ["决策"],
        }
        profile = build_profiles([book])[0]
        self.assertIn("hl-1", [item["source_id"] for item in profile["citations"]])
        self.assertNotIn("完整论证", profile["about"])

    def test_profile_reflection_joins_thoughts_without_double_punctuation(self):
        book = {
            "book_id": "b2",
            "title": "两条想法",
            "author": "作者",
            "evidence_level": "E2",
            "highlights": [],
            "thoughts": [{"text": "第一条。", "source_id": "r1"}, {"text": "第二条。", "source_id": "r2"}],
        }
        profile = build_profiles([book])[0]
        self.assertNotIn("。；", profile["reflection"])


class PipelineTests(unittest.TestCase):
    def test_png_export_can_reuse_an_installed_system_browser(self):
        browser = find_browser_executable()
        self.assertIsNotNone(browser)
        self.assertTrue(Path(browser).exists())

    def test_sample_pipeline_builds_public_artifacts_without_secret(self):
        sample = SKILL_ROOT / "assets" / "sample-data.json"
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "2026"
            preview = generate_preview(2026, sample, output)
            selection = preview["selection"]
            selection["status"] = "confirmed"
            selection["confirmed_at"] = "2026-09-28T12:00:00+08:00"
            selection["book_of_year_id"] = selection["book_of_year_candidates"][0]
            selection["selected_book_ids"] = ["sample-001", "sample-002", "sample-003", "sample-005"]
            result = finalize_yearbook(2026, sample, output, selection, export_png=False)
            self.assertTrue((output / "atlas.html").exists())
            self.assertTrue((output / "yearbook-data.json").exists())
            self.assertTrue((output / "selection-preview.md").exists())
            self.assertTrue((output / "validation-report.json").exists())
            self.assertGreaterEqual(len(list((output / "books").glob("*/profile.md"))), 1)
            cover_html = (output / "cards-html" / "01-cover.html").read_text("utf-8")
            self.assertEqual(cover_html.count('class="month-arc"'), 12)
            self.assertIn('class="book-node', cover_html)
            manifest = json.loads((output / "cards-manifest.json").read_text("utf-8"))
            types = {item["type"] for item in manifest}
            self.assertFalse({"cover", "reading-rhythm", "recurring-topics", "book-of-year", "final-question"} - types)
            layouts = {item.get("layout") for item in manifest if item["type"] in {"book-of-year", "selected-book"}}
            self.assertTrue({"vertical", "spread", "fold"}.issubset(layouts))
            self.assertEqual(result["data"]["publication_status"], "final")
            self.assertNotIn("WEREAD_API_KEY", json.dumps(result, ensure_ascii=False))
            for path in output.rglob("*"):
                if path.is_file():
                    self.assertNotIn("wrk-test-secret", path.read_text("utf-8", errors="ignore"))

    def test_deep_distill_requires_real_text_and_can_create_candidate(self):
        text = """第一章 判断\n判断之前先收集事实。方法一：列出假设并寻找反例。\n第二章 行动\n方法二：设定期限并记录结果。不要把短期运气当成长期能力。"""
        result = distill_text(text, title="判断与行动", source_name="user.txt", full_text_confirmed=True)
        self.assertEqual(result["evidence_level"], "E3")
        self.assertGreaterEqual(len(result["sections"]), 2)
        self.assertTrue(result["source_name"].endswith("user.txt"))
        self.assertTrue(all(item.get("source_id") for item in result["candidate_methods"]))

    def test_deep_distill_does_not_claim_e3_without_full_text_confirmation(self):
        text = "第一章 方法\n方法一：先记录事实再行动。\n第二章 边界\n风险过高时不要使用这个方法。"
        result = distill_text(text, title="局部材料", source_name="excerpt.txt", full_text_confirmed=False)
        self.assertEqual(result["evidence_level"], "E2")
        self.assertFalse(result["skill_eligible"])

    def test_epub_text_is_extracted_without_network_access(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            epub = Path(temp_dir) / "book.epub"
            with zipfile.ZipFile(epub, "w") as archive:
                archive.writestr("chapter.xhtml", "<html><body><h1>第一章</h1><p>这是用户提供的正文。</p></body></html>")
            text, status = load_legal_text(epub)
            self.assertEqual(status, "verified")
            self.assertIn("用户提供的正文", text)

    def test_finalize_requires_confirmed_selection(self):
        sample = SKILL_ROOT / "assets" / "sample-data.json"
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "2026"
            preview = generate_preview(2026, sample, output)
            with self.assertRaises(ValueError):
                finalize_yearbook(2026, sample, output, preview["selection"], export_png=False)

    def test_validation_fails_when_requested_png_export_failed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            (output / "yearbook-data.json").write_text(json.dumps({"schema_version": "1.0", "year": 2026, "source_mode": "sample", "verification_status": "sample_verified", "books": [], "profiles": [], "summary": {}}), "utf-8")
            (output / "atlas.html").write_text("<!doctype html><title>x</title>", "utf-8")
            (output / "selection-preview.md").write_text("# x", "utf-8")
            (output / "cards-html").mkdir()
            report = validate_output(output, require_png=True, png_result={"status": "failed", "exported": 0})
            self.assertEqual(report["status"], "fail")


if __name__ == "__main__":
    unittest.main()
