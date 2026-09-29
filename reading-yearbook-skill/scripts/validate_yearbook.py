from __future__ import annotations

import argparse
import json
import re
import struct
from pathlib import Path


SECRET_PATTERNS = (re.compile(r"wrk-[A-Za-z0-9_-]{8,}"), re.compile(r"WEREAD_API_KEY\s*[:=]\s*[^\s<]+"))
VERIFICATION_STATES = {"sample_verified", "live_verified", "partial_unverified", "implemented_unverified"}
REQUIRED_CARD_TYPES = {"cover", "reading-rhythm", "recurring-topics", "book-of-year", "final-question"}


def _png_size(path: Path) -> tuple[int, int] | None:
    try:
        with path.open("rb") as handle:
            header = handle.read(24)
        if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
            return None
        return struct.unpack(">II", header[16:24])
    except OSError:
        return None


def validate_output(output_dir: Path, require_png: bool = False, png_result: dict | None = None) -> dict:
    output_dir = Path(output_dir)
    checks = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "status": "pass" if passed else "fail", "detail": detail})

    required = [output_dir / "atlas.html", output_dir / "yearbook-data.json", output_dir / "selection-preview.md", output_dir / "selection.json", output_dir / "cards-manifest.json"]
    missing = [path.name for path in required if not path.exists()]
    add("required_files", not missing, "齐全" if not missing else f"缺少：{', '.join(missing)}")
    data = None
    try:
        data = json.loads((output_dir / "yearbook-data.json").read_text("utf-8"))
        schema_errors = []
        required_keys = {"schema_version", "year", "source_mode", "verification_status", "summary", "books", "topics", "profiles", "thesis", "selection", "publication_status"}
        absent = sorted(required_keys - set(data)) if isinstance(data, dict) else sorted(required_keys)
        if absent:
            schema_errors.append(f"缺少字段：{', '.join(absent)}")
        if not isinstance(data, dict):
            schema_errors.append("顶层必须是对象")
            data = {}
        if not isinstance(data.get("year"), int) or isinstance(data.get("year"), bool):
            schema_errors.append("year 必须是整数")
        if data.get("publication_status") != "final":
            schema_errors.append("publication_status 必须为 final")
        source_mode = data.get("source_mode")
        verification = data.get("verification_status")
        if source_mode not in {"sample", "live"}:
            schema_errors.append("source_mode 仅允许 sample 或 live")
        if verification not in VERIFICATION_STATES:
            schema_errors.append("verification_status 无效")
        if source_mode == "sample" and verification != "sample_verified":
            schema_errors.append("sample 数据必须标记为 sample_verified")
        if source_mode == "live" and verification != "live_verified":
            schema_errors.append("live 最终产物必须通过验证并标记为 live_verified")

        summary = data.get("summary")
        if not isinstance(summary, dict):
            schema_errors.append("summary 必须是对象")
            summary = {}
        summary_keys = {"book_count", "total_read_seconds", "read_days", "note_count", "monthly_read_seconds"}
        missing_summary = sorted(summary_keys - set(summary))
        if missing_summary:
            schema_errors.append(f"summary 缺少：{', '.join(missing_summary)}")
        monthly = summary.get("monthly_read_seconds")
        if not isinstance(monthly, list) or len(monthly) != 12 or any(not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0 for value in (monthly or [])):
            schema_errors.append("monthly_read_seconds 必须是 12 个非负数")

        books = data.get("books")
        if not isinstance(books, list) or not books:
            schema_errors.append("books 必须是非空数组")
            books = []
        book_keys = {"book_id", "title", "author", "evidence_level", "annual_reading_seconds", "months", "highlights", "thoughts", "score", "selected", "book_of_year_candidate", "book_of_year"}
        book_ids = []
        for index, book in enumerate(books):
            if not isinstance(book, dict):
                schema_errors.append(f"books[{index}] 必须是对象")
                continue
            missing_book = sorted(book_keys - set(book))
            if missing_book:
                schema_errors.append(f"books[{index}] 缺少：{', '.join(missing_book)}")
            book_id = book.get("book_id")
            if not isinstance(book_id, str) or not book_id.strip():
                schema_errors.append(f"books[{index}].book_id 无效")
            else:
                book_ids.append(book_id)
            if book.get("evidence_level") not in {"E0", "E1", "E2", "E3"}:
                schema_errors.append(f"books[{index}].evidence_level 无效")
            for numeric_key in ("annual_reading_seconds", "score"):
                value = book.get(numeric_key)
                if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
                    schema_errors.append(f"books[{index}].{numeric_key} 必须是非负数")
            if not isinstance(book.get("selected"), bool) or not isinstance(book.get("book_of_year_candidate"), bool) or not isinstance(book.get("book_of_year"), bool):
                schema_errors.append(f"books[{index}] 的选择标记必须是布尔值")
            if not isinstance(book.get("months"), list) or any(not isinstance(month, int) or isinstance(month, bool) or month < 1 or month > 12 for month in book.get("months", [])):
                schema_errors.append(f"books[{index}].months 无效")
            if not isinstance(book.get("highlights"), list) or not isinstance(book.get("thoughts"), list):
                schema_errors.append(f"books[{index}] 的年度批注必须是数组")
        if len(book_ids) != len(set(book_ids)):
            schema_errors.append("book_id 必须唯一")
        if summary.get("book_count") != len(books):
            schema_errors.append("summary.book_count 与 books 数量不一致")

        profiles = data.get("profiles")
        if not isinstance(profiles, list):
            schema_errors.append("profiles 必须是数组")
            profiles = []
        profile_ids = [profile.get("book_id") for profile in profiles if isinstance(profile, dict)]
        if set(profile_ids) != set(book_ids) or len(profile_ids) != len(book_ids):
            schema_errors.append("profiles 必须与 books 一一对应")

        selection = data.get("selection")
        if not isinstance(selection, dict):
            schema_errors.append("selection 必须是对象")
            selection = {}
        selected_ids = selection.get("selected_book_ids")
        book_of_year_id = selection.get("book_of_year_id")
        if not isinstance(selected_ids, list) or not selected_ids or any(item not in book_ids for item in selected_ids):
            schema_errors.append("selected_book_ids 必须是已知书籍的非空数组")
            selected_ids = []
        elif len(selected_ids) != len(set(selected_ids)):
            schema_errors.append("selected_book_ids 不能重复")
        if not isinstance(book_of_year_id, str) or book_of_year_id not in selected_ids:
            schema_errors.append("book_of_year_id 必须属于 selected_book_ids")
        if not isinstance(selection.get("confirmed_at"), str) or not selection.get("confirmed_at", "").strip():
            schema_errors.append("selection.confirmed_at 不能为空")
        if not isinstance(data.get("thesis"), str) or not data.get("thesis", "").strip():
            schema_errors.append("thesis 不能为空")
        selected_from_books = {book.get("book_id") for book in books if isinstance(book, dict) and book.get("selected") is True}
        year_books = [book.get("book_id") for book in books if isinstance(book, dict) and book.get("book_of_year") is True]
        if set(selected_ids) != selected_from_books:
            schema_errors.append("selection 与 books.selected 不一致")
        if year_books != [book_of_year_id]:
            schema_errors.append("selection 与 books.book_of_year 不一致")
        add("data_contract", not schema_errors, "schema、状态与选择关系有效" if not schema_errors else "；".join(schema_errors[:8]))
    except (OSError, json.JSONDecodeError) as exc:
        add("data_contract", False, f"无法读取数据：{exc}")

    expected_book_count = len(data.get("books", [])) if data else -1
    profile_count = len(list((output_dir / "books").glob("*/profile.md"))) if (output_dir / "books").exists() else 0
    add("book_profiles", expected_book_count >= 0 and profile_count == expected_book_count, f"预期 {expected_book_count}，检测到 {profile_count}")
    html_cards = sorted((output_dir / "cards-html").glob("*.html")) if (output_dir / "cards-html").exists() else []
    add("editable_cards", len(html_cards) >= 5, f"检测到 {len(html_cards)} 张 HTML 卡片")
    try:
        selection_file = json.loads((output_dir / "selection.json").read_text("utf-8"))
        final_selection = (data or {}).get("selection", {})
        selection_errors = []
        if not isinstance(selection_file, dict):
            selection_errors.append("selection.json 必须是对象")
            selection_file = {}
        if selection_file.get("status") != "confirmed":
            selection_errors.append("selection.json 尚未确认")
        if selection_file.get("year") != (data or {}).get("year"):
            selection_errors.append("selection.json 年份不一致")
        for key in ("selected_book_ids", "book_of_year_id", "confirmed_at"):
            if selection_file.get(key) != final_selection.get(key):
                selection_errors.append(f"selection.json 的 {key} 与最终数据不一致")
        add("selection_confirmation", not selection_errors, "确认文件与最终数据一致" if not selection_errors else "；".join(selection_errors))
    except (OSError, json.JSONDecodeError) as exc:
        add("selection_confirmation", False, f"无法读取 selection.json：{exc}")
    try:
        manifest = json.loads((output_dir / "cards-manifest.json").read_text("utf-8"))
        manifest_errors = []
        if not isinstance(manifest, list):
            manifest_errors.append("manifest 必须是数组")
            manifest = []
        entries = [item for item in manifest if isinstance(item, dict)]
        if len(entries) != len(manifest):
            manifest_errors.append("manifest 条目必须是对象")
        files = [item.get("file") for item in entries]
        type_values = [item.get("type") for item in entries]
        types = {value for value in type_values if isinstance(value, str)}
        actual_files = {path.name for path in html_cards}
        valid_file_fields = all(isinstance(name, str) and name.endswith(".html") for name in files)
        if not valid_file_fields:
            manifest_errors.append("manifest file 字段无效")
        if valid_file_fields and len(files) != len(set(files)):
            manifest_errors.append("manifest file 不能重复")
        if not valid_file_fields or set(files) != actual_files:
            manifest_errors.append("manifest 与 cards-html 文件不一致")
        missing_types = sorted(REQUIRED_CARD_TYPES - types)
        if missing_types:
            manifest_errors.append(f"缺少卡片类型：{', '.join(missing_types)}")
        known_ids = {book.get("book_id") for book in (data or {}).get("books", []) if isinstance(book, dict)}
        if any(item.get("type") in {"book-of-year", "selected-book"} and item.get("book_id") not in known_ids for item in entries):
            manifest_errors.append("书籍卡片引用了未知 book_id")
        final_selection = (data or {}).get("selection", {})
        selected_ids = set(final_selection.get("selected_book_ids", []))
        book_of_year_id = final_selection.get("book_of_year_id")
        year_cards = [item for item in entries if item.get("type") == "book-of-year"]
        if len(year_cards) != 1 or year_cards[0].get("book_id") != book_of_year_id:
            manifest_errors.append("年度之书卡必须唯一并匹配用户选择")
        selected_cards = [item for item in entries if item.get("type") == "selected-book"]
        selected_card_ids = [item.get("book_id") for item in selected_cards]
        if len(selected_card_ids) != len(set(selected_card_ids)) or set(selected_card_ids) != selected_ids - {book_of_year_id}:
            manifest_errors.append("精选单书卡必须与用户选择一一对应")
        add("cards_manifest", not manifest_errors, "manifest 与卡片文件及类型一致" if not manifest_errors else "；".join(manifest_errors))
    except (OSError, json.JSONDecodeError) as exc:
        add("cards_manifest", False, f"无法读取 manifest：{exc}")
    html_errors = [path.name for path in [output_dir / "atlas.html", *html_cards] if path.exists() and "<!doctype html>" not in path.read_text("utf-8", errors="ignore").lower()]
    add("html_documents", not html_errors, "HTML 文档可识别" if not html_errors else f"格式异常：{', '.join(html_errors)}")

    leaks = []
    for path in output_dir.rglob("*"):
        if path.is_file() and path.name != "validation-report.json":
            text = path.read_text("utf-8", errors="ignore")
            if any(pattern.search(text) for pattern in SECRET_PATTERNS):
                leaks.append(str(path.relative_to(output_dir)))
    add("secret_scan", not leaks, "未发现 Key" if not leaks else f"疑似泄露：{', '.join(leaks)}")
    missing_sources = [citation for profile in (data or {}).get("profiles", []) for citation in profile.get("citations", []) if not citation.get("source_id")]
    add("citation_sources", not missing_sources, "引用均有 source_id" if not missing_sources else "存在无来源引用")

    if require_png:
        png_files = sorted((output_dir / "cards").glob("*.png")) if (output_dir / "cards").exists() else []
        bad_sizes = [path.name for path in png_files if _png_size(path) != (900, 1200)]
        export_ok = bool(png_result and png_result.get("status") == "pass")
        count_ok = len(png_files) == len(html_cards)
        stem_match = {path.stem for path in png_files} == {path.stem for path in html_cards}
        add("png_export", export_ok and count_ok and stem_match and not bad_sizes, f"HTML {len(html_cards)} / PNG {len(png_files)}；文件映射 {'一致' if stem_match else '不一致'}；尺寸异常 {len(bad_sizes)}")
    else:
        add("png_export", True, "本次未要求 PNG")

    status = "pass" if all(item["status"] == "pass" for item in checks) else "fail"
    return {"status": status, "checks": checks}


def main() -> int:
    parser = argparse.ArgumentParser(description="检查年报数据、隐私、引用、HTML 和 PNG 完整性。")
    parser.add_argument("output", type=Path)
    parser.add_argument("--require-png", action="store_true")
    args = parser.parse_args()
    report = validate_output(args.output, require_png=args.require_png, png_result={"status": "pass"} if args.require_png else None)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
