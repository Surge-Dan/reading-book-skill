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
from run_share import (approve_content, approve_visual, content_hash, digest, export_share,
                       file_digest, load_job, prepare_share, require_content, status, validate_job, write_json)


class ShareStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name) / "share"
        self.job = prepare_share(2026, SKILL / "assets/sample-data.json", self.folder, ["sample-002"])
        self.job["art_brief"] = {"focus": "街道观察", "layout": "照片全景与局部"}
        write_json(self.folder / "share-job.json", self.job)

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
        approve_content(self.folder)
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
        job = prepare_share(2026, fixture, folder, ["sample-002"])
        source = job["sources"]["sample-002/thought/s2-r1"]
        self.assertTrue(source["truncated"])
        self.assertEqual(len(source["text"]), 800)
        job["art_brief"] = {"focus": "test"}
        job["pages"][1]["blocks"].append({"id": "wrong-quote", "kind": "thought", "text": source["text"], "source_refs": ["sample-002/thought/s2-r1"]})
        with self.assertRaisesRegex(ValueError, "截断"):
            validate_job(job, folder)


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


if __name__ == "__main__":
    unittest.main()
