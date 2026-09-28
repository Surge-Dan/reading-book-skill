import json
import os
import sys
import tempfile
import unittest
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
from run_yearbook import generate_yearbook  # noqa: E402
from build_deep_distill import distill_text  # noqa: E402
from export_cards import find_browser_executable  # noqa: E402


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
            result = generate_yearbook(2026, sample, output, export_png=False)
            self.assertTrue((output / "atlas.html").exists())
            self.assertTrue((output / "yearbook-data.json").exists())
            self.assertTrue((output / "selection-preview.md").exists())
            self.assertTrue((output / "validation-report.json").exists())
            self.assertGreaterEqual(len(list((output / "books").glob("*/profile.md"))), 1)
            cover_html = (output / "cards-html" / "01-cover.html").read_text("utf-8")
            self.assertEqual(cover_html.count('class="month-arc"'), 12)
            self.assertIn('class="book-node', cover_html)
            self.assertNotIn("WEREAD_API_KEY", json.dumps(result, ensure_ascii=False))
            for path in output.rglob("*"):
                if path.is_file():
                    self.assertNotIn("wrk-test-secret", path.read_text("utf-8", errors="ignore"))

    def test_deep_distill_requires_real_text_and_can_create_candidate(self):
        text = """第一章 判断\n判断之前先收集事实。方法一：列出假设并寻找反例。\n第二章 行动\n方法二：设定期限并记录结果。不要把短期运气当成长期能力。"""
        result = distill_text(text, title="判断与行动", source_name="user.txt")
        self.assertEqual(result["evidence_level"], "E3")
        self.assertGreaterEqual(len(result["sections"]), 2)
        self.assertTrue(result["source_name"].endswith("user.txt"))


if __name__ == "__main__":
    unittest.main()
