import importlib.util
import json
import os
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "reading-yearbook-skill"
sys.path.insert(0, str(SKILL / "scripts"))
sys.path.insert(0, str(SKILL / "examples"))
from workflow_fixture import sample_decisions, build as build_annual_fixture
from share_contract import make_canvas, preview_ids, require_scope
from run_share import (approve_scope, approve_content, approve_visual, content_hash, digest, export_share,
                       file_digest, load_job, prepare_share, require_content, status, validate_job, write_json)


class ShareStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name) / "share"
        self.job = prepare_share(2026, SKILL / "assets/sample-data.json", self.folder, ["sample-002"], "book-list")
        sample_decisions(self.job)
        self.job["art_brief"] = {"focus": "街道观察", "layout": "照片全景与局部"}
        write_json(self.folder / "share-job.json", self.job)
        approve_scope(self.folder, True)

    def tearDown(self):
        self.temp.cleanup()

    def test_prepare_keeps_selected_evidence_without_full_archives(self):
        self.assertEqual([b["book_id"] for b in self.job["books"]], ["sample-002"])
        self.assertFalse(any(ref.startswith("sample-001/") for ref in self.job["sources"]))
        self.assertNotIn("profiles", self.job)
        self.assertFalse((self.folder / "atlas.html").exists())
        self.assertEqual(len(self.job["pages"]), 2)

    def test_existing_job_is_not_overwritten_on_prepare(self):
        previous = (self.folder / "share-job.json").read_bytes()
        with self.assertRaises(ValueError):
            prepare_share(2026, SKILL / "assets/sample-data.json", self.folder)
        self.assertEqual((self.folder / "share-job.json").read_bytes(), previous)

    def test_changed_direct_thought_is_rejected_but_layout_whitespace_is_allowed(self):
        block = self.job["pages"][1]["blocks"][-1]
        block["text"] = block["text"].replace("每天经过", "每天\n经过")
        validate_job(self.job, self.folder)
        block["text"] = "这本书彻底改变了我的人生。"
        with self.assertRaisesRegex(ValueError, "与来源不一致"):
            validate_job(self.job, self.folder)

    def test_content_or_art_changes_invalidate_content_approval(self):
        job = approve_content(self.folder, True)
        require_content(job)
        job["caption"] += "\n另一段文案"
        with self.assertRaises(ValueError):
            require_content(job)
        job = approve_content(self.folder, True)
        job["art_brief"]["focus"] = "另一个方向"
        with self.assertRaises(ValueError):
            require_content(job)

    def test_live_partial_data_cannot_use_test_approval_or_finalize(self):
        self.job["source_mode"] = "live"
        self.job["coverage"].update(collection_complete=False, verification_status="partial_unverified")
        write_json(self.folder / "share-job.json", self.job)
        with self.assertRaisesRegex(ValueError, "技术测试"):
            approve_content(self.folder, True)
        evidence = {"reply": "确认本次范围和内容，数据不完整先看草稿。", "context_ref": "test:live-partial"}
        approve_scope(self.folder, confirmation=evidence)
        approve_content(self.folder, confirmation=evidence)
        with self.assertRaisesRegex(ValueError, "采集不完整"):
            export_share(self.folder, "final")

    def test_fabricated_user_input_and_asset_path_escape_are_rejected(self):
        block = self.job["pages"][1]["blocks"][-1]
        block.update(kind="user_input", provided_by_user=False)
        with self.assertRaisesRegex(ValueError, "来自用户"):
            validate_job(self.job, self.folder)
        block["provided_by_user"] = True
        self.job["assets"] = [{"path": "../private.jpg", "source": "user", "rights": "user-provided"}]
        with self.assertRaisesRegex(ValueError, "分享目录"):
            validate_job(self.job, self.folder)

    def test_missing_runtime_retains_draft_and_does_not_create_pngs(self):
        approve_content(self.folder, True)
        with patch("run_share.shutil.which", return_value=None):
            result = export_share(self.folder, "preview")
        self.assertEqual(result["status"], "unavailable")

    def test_invalid_explicit_node_retains_draft(self):
        approve_content(self.folder, True)
        result = export_share(self.folder, "preview", node=str(self.folder / "absent-node.exe"))
        self.assertEqual(result["status"], "unavailable")
        self.assertFalse((self.folder / "images").exists())
        self.assertFalse((self.folder / "images").exists())
        self.assertEqual(status(self.folder)["status"], "draft")

    def test_numeric_book_ids_produce_valid_html_and_block_ids(self):
        raw = json.loads((SKILL / "assets/sample-data.json").read_text("utf-8"))
        for item in raw["shelf"]["books"]:
            if item["bookId"] == "sample-002":
                item["bookId"] = "123456"
        raw["book_details"]["123456"] = raw["book_details"].pop("sample-002")
        fixture = Path(self.temp.name) / "numeric.json"
        write_json(fixture, raw)
        folder = Path(self.temp.name) / "numeric"
        job = prepare_share(2026, fixture, folder, ["123456"])
        job["art_brief"] = {"focus": "test"}
        validate_job(job, folder)

    def test_long_material_is_bounded_and_cannot_masquerade_as_full_quote(self):
        raw = json.loads((SKILL / "assets/sample-data.json").read_text("utf-8"))
        row = raw["book_details"]["sample-002"]["reviews"]["reviews"][0]["review"]
        row["content"] = "长材料" * 400
        fixture = Path(self.temp.name) / "long.json"
        write_json(fixture, raw)
        folder = Path(self.temp.name) / "long"
        job = prepare_share(2026, fixture, folder, ["sample-002"], "book-list")
        source = job["sources"]["sample-002/thought/s2-r1"]
        self.assertTrue(source["truncated"])
        self.assertEqual(len(source["text"]), 800)
        job["art_brief"] = {"focus": "test"}
        job["pages"][1]["blocks"].append({"id": "wrong-quote", "kind": "thought", "text": source["text"], "source_refs": ["sample-002/thought/s2-r1"]})
        with self.assertRaisesRegex(ValueError, "截断"):
            validate_job(job, folder)

    def test_annual_candidates_do_not_choose_a_ratio_or_approve_scope(self):
        folder = Path(self.temp.name) / "annual"
        job = prepare_share(2026, SKILL / "assets/sample-data.json", folder)
        self.assertIsNone(job["canvas"])
        self.assertFalse(job["approvals"])
        self.assertEqual([p["role"] for p in job["pages"][:3]], ["cover", "overview", "book"])
        self.assertEqual(preview_ids(job), ["cover", "overview", job["pages"][2]["id"]])
        with self.assertRaisesRegex(ValueError, "比例"):
            approve_scope(folder, True)

    def test_confirmation_requires_reply_and_context_not_just_actor(self):
        for evidence in (None, {}, {"reply": "可以"}, {"reply": "可以", "context_ref": " "}):
            with self.subTest(evidence=evidence), self.assertRaisesRegex(ValueError, "实际回复"):
                approve_content(self.folder, confirmation=evidence)
        job = approve_content(self.folder, confirmation={"reply": "确认内容，选择方向a。", "context_ref": "test:creation-reply"})
        require_content(job)
        job["approvals"]["content"].pop("evidence")
        with self.assertRaisesRegex(ValueError, "未确认"):
            require_content(job)

    def test_confirmation_does_not_persist_credentials(self):
        before = (self.folder / "share-job.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "密钥"):
            approve_content(self.folder, confirmation={"reply": "WEREAD_API_KEY=synthetic-test", "context_ref": "test:synthetic-secret"})
        self.assertEqual((self.folder / "share-job.json").read_bytes(), before)

    def test_scope_changes_invalidate_later_steps(self):
        for change in (lambda j: j.update(canvas=make_canvas("1:1")),
                       lambda j: j["brief"].update(platform="其他平台"),
                       lambda j: j["pages"].append(deepcopy(j["pages"][-1]))):
            job = approve_content(self.folder, True)
            change(job)
            with self.assertRaises(ValueError):
                require_content(job)

    def test_two_directions_and_actual_font_reference_decisions_are_required(self):
        for mutate in (lambda j: j.update(directions=j["directions"][:1]),
                       lambda j: j["directions"][0].update(fonts=[]),
                       lambda j: j["directions"][1].update(references=[]),
                       lambda j: j.update(selected_direction=None)):
            job = deepcopy(self.job)
            mutate(job)
            write_json(self.folder / "share-job.json", job)
            approve_scope(self.folder, True)
            with self.assertRaises(ValueError):
                approve_content(self.folder, True)

    def test_quotation_is_not_a_personal_takeaway(self):
        page = self.job["pages"][1]
        page["blocks"] = [block for block in page["blocks"] if block["kind"] != "thought"]
        ref = next(ref for ref in self.job["books"][0]["excerpt_refs"] if self.job["sources"][ref]["kind"] == "highlight")
        page["blocks"].append({"id": "quote-only", "kind": "quote", "text": self.job["sources"][ref]["text"], "source_refs": [ref]})
        page['storyboard']['supporting_blocks'] = [b['id'] for b in page['blocks']]
        write_json(self.folder / "share-job.json", self.job)
        approve_scope(self.folder, True)
        with self.assertRaisesRegex(ValueError, "个人想法"):
            approve_content(self.folder, True)
        self.job["brief"]["focus"] = "excerpts"
        write_json(self.folder / "share-job.json", self.job)
        approve_scope(self.folder, True)
        approve_content(self.folder, True)

    def test_legacy_approval_cannot_silently_bypass_new_brief(self):
        self.job["schema_version"] = "share-1"
        write_json(self.folder / "share-job.json", self.job)
        with self.assertRaisesRegex(ValueError, "旧任务"):
            approve_content(self.folder, True)

    def test_canvas_ratio_bounds_and_single_image_scope(self):
        for ratio, dimensions in (("1:1", (900, 900)), ("3:4", (900, 1200)), ("4:5", (900, 1125))):
            canvas = make_canvas(ratio)
            self.assertEqual((canvas["width"], canvas["height"]), dimensions)
        self.assertEqual(make_canvas("custom", 800, 1000)["ratio"], "4:5")
        for args in (("1:1", 900, 1200), ("custom", 100, 900), ("custom", 900, 9000)):
            with self.assertRaises(ValueError):
                make_canvas(*args)
        folder = Path(self.temp.name) / "single"
        job = prepare_share(2026, SKILL / "assets/sample-data.json", folder, ["sample-002"], "single-image")
        sample_decisions(job, "1:1")
        self.assertEqual(len(job["pages"]), 1)
        write_json(folder / "share-job.json", job)
        approve_scope(folder, True)


@unittest.skipUnless(os.environ.get("SHARE_NODE") and os.environ.get("SHARE_PLAYWRIGHT") and os.environ.get("SHARE_BROWSER"), "Set SHARE_NODE, SHARE_PLAYWRIGHT and SHARE_BROWSER for the real local-render test.")
class ShareRenderTests(unittest.TestCase):
    def test_real_export_cache_single_page_edit_and_failed_layout_preserves_images(self):
        spec = importlib.util.spec_from_file_location("share_demo", SKILL / "examples/build_share_demo.py")
        demo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(demo)
        options = {"node": os.environ["SHARE_NODE"], "playwright_package": os.environ["SHARE_PLAYWRIGHT"], "browser": os.environ["SHARE_BROWSER"]}
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "share"
            demo.build(folder)
            approve_scope(folder, True)
            approve_content(folder, True)
            first = export_share(folder, "preview", **options)
            self.assertEqual((first["rendered"], first["reused"]), (2, 0))
            approve_visual(folder, True)
            final = export_share(folder, "final", **options)
            self.assertEqual((final["rendered"], final["reused"]), (2, 2))
            self.assertEqual(status(folder)["status"], "ready_sample")
            repeated = export_share(folder, "final", **options)
            self.assertEqual((repeated["rendered"], repeated["reused"]), (0, 4))
            old_images = {p.name: file_digest(p) for p in (folder / "images").glob("*.png")}
            job = load_job(folder)
            block = next(b for b in job["pages"][-1]["blocks"] if b["id"] == "b-sample-005-about")
            old, replacement = block["text"], "写的是澄清边界和寻找证据。"
            block["text"] = replacement
            write_json(folder / "share-job.json", job)
            html = (folder / "deck.html").read_text("utf-8").replace(old, replacement)
            (folder / "deck.html").write_text(html, "utf-8")
            self.assertEqual(status(folder)["status"], "draft")
            with self.assertRaisesRegex(ValueError, "未确认"):
                export_share(folder, "final", **options)
            approve_content(folder, True)
            revised = export_share(folder, "final", **options)
            self.assertEqual((revised["rendered"], revised["reused"]), (1, 3))
            new_images = {p.name: file_digest(p) for p in (folder / "images").glob("*.png")}
            self.assertEqual(sum(old_images[name] != value for name, value in new_images.items()), 1)
            good_report = (folder / "validation-report.json").read_bytes()
            broken = html.replace('class="quote" data-block="b-sample-005-quote"', 'class="quote" style="top:1160px" data-block="b-sample-005-quote"')
            (folder / "deck.html").write_text(broken, "utf-8")
            failed = export_share(folder, "final", **options)
            self.assertEqual(failed["status"], "failed")
            self.assertTrue(any(e["problem"] == "text_clipped_or_hidden" for e in failed["errors"]))
            self.assertEqual(good_report, (folder / "validation-report.json").read_bytes())
            self.assertEqual(new_images, {p.name: file_digest(p) for p in (folder / "images").glob("*.png")})
            self.assertEqual(status(folder)["status"], "draft")
            (folder / "deck.html").write_text(html, "utf-8")
            self.assertEqual(status(folder)["status"], "ready_sample")

    def test_css_image_changes_invalidate_only_its_page(self):
        spec = importlib.util.spec_from_file_location("botanical_demo", SKILL / "examples/build_botanical_demo.py")
        demo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(demo)
        options = {"node": os.environ["SHARE_NODE"], "playwright_package": os.environ["SHARE_PLAYWRIGHT"], "browser": os.environ["SHARE_BROWSER"]}
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "botanical"
            demo.build(folder)
            css_asset = folder / "assets/paper (1).svg"
            css_asset.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect width="10" height="10" fill="#702936"/></svg>', "utf-8")
            job = load_job(folder)
            job["assets"].append({"path": "assets/paper (1).svg", "source": "original test", "rights": "original", "sha256": file_digest(css_asset)})
            write_json(folder / "share-job.json", job)
            html = (folder / "deck.html").read_text("utf-8").replace('class="page inside"', 'class="page inside" style="background-image:url(\'assets/paper (1).svg\')"')
            (folder / "deck.html").write_text(html, "utf-8")
            approve_scope(folder, True)
            approve_content(folder, True)
            export_share(folder, "preview", **options)
            approve_visual(folder, True)
            export_share(folder, "final", **options)
            css_asset.write_text(css_asset.read_text("utf-8").replace('#702936', '#622331'), "utf-8")
            job = load_job(folder)
            job["assets"][-1]["sha256"] = file_digest(css_asset)
            write_json(folder / "share-job.json", job)
            approve_content(folder, True)
            preview = export_share(folder, "preview", **options)
            self.assertEqual((preview["rendered"], preview["reused"]), (1, 1))
            approve_visual(folder, True)
            self.assertEqual(export_share(folder, "final", **options)["status"], "pass")

    def test_annual_three_previews_and_all_canvas_sizes(self):
        options = {"node": os.environ["SHARE_NODE"], "playwright_package": os.environ["SHARE_PLAYWRIGHT"], "browser": os.environ["SHARE_BROWSER"]}
        with tempfile.TemporaryDirectory() as temp:
            for ratio in ("1:1", "3:4", "4:5"):
                with self.subTest(ratio=ratio):
                    folder = Path(temp) / ratio.replace(":", "-")
                    build_annual_fixture(folder, ratio)
                    approve_scope(folder, True)
                    approve_content(folder, True)
                    preview = export_share(folder, "preview", **options)
                    self.assertEqual((preview["rendered"], preview["pages"]), (3, 3))
                    report = json.loads((folder / "validation-report.json").read_text("utf-8"))
                    self.assertEqual(report["requested_ids"], preview_ids(load_job(folder)))
                    with self.assertRaisesRegex(ValueError, "实际图片"):
                        export_share(folder, "final", **options)
                    approve_visual(folder, True)
                    result = export_share(folder, "final", **options)
                    self.assertEqual((result["rendered"], result["reused"]), (2, 3))
                    self.assertEqual(status(folder)["status"], "ready_sample")
                    canvas = make_canvas(ratio)
                    for png in (folder / "images").glob("*.png"):
                        header = png.read_bytes()[:24]
                        self.assertEqual((int.from_bytes(header[16:20], "big"), int.from_bytes(header[20:24], "big")), (canvas["width"], canvas["height"]))
                    overview = (folder / "overview.png").read_bytes()[:24]
                    self.assertEqual(int.from_bytes(overview[16:20], "big"), 750)
                    self.assertGreater(int.from_bytes(overview[20:24], "big"), canvas["height"] * 375 / canvas["width"])


if __name__ == "__main__":
    unittest.main()
