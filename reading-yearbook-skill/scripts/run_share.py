"""Local sharing workflow. The host agent writes prose/HTML; this manages evidence and exports."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from yearbook_core import normalize_yearbook
from static_graphics import validate_graphics
from share_contract import (FORMATS, confirmation_record, make_canvas, preview_ids,
                            require_confirmation, require_scope, scope_payload,
                            validate_creation, validate_scope)

SCRIPT_DIR = Path(__file__).resolve().parent
ID_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,79}$")


def digest(value) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compact_text(text: str) -> str:
    return "".join(text.split())


def load_job(folder: Path) -> dict:
    return json.loads((Path(folder) / "share-job.json").read_text("utf-8"))


def write_json(path: Path, value: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.writing")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", "utf-8")
    os.replace(temporary, path)


def local_asset(folder: Path, relative: str) -> Path:
    root = Path(folder).resolve()
    candidate = (root / relative).resolve()
    if Path(relative).is_absolute() or not candidate.is_relative_to(root) or candidate == root:
        raise ValueError("素材路径必须位于分享目录内。")
    return candidate


def content_hash(job: dict) -> str:
    return digest({key: job.get(key) for key in ("schema_version", "year", "source_mode", "coverage", "period", "sources", "books", "pages", "art_brief", "assets", "caption", "brief", "canvas", "directions", "selected_direction", "annual_summary", "preview_page_ids")})


def validate_job(job: dict, folder: Path) -> None:
    if job.get("schema_version") not in ("share-1", "share-2", "share-3") or job.get("source_mode") not in ("sample", "live"):
        raise ValueError("不支持的分享数据模式或版本。")
    if not job.get("pages"):
        raise ValueError("没有可分享的书籍；不要为了凑页数生成卡组。")
    book_ids = {book["book_id"] for book in job["books"]}
    if len(book_ids) != len(job["books"]):
        raise ValueError("精选书籍 ID 重复。")
    seen_pages, seen_blocks = set(), set()
    for page in job["pages"]:
        page_id = page["id"]
        if not ID_PATTERN.fullmatch(page_id) or page_id in seen_pages:
            raise ValueError("页面 ID 必须唯一，以字母开头，只含字母、数字、下划线或连字符。")
        seen_pages.add(page_id)
        if set(page.get("book_ids", [])) - book_ids:
            raise ValueError(f"{page_id} 引用了未知书籍。")
        for block in page["blocks"]:
            block_id = block["id"]
            if not ID_PATTERN.fullmatch(block_id) or block_id in seen_blocks or not block.get("text", "").strip():
                raise ValueError("内容块 ID 重复、格式错误或文字为空。")
            seen_blocks.add(block_id)
            refs = block.get("source_refs", [])
            if any(ref not in job["sources"] for ref in refs):
                raise ValueError(f"{block_id} 引用了不存在的来源。")
            kind = block["kind"]
            if kind in ("fact", "quote", "thought"):
                if len(refs) != 1:
                    raise ValueError(f"{block_id} 必须绑定一个原始来源。")
                source = job["sources"][refs[0]]
                expected_kind = {"fact": "fact", "quote": "highlight", "thought": "thought"}[kind]
                if source["kind"] != expected_kind or source.get("truncated") or compact_text(block["text"]) != compact_text(source["text"]):
                    raise ValueError(f"{block_id} 与来源不一致；引文不得改写，截断材料只能作编辑归纳。")
            elif kind == "editorial":
                pass  # Grounding of paraphrases is reviewed by the host agent and user.
            elif kind == "user_input":
                if not block.get("provided_by_user"):
                    raise ValueError("补充感受必须来自用户，不得冒充历史笔记。")
            else:
                raise ValueError(f"未知内容类型：{kind}")
    covers = [page for page in job["pages"] if page["role"] == "cover"]
    if len(covers) != 1 or job["pages"][0]["role"] != "cover":
        raise ValueError("分享任务需要恰好一张开头封面，其他页由内容决定。")
    asset_paths = set()
    for asset in job["assets"]:
        path = local_asset(folder, asset["path"])
        if asset["path"] in asset_paths:
            raise ValueError("素材路径重复。")
        asset_paths.add(asset["path"])
        if not asset.get("rights") or not asset.get("source"):
            raise ValueError("素材须记录来源与使用依据。")
        if not path.is_file() or file_digest(path) != asset.get("sha256"):
            raise ValueError("素材文件缺失或版本变化；核对来源并更新素材记录后重新确认。")
    if re.search(r"\bwrk-[a-zA-Z0-9_-]{12,}|WEREAD_API_KEY\s*[:=]", json.dumps(job, ensure_ascii=False)):
        raise ValueError("分享文件疑似包含密钥，不可导出。")
    validate_graphics(job)


def prepare_share(year: int, input_path: Path, folder: Path, selected_ids: list[str] | None = None, share_format: str = "annual") -> dict:
    folder = Path(folder)
    if (folder / "share-job.json").exists():
        raise ValueError("分享任务已存在；局部修改复用它，不重新采集或覆盖确认。")
    if share_format not in FORMATS:
        raise ValueError("未知分享类型。")
    raw = json.loads(Path(input_path).read_text("utf-8"))
    if "books" in raw and "summary" in raw and "year" in raw:
        if int(raw["year"]) != year:
            raise ValueError("已有规范化数据的年份不一致。")
        data = raw
    else:
        data = normalize_yearbook(raw, year)
    if data["source_mode"] not in ("sample", "live"):
        raise ValueError("先确认数据是样例还是来自真实采集。")
    known = {book["book_id"]: book for book in data["books"]}
    if selected_ids is None:
        # This is a candidate list, not a preference ranking or final user choice.
        selected_ids = [book["book_id"] for book in sorted(data["books"], key=lambda b: (bool(b.get("thoughts")), len(b.get("thoughts", [])), b.get("annual_reading_seconds", 0)), reverse=True)[:3]]
    if len(selected_ids) != len(set(selected_ids)) or set(selected_ids) - known.keys():
        raise ValueError("精选书 ID 重复或不存在。")
    sources = {"period/year": {"kind": "fact", "text": str(year)}}
    books, pages = [], []
    cover_blocks = [{"id": "cover-title", "kind": "editorial", "text": f"{year}年读过的几本书", "source_refs": []},
                    {"id": "cover-year", "kind": "fact", "text": str(year), "source_refs": ["period/year"]}]
    for book_id in selected_ids:
        book = known[book_id]
        slug = "b-" + re.sub(r"[^a-zA-Z0-9_-]", "-", book_id)[:55]
        if not slug.strip("b-") or f"book-{slug}" in {p["id"] for p in pages}:
            slug = "b-" + hashlib.sha256(book_id.encode()).hexdigest()[:12]
        title_ref, author_ref, intro_ref = (f"{book_id}/{name}" for name in ("title", "author", "intro"))
        for key, ref in (("title", title_ref), ("author", author_ref), ("intro", intro_ref)):
            text = str(book.get(key, ""))
            sources[ref] = {"kind": "fact", "text": text[:800], "truncated": len(text) > 800, "original_characters": len(text)}
        excerpts = []
        for kind, field in (("highlight", "highlights"), ("thought", "thoughts")):
            for item in book.get(field, [])[:2]:
                ref = f"{book_id}/{kind}/{item['source_id']}"
                text = item["text"]
                sources[ref] = {"kind": kind, "source_id": item["source_id"], "text": text[:800], "truncated": len(text) > 800, "original_characters": len(text), "created_at": item.get("created_at")}
                excerpts.append(ref)
        books.append({"book_id": book_id, "title": book["title"], "author": book["author"], "evidence_level": book["evidence_level"],
                      "excerpt_refs": excerpts, "available_highlights": len(book.get("highlights", [])), "available_thoughts": len(book.get("thoughts", [])),
                      "candidate_reason": "有个人笔记，可先讨论阅读所得" if any(sources[ref]["kind"] == "thought" for ref in excerpts) else "有书目或划线，尚需补充个人想法"})
        cover_blocks.append({"id": f"cover-book-{slug}", "kind": "fact", "text": book["title"], "source_refs": [title_ref]})
        blocks = [{"id": f"{slug}-title", "kind": "fact", "text": book["title"], "source_refs": [title_ref]},
                  {"id": f"{slug}-author", "kind": "fact", "text": book["author"], "source_refs": [author_ref]}]
        if book.get("intro"):
            blocks.append({"id": f"{slug}-about", "kind": "editorial", "text": book["intro"][:800], "source_refs": [intro_ref]})
        usable = [ref for ref in excerpts if not sources[ref]["truncated"]]
        thought_ref = next((ref for ref in usable if sources[ref]["kind"] == "thought"), None)
        chosen = thought_ref or (usable[0] if usable else None)
        if chosen:
            blocks.append({"id": f"{slug}-note", "kind": "thought" if thought_ref else "quote", "text": sources[chosen]["text"], "source_refs": [chosen]})
        pages.append({"id": f"book-{slug}", "role": "book", "book_ids": [book_id], "blocks": blocks})
    today = date.today()
    period = {"year": year, "as_of": min(today, date(year, 12, 31)).isoformat(), "complete": today > date(year, 12, 31)}
    complete = bool(raw.get("collection_complete") or data.get("verification_status") == "live_verified" or data["source_mode"] == "sample")
    caption = f"{year}年的书，挑几本聊聊。\n\n" + "\n".join(f"- 《{book['title']}》" for book in books)
    if data["source_mode"] == "sample":
        caption += "\n\n样例：虚构书籍与笔记，仅作设计演示。"
    elif not period["complete"]:
        caption += f"\n\n记录截至{period['as_of']}。"
    summary = {key: data["summary"][key] for key in ("total_read_seconds", "read_days", "monthly_read_seconds", "monthly_observed") if key in data["summary"]}
    overview_blocks = [{"id": "overview-title", "kind": "editorial", "text": "这一年的阅读记录", "source_refs": []}]
    if "monthly_observed" in summary:
        sources["summary/monthly-records"] = {"kind": "fact", "text": "按月汇总已提供的时长记录",
                                             "value": {"seconds": summary["monthly_read_seconds"], "observed": summary["monthly_observed"]},
                                             "basis": "provided dated records; absence is unknown, not zero; not proof of complete monthly coverage"}
    for key, text in (("total_read_seconds", f"{int(summary.get('total_read_seconds', 0)) // 3600}小时{int(summary.get('total_read_seconds', 0)) % 3600 // 60}分钟"),
                      ("read_days", f"{summary.get('read_days', 0)}天阅读")):
        if key in summary:
            ref = f"summary/{key}"
            sources[ref] = {"kind": "fact", "text": text, "value": summary[key], "basis": "normalized annual statistics; not selected-book totals"}
            overview_blocks.append({"id": f"overview-{key.replace('_', '-')}", "kind": "fact", "text": text, "source_refs": [ref]})
    cover = {"id": "cover", "role": "cover", "book_ids": selected_ids, "blocks": cover_blocks}
    overview = {"id": "overview", "role": "overview", "book_ids": [], "blocks": overview_blocks}
    planned = [cover] + ([overview] if share_format == "annual" else []) + ([] if share_format == "single-image" else pages)
    job = {"schema_version": "share-3", "year": year, "source_mode": data["source_mode"], "source_sha256": file_digest(Path(input_path)),
           "coverage": {"collection_complete": complete, "verification_status": data["verification_status"], "scope": "selected-books", "annual_book_candidates": len(known)},
           "period": period, "books": books, "sources": sources,
           "pages": planned if books else [], "annual_summary": summary,
           "brief": {"platform": "", "format": share_format, "focus": "reading-takeaways"}, "canvas": None,
           "directions": [], "selected_direction": None,
           "art_brief": {"workflow": "material-led"}, "assets": [], "caption": caption, "approvals": {}, "status": "scope_draft", "runs": []}
    write_json(folder / "share-job.json", job)
    return job


def approve_scope(folder: Path, sample_test: bool = False, confirmation: dict | None = None) -> dict:
    job = load_job(folder)
    validate_job(job, folder)
    validate_scope(job)
    payload = scope_payload(job)
    job["approvals"]["scope"] = confirmation_record(job, "scope", digest(payload), confirmation, sample_test)
    job["approvals"]["scope"]["presented_scope"] = payload
    job["status"] = "awaiting_creation_plan"
    write_json(Path(folder) / "share-job.json", job)
    return job


def approve_content(folder: Path, sample_test: bool = False, confirmation: dict | None = None) -> dict:
    job = load_job(folder)
    validate_job(job, folder)
    if sample_test and job["source_mode"] != "sample":
        raise ValueError("技术测试确认不能用于真实数据。")
    require_scope(job)
    validate_creation(job)
    job["approvals"]["content"] = confirmation_record(job, "content", content_hash(job), confirmation, sample_test)
    job["status"] = "awaiting_visual_preview"
    write_json(Path(folder) / "share-job.json", job)
    return job


def require_content(job: dict) -> None:
    require_scope(job)
    validate_creation(job)
    require_confirmation(job, "content", content_hash(job))


def visual_version(job: dict, report: dict) -> str:
    ids = preview_ids(job)
    pages = {page["id"]: page for page in report["pages"]}
    if any(page_id not in pages for page_id in ids):
        raise ValueError("缺少封面、年度概览或代表书卡的实际样张。")
    return digest({"art_hash": report["art_hash"], "brief_hash": digest(job["art_brief"]),
                   "scope_hash": digest(scope_payload(job)), "selected_direction": job["selected_direction"],
                   "anchors": {page_id: pages[page_id]["fingerprint"] for page_id in ids}})


def status(folder: Path) -> dict:
    folder = Path(folder)
    job = load_job(folder)
    try:
        validate_job(job, folder)
        require_content(job)
        report = json.loads((folder / "validation-report.json").read_text("utf-8"))
        if report.get("content_hash") != content_hash(job) or report.get("source_sha256") != file_digest(folder / "deck.html"):
            raise ValueError("当前内容或 HTML 与图片版本不一致。")
        for image in report["images"]:
            if file_digest(folder / "images" / image["file"]) != image["sha256"]:
                raise ValueError("图片缺失或变化。")
        if report["stage"] != "final" or report["status"] != "pass":
            return {"status": "awaiting_visual_confirmation", "source_mode": job["source_mode"], "pages": len(job["pages"])}
        require_confirmation(job, "visual", visual_version(job, report))
        visual = job.get("approvals", {}).get("visual", {})
        fingerprints = {page["id"]: page["fingerprint"] for page in report["pages"]}
        if visual.get("art_hash") != report["art_hash"] or visual.get("brief_hash") != digest(job["art_brief"]) or any(fingerprints.get(key) != value for key, value in visual.get("anchors", {}).items()) or not visual.get("anchors"):
            raise ValueError("视觉确认已失效。")
        expected = {page["id"] for page in job["pages"]}
        if {image["id"] for image in report["images"]} != expected:
            raise ValueError("图片没有覆盖全部当前页面。")
        if job["source_mode"] == "live" and (not job["coverage"]["collection_complete"] or job["coverage"]["verification_status"] == "partial_unverified" or visual.get("actor") != "user"):
            raise ValueError("真实数据不完整或尚未由用户确认。")
        if (folder / "caption.md").read_text("utf-8") != job["caption"] + "\n":
            raise ValueError("发布文案与确认版本不一致。")
        return {"status": "ready_sample" if job["source_mode"] == "sample" else "ready", "source_mode": job["source_mode"], "pages": len(job["pages"])}
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        return {"status": "draft", "reason": str(exc), "source_mode": job["source_mode"], "pages": len(job["pages"])}


def approve_visual(folder: Path, sample_test: bool = False, confirmation: dict | None = None) -> dict:
    folder = Path(folder)
    job = load_job(folder)
    validate_job(job, folder)
    if sample_test and job["source_mode"] != "sample":
        raise ValueError("技术测试确认不能用于真实数据。")
    require_content(job)
    report = json.loads((folder / "validation-report.json").read_text("utf-8"))
    if report.get("stage") != "preview" or report.get("status") != "pass" or report.get("content_hash") != content_hash(job) or report.get("source_sha256") != file_digest(folder / "deck.html"):
        raise ValueError("先导出当前版本的封面、年度概览和代表书卡，再记录视觉确认。")
    if set(report["requested_ids"]) != set(preview_ids(job)):
        raise ValueError("预览没有覆盖当前任务要求的页面角色。")
    for image in report["images"]:
        if file_digest(folder / "images" / image["file"]) != image["sha256"]:
            raise ValueError("预览图片缺失或已变化。")
    anchors = {page["id"]: page["fingerprint"] for page in report["pages"] if page["id"] in report["requested_ids"]}
    job["approvals"]["visual"] = confirmation_record(job, "visual", visual_version(job, report), confirmation, sample_test)
    job["approvals"]["visual"].update(art_hash=report["art_hash"], brief_hash=digest(job["art_brief"]), anchors=anchors)
    job["status"] = "visual_approved"
    write_json(folder / "share-job.json", job)
    return job


def _safe_remove_staging(staging: Path, parent: Path, prefix: str) -> None:
    resolved = staging.resolve()
    if resolved.parent != parent.resolve() or not resolved.name.startswith(prefix):
        raise ValueError("临时目录不在预期位置，停止清理。")
    if resolved.exists():
        shutil.rmtree(resolved)


def export_share(folder: Path, stage: str, node: str | None = None, playwright_package: str | None = None, browser: str | None = None) -> dict:
    if stage not in ("preview", "final"):
        raise ValueError("导出阶段只能为preview或final。")
    folder = Path(folder).resolve()
    job = load_job(folder)
    validate_job(job, folder)
    require_content(job)
    if stage == "final":
        if job["source_mode"] == "live" and (not job["coverage"]["collection_complete"] or job["coverage"]["verification_status"] == "partial_unverified"):
            raise ValueError("真实采集不完整；可以预览，不能交付最终分享包。")
        visual = job.get("approvals", {}).get("visual", {})
        if not visual.get("anchors") or visual.get("brief_hash") != digest(job["art_brief"]):
            raise ValueError("先确认封面和代表内页的实际图片。")
        if job["source_mode"] == "live" and visual.get("actor") != "user":
            raise ValueError("真实数据需要用户的视觉确认。")
        previous = json.loads((folder / "validation-report.json").read_text("utf-8"))
        require_confirmation(job, "visual", visual_version(job, previous))
    executable = shutil.which(node or "node")
    if not executable:
        return {"status": "unavailable", "reason": "没有可用 Node；保留 HTML，不安装依赖，也不宣称 PNG 完成。"}
    prefix = f".{folder.name}.render-"
    # Normal workspace ACL inheritance matters on Windows: mkdtemp's private ACL
    # would travel with images when the directory is renamed into the share package.
    staging = folder.parent / f"{prefix}{uuid.uuid4().hex}"
    staging.mkdir()
    command = [executable, str(SCRIPT_DIR / "export_deck.cjs"), "--folder", str(folder), "--output", str(staging), "--stage", stage]
    if stage == "preview":
        command += ["--page-ids", json.dumps(preview_ids(job))]
    if playwright_package:
        command += ["--playwright-package", playwright_package]
    if browser:
        command += ["--browser", browser]
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        try:
            stdout, stderr = process.communicate(timeout=120)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                # Only our known renderer process and its browser children, never other sessions.
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=10)
            else:
                process.kill()
            process.communicate(timeout=10)
            raise
        report_path = staging / "render-report.json"
        if not report_path.exists():
            attempt = {"status": "failed", "reason": (stderr or stdout).strip()[:1000] or "渲染器未返回报告。"}
        else:
            attempt = json.loads(report_path.read_text("utf-8"))
        if process.returncode or attempt.get("status") != "pass":
            write_json(folder / "last-attempt.json", attempt)
            return attempt
        attempt.update(content_hash=content_hash(job), source_sha256=file_digest(folder / "deck.html"), source_mode=job["source_mode"],
                       verification_status="sample_verified" if job["source_mode"] == "sample" else ("live_verified" if stage == "final" else "implemented_unverified"))
        # Keep one recoverable snapshot only when the actual PNG set changed.
        previous_images = folder / "images"
        changed = not previous_images.is_dir() or set(p.name for p in previous_images.glob("*.png")) != {image["file"] for image in attempt["images"]} or any(not (previous_images / image["file"]).exists() or file_digest(previous_images / image["file"]) != image["sha256"] for image in attempt["images"])
        backup = None
        if changed:
            if previous_images.exists():
                backup = folder / "revisions" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
                backup.mkdir(parents=True)
                os.replace(previous_images, backup / "images")
                if (folder / "validation-report.json").exists():
                    shutil.copy2(folder / "validation-report.json", backup / "validation-report.json")
            try:
                os.replace(staging / "images", previous_images)
            except Exception:
                if backup:
                    os.replace(backup / "images", previous_images)
                raise
        os.replace(staging / "overview.png", folder / "overview.png")
        (folder / "caption.md").write_text(job["caption"] + "\n", "utf-8")
        write_json(folder / "validation-report.json", attempt)
        job["status"] = "preview_ready" if stage == "preview" else ("ready_sample" if job["source_mode"] == "sample" else "ready")
        job["runs"].append({"stage": stage, "at": datetime.now(timezone.utc).isoformat(), "rendered": attempt["rendered"], "reused": attempt["reused"], "elapsed_seconds": attempt["elapsed_seconds"]})
        write_json(folder / "share-job.json", job)
        (folder / "last-attempt.json").unlink(missing_ok=True)
        return {"status": "pass", "stage": stage, "rendered": attempt["rendered"], "reused": attempt["reused"], "pages": len(attempt["images"]), "elapsed_seconds": attempt["elapsed_seconds"]}
    except subprocess.TimeoutExpired:
        attempt = {"status": "failed", "reason": "渲染超过 120 秒，保留此前有效图片；检查失败项后再重试。"}
        write_json(folder / "last-attempt.json", attempt)
        return attempt
    finally:
        _safe_remove_staging(staging, folder.parent, prefix)


def main() -> int:
    parser = argparse.ArgumentParser(description="阅读分享：范围确认、内容与方向确认、真实样张确认、整组导出。助手维护文件。")
    sub = parser.add_subparsers(dest="command", required=True)
    prep = sub.add_parser("prepare")
    prep.add_argument("--year", type=int, required=True)
    prep.add_argument("--input", type=Path, required=True)
    prep.add_argument("--output", type=Path, required=True)
    prep.add_argument("--books", nargs="*")
    prep.add_argument("--format", choices=sorted(FORMATS), default="annual")
    for name in ("status", "configure", "approve-scope", "approve-content", "approve-visual", "preview", "finalize"):
        cmd = sub.add_parser(name)
        cmd.add_argument("folder", type=Path)
        if name.startswith("approve-"):
            cmd.add_argument("--sample-test", action="store_true", help="仅样例技术测试；不冒称用户确认。真实任务只在用户已确认时记录。")
            cmd.add_argument("--confirmation-file", type=Path, help="助手记录的当前回复与会话位置JSON，不让用户编辑。")
        if name == "configure":
            cmd.add_argument("--ratio", required=True, choices=["1:1", "3:4", "4:5", "custom"])
            cmd.add_argument("--width", type=int)
            cmd.add_argument("--height", type=int)
            cmd.add_argument("--platform", required=True)
        if name in ("preview", "finalize"):
            cmd.add_argument("--node")
            cmd.add_argument("--playwright-package")
            cmd.add_argument("--browser")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            job = prepare_share(args.year, args.input, args.output, args.books, args.format)
            result = {"status": "scope_draft" if job["books"] else "empty", "books": len(job["books"]), "pages": len(job["pages"]), "job": str(args.output / "share-job.json")}
        elif args.command == "configure":
            job = load_job(args.folder)
            if job.get("schema_version") != "share-3":
                raise ValueError("旧任务须先重新确认简报，保留旧文件，不直接覆盖历史。")
            job["canvas"] = make_canvas(args.ratio, args.width, args.height)
            job["brief"]["platform"] = args.platform
            job["status"] = "scope_draft"
            write_json(args.folder / "share-job.json", job)
            result = {"status": job["status"], "canvas": job["canvas"]}
        elif args.command == "status":
            result = status(args.folder)
        elif args.command.startswith("approve-"):
            if args.sample_test and args.confirmation_file:
                raise ValueError("样例技术测试不能同时记录用户确认。")
            confirmation = json.loads(args.confirmation_file.read_text("utf-8")) if args.confirmation_file else None
            approve = {"approve-scope": approve_scope, "approve-content": approve_content, "approve-visual": approve_visual}[args.command]
            result = {"status": approve(args.folder, args.sample_test, confirmation)["status"]}
        else:
            result = export_share(args.folder, "preview" if args.command == "preview" else "final", args.node, args.playwright_package, args.browser)
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["status"] not in ("failed", "unavailable", "draft", "empty") else 2
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
