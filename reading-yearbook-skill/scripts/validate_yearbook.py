from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


SECRET_PATTERNS = (re.compile(r"wrk-[A-Za-z0-9_-]{8,}"), re.compile(r"WEREAD_API_KEY\s*[:=]\s*[^\s<]+"))


def validate_output(output_dir: Path, expected_book_count: int | None = None) -> dict:
    output_dir = Path(output_dir)
    checks = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "status": "pass" if passed else "fail", "detail": detail})

    required = [output_dir / "atlas.html", output_dir / "yearbook-data.json", output_dir / "selection-preview.md"]
    missing = [path.name for path in required if not path.exists()]
    add("required_files", not missing, "齐全" if not missing else f"缺少：{', '.join(missing)}")
    profile_count = len(list((output_dir / "books").glob("*/profile.md"))) if (output_dir / "books").exists() else 0
    add("book_profiles", expected_book_count is None or profile_count == expected_book_count, f"检测到 {profile_count} 个档案")
    card_count = len(list((output_dir / "cards-html").glob("*.html"))) if (output_dir / "cards-html").exists() else 0
    add("editable_cards", card_count >= 1, f"检测到 {card_count} 张 HTML 卡片")
    leaks = []
    for path in output_dir.rglob("*"):
        if path.is_file() and path.name != "validation-report.json":
            text = path.read_text("utf-8", errors="ignore")
            if any(pattern.search(text) for pattern in SECRET_PATTERNS):
                leaks.append(str(path.relative_to(output_dir)))
    add("secret_scan", not leaks, "未发现 Key" if not leaks else f"疑似泄露：{', '.join(leaks)}")
    try:
        data = json.loads((output_dir / "yearbook-data.json").read_text("utf-8"))
        missing_sources = [citation for profile in data.get("profiles", []) for citation in profile.get("citations", []) if not citation.get("source_id")]
        add("citation_sources", not missing_sources, "引用均有 source_id" if not missing_sources else "存在无来源引用")
    except (OSError, json.JSONDecodeError) as exc:
        add("citation_sources", False, f"无法读取数据：{exc}")
    status = "pass" if all(item["status"] == "pass" for item in checks) else "fail"
    return {"status": status, "checks": checks}


def main() -> int:
    parser = argparse.ArgumentParser(description="检查年报数据、隐私、引用和文件完整性。")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = validate_output(args.output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
