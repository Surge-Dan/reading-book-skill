from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import tempfile
import uuid
from copy import deepcopy
from pathlib import Path

from render_yearbook import render_atlas, render_cards
from validate_yearbook import validate_output
from yearbook_core import build_profiles, choose_yearly_thesis, derive_yearly_topics, normalize_yearbook, score_books


def _slug(book_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", book_id).strip("-") or "book"


def _prepare_data(year: int, input_path: Path) -> tuple[dict, dict]:
    raw = json.loads(Path(input_path).read_text("utf-8"))
    data = normalize_yearbook(raw, int(year))
    data["books"] = score_books(data["books"])
    data["summary"]["book_count"] = len(data["books"])
    data["topics"] = derive_yearly_topics(data["books"])
    data["thesis"] = choose_yearly_thesis(int(year), data["topics"], data["books"])
    data["profiles"] = build_profiles(data["books"])
    data["publication_status"] = "draft"
    return raw, data


def _selection_manifest(data: dict) -> dict:
    return {
        "year": data["year"],
        "status": "pending_user_confirmation",
        "selected_book_ids": [book["book_id"] for book in data["books"] if book["selected"]],
        "book_of_year_candidates": [book["book_id"] for book in data["books"] if book["book_of_year_candidate"]],
        "book_of_year_id": None,
        "confirmed_at": None,
        "instructions": "调整 selected_book_ids，选择 book_of_year_id，并将 status 改为 confirmed 后再运行 finalize。",
    }


def _selection_markdown(data: dict, selection: dict) -> str:
    lines = [f"# {data['year']} 年精选确认", "", f"> 数据模式：`{data['source_mode']}`；验证状态：`{data['verification_status']}`。", "", "## 前 20% 推荐", ""]
    selected_ids = set(selection["selected_book_ids"])
    lines.extend(f"- [{'x' if book['book_id'] in selected_ids else ' '}] **{book['title']}**｜ID `{book['book_id']}`｜{book['score']} 分｜{book['score_reason']}" for book in data["books"])
    lines.extend(["", "## 年度之书候选", ""])
    lines.extend(f"- [ ] **{book['title']}**｜ID `{book['book_id']}`｜{book['score']} 分｜{book['evidence_reason']}" for book in data["books"] if book["book_of_year_candidate"])
    lines.extend(["", "## 确认方式", "", "编辑同目录 `selection.json`：调整 `selected_book_ids`，填写 `book_of_year_id`，补充 `confirmed_at`，并将 `status` 改为 `confirmed`。预览阶段不会生成最终图谱和卡片。", ""])
    return "\n".join(lines)


def generate_preview(year: int, input_path: Path, output_dir: Path) -> dict:
    _, data = _prepare_data(year, input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    selection = _selection_manifest(data)
    (output_dir / "yearbook-data.draft.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
    (output_dir / "selection.json").write_text(json.dumps(selection, ensure_ascii=False, indent=2), "utf-8")
    (output_dir / "selection-preview.md").write_text(_selection_markdown(data, selection), "utf-8")
    return {"data": data, "selection": selection, "output": str(output_dir)}


def _apply_selection(data: dict, selection: dict) -> None:
    if selection.get("status") != "confirmed" or not selection.get("confirmed_at"):
        raise ValueError("selection.json 尚未由用户确认。")
    known = {book["book_id"] for book in data["books"]}
    selected = list(dict.fromkeys(str(item) for item in selection.get("selected_book_ids", [])))
    unknown = sorted(set(selected) - known)
    if unknown:
        raise ValueError(f"selection.json 包含未知书籍：{', '.join(unknown)}")
    book_of_year = str(selection.get("book_of_year_id") or "")
    candidates = {book["book_id"] for book in data["books"] if book["book_of_year_candidate"]}
    if not selected or book_of_year not in selected:
        raise ValueError("年度之书必须属于用户确认的精选书。")
    for book in data["books"]:
        book["selected"] = book["book_id"] in selected
        book["book_of_year"] = book["book_id"] == book_of_year
    data["selection"] = {"selected_book_ids": selected, "book_of_year_id": book_of_year, "confirmed_at": selection["confirmed_at"], "user_override": book_of_year not in candidates}
    data["publication_status"] = "final"


def _profile_markdown(profile: dict, book: dict) -> str:
    lines = [f"# {profile['title']}", "", f"作者：{profile['author']}", f"证据等级：{profile['evidence_level']}", "", "## 这本书讲了啥", "", profile["about"], "", "## 我的思考", "", profile["reflection"], "", "## 证据索引", ""]
    lines.extend(f"- `{item['source_id']}` · {item['type']} · {item['text']}" for item in profile["citations"])
    if not profile["citations"]:
        lines.append("- 暂无可引用证据。")
    lines.extend(["", "## 年度位置", "", f"月份：{', '.join(map(str, book.get('months', []))) or '未记录'}", f"主题：{'、'.join(book.get('topics', [])) or '未形成'}", f"代表性得分：{book.get('score', 0)}（{book.get('score_reason', '无')}）", ""])
    return "\n".join(lines)


def _clear_generated(folder: Path, suffix: str) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for path in folder.glob(f"*{suffix}"):
        if path.is_file():
            path.unlink()


def _clear_profile_files(output_dir: Path) -> None:
    books_dir = output_dir / "books"
    if not books_dir.exists():
        return
    for filename in ("profile.md", "evidence.json"):
        for path in books_dir.glob(f"*/{filename}"):
            if path.is_file():
                path.unlink()


def _publish_staging(staging_dir: Path, output_dir: Path) -> None:
    backup_dir = output_dir.parent / f".{output_dir.name}.backup-{uuid.uuid4().hex}"
    had_output = output_dir.exists()
    if had_output:
        os.replace(output_dir, backup_dir)
    try:
        os.replace(staging_dir, output_dir)
    except Exception:
        if had_output and backup_dir.exists() and not output_dir.exists():
            os.replace(backup_dir, output_dir)
        raise
    if backup_dir.exists():
        shutil.rmtree(backup_dir)


def _write_final_artifacts(data: dict, selection: dict, output_dir: Path) -> tuple[list[Path], list[dict]]:
    (output_dir / "yearbook-data.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
    (output_dir / "selection.json").write_text(json.dumps(selection, ensure_ascii=False, indent=2), "utf-8")
    profiles = {item["book_id"]: item for item in data["profiles"]}
    for book in data["books"]:
        folder = output_dir / "books" / _slug(book["book_id"])
        folder.mkdir(parents=True, exist_ok=True)
        profile = profiles[book["book_id"]]
        (folder / "profile.md").write_text(_profile_markdown(profile, book), "utf-8")
        evidence = {"book_id": book["book_id"], "evidence_level": book["evidence_level"], "reason": book["evidence_reason"], "citations": profile["citations"]}
        (folder / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), "utf-8")
    render_atlas(data, output_dir / "atlas.html")
    _clear_generated(output_dir / "cards-html", ".html")
    rendered, manifest = render_cards(data, output_dir / "cards-html")
    (output_dir / "cards-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), "utf-8")
    return rendered, manifest


def finalize_yearbook(year: int, input_path: Path, output_dir: Path, selection: dict, export_png: bool = False) -> dict:
    raw, data = _prepare_data(year, input_path)
    if data["source_mode"] == "live" and (data["verification_status"] == "partial_unverified" or not raw.get("collection_complete", False)):
        raise ValueError("真实数据采集不完整，只能保留预览，不能生成最终版。")
    draft_data = deepcopy(data)
    _apply_selection(data, selection)
    live_candidate = data["source_mode"] == "live" and raw.get("collection_complete", False)
    if live_candidate:
        data["verification_status"] = "live_verified"
    output_dir = Path(output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.staging-", dir=output_dir.parent))
    try:
        if output_dir.exists():
            shutil.copytree(output_dir, staging_dir, dirs_exist_ok=True)
        (staging_dir / "yearbook-data.draft.json").write_text(json.dumps(draft_data, ensure_ascii=False, indent=2), "utf-8")
        (staging_dir / "selection-preview.md").write_text(_selection_markdown(draft_data, selection), "utf-8")
        _clear_profile_files(staging_dir)
        html_cards, _ = _write_final_artifacts(data, selection, staging_dir)
        export_result = {"status": "skipped", "reason": "未请求 PNG 导出", "exported": 0}
        if export_png:
            from export_cards import export_cards

            _clear_generated(staging_dir / "cards", ".png")
            export_result = export_cards(staging_dir / "cards-html", staging_dir / "cards")
        report = validate_output(staging_dir, require_png=export_png, png_result=export_result)
        report["png_export"] = export_result
        report["source_mode"] = data["source_mode"]
        report["verification_status"] = data["verification_status"]
        (staging_dir / "validation-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
        if report["status"] != "pass":
            if live_candidate:
                data["verification_status"] = "implemented_unverified"
                data["publication_status"] = "draft"
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "validation-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
            return {"data": data, "output": str(output_dir), "card_html_count": len(html_cards), "validation": report}
        _publish_staging(staging_dir, output_dir)
        return {"data": data, "output": str(output_dir), "card_html_count": len(html_cards), "validation": report}
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description="生成一套可追溯的微信读书年度阅读档案。")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--input", type=Path, required=True, help="采集后的原始 JSON；可使用 assets/sample-data.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stage", choices=("preview", "finalize"), default="preview")
    parser.add_argument("--selection", type=Path, help="finalize 阶段必需，指向用户确认后的 selection.json")
    parser.add_argument("--export-png", action="store_true")
    args = parser.parse_args()
    if args.stage == "preview":
        result = generate_preview(args.year, args.input, args.output)
        print(json.dumps({"status": "awaiting_confirmation", "selection": str(Path(args.output) / "selection.json")}, ensure_ascii=False))
        return 0
    if not args.selection:
        parser.error("--stage finalize 必须提供 --selection")
    selection = json.loads(args.selection.read_text("utf-8"))
    try:
        result = finalize_yearbook(args.year, args.input, args.output, selection, args.export_png)
    except ValueError as exc:
        print(json.dumps({"status": "blocked", "message": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps({"status": "ok", "output": result["output"], "validation": result["validation"]["status"]}, ensure_ascii=False))
    return 0 if result["validation"]["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
