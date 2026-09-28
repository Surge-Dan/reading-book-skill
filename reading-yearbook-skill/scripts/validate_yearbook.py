from __future__ import annotations

import argparse
import json
import re
import struct
from pathlib import Path


SECRET_PATTERNS = (re.compile(r"wrk-[A-Za-z0-9_-]{8,}"), re.compile(r"WEREAD_API_KEY\s*[:=]\s*[^\s<]+"))
VERIFICATION_STATES = {"sample_verified", "live_verified", "partial_unverified", "implemented_unverified"}


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
        required_keys = {"schema_version", "year", "source_mode", "verification_status", "summary", "books", "topics", "profiles", "publication_status"}
        absent = sorted(required_keys - set(data))
        add("data_contract", not absent and data.get("verification_status") in VERIFICATION_STATES and data.get("publication_status") == "final", "schema 与状态有效" if not absent else f"缺少字段：{', '.join(absent)}")
    except (OSError, json.JSONDecodeError) as exc:
        add("data_contract", False, f"无法读取数据：{exc}")

    expected_book_count = len(data.get("books", [])) if data else -1
    profile_count = len(list((output_dir / "books").glob("*/profile.md"))) if (output_dir / "books").exists() else 0
    add("book_profiles", expected_book_count >= 0 and profile_count == expected_book_count, f"预期 {expected_book_count}，检测到 {profile_count}")
    html_cards = sorted((output_dir / "cards-html").glob("*.html")) if (output_dir / "cards-html").exists() else []
    add("editable_cards", len(html_cards) >= 5, f"检测到 {len(html_cards)} 张 HTML 卡片")
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
        add("png_export", export_ok and count_ok and not bad_sizes, f"HTML {len(html_cards)} / PNG {len(png_files)}；尺寸异常 {len(bad_sizes)}")
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
