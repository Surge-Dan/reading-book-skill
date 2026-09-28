from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from render_yearbook import render_atlas, render_cards
from validate_yearbook import validate_output
from yearbook_core import build_profiles, choose_yearly_thesis, derive_yearly_topics, normalize_yearbook, score_books


def _slug(book_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", book_id).strip("-") or "book"


def _profile_markdown(profile: dict, book: dict) -> str:
    lines = [f"# {profile['title']}", "", f"作者：{profile['author']}", f"证据等级：{profile['evidence_level']}", "", "## 这本书讲了啥", "", profile["about"], "", "## 我的思考", "", profile["reflection"], "", "## 证据索引", ""]
    if profile["citations"]:
        lines.extend(f"- `{item['source_id']}` · {item['type']} · {item['text']}" for item in profile["citations"])
    else:
        lines.append("- 暂无可引用证据。")
    lines.extend(["", "## 年度位置", "", f"月份：{', '.join(map(str, book.get('months', []))) or '未记录'}", f"主题：{'、'.join(book.get('topics', [])) or '未形成'}", f"代表性得分：{book.get('score', 0)}（{book.get('score_reason', '无')}）", ""])
    return "\n".join(lines)


def _selection_markdown(data: dict) -> str:
    lines = [f"# {data['year']} 年精选确认", "", f"> 数据模式：`{data['source_mode']}`；验证状态：`{data['verification_status']}`。", "", "## 前 20% 推荐", ""]
    selected = [book for book in data["books"] if book["selected"]]
    lines.extend(f"- [ ] **{book['title']}**｜{book['score']} 分｜{book['score_reason']}" for book in selected)
    lines.extend(["", "## 年度之书候选", ""])
    lines.extend(f"- [ ] **{book['title']}**｜{book['score']} 分｜{book['evidence_reason']}" for book in data["books"] if book["book_of_year_candidate"])
    lines.extend(["", "## 全年书目", ""])
    lines.extend(f"- {book['title']}｜{book['author']}｜{book['evidence_level']}｜进度 {book['progress']}%" for book in data["books"])
    lines.extend(["", "确认方法：勾选保留项；如需替换，直接在本文件写明书名。最终生成前应由用户确认。", ""])
    return "\n".join(lines)


def generate_yearbook(year: int, input_path: Path, output_dir: Path, export_png: bool = False) -> dict:
    raw = json.loads(Path(input_path).read_text("utf-8"))
    data = normalize_yearbook(raw, int(year))
    data["books"] = score_books(data["books"])
    data["summary"]["book_count"] = len(data["books"])
    data["topics"] = derive_yearly_topics(data["books"])
    data["thesis"] = choose_yearly_thesis(int(year), data["topics"], data["books"])
    data["profiles"] = build_profiles(data["books"])
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "yearbook-data.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
    (output_dir / "selection-preview.md").write_text(_selection_markdown(data), "utf-8")
    profiles = {item["book_id"]: item for item in data["profiles"]}
    for book in data["books"]:
        folder = output_dir / "books" / _slug(book["book_id"])
        folder.mkdir(parents=True, exist_ok=True)
        profile = profiles[book["book_id"]]
        (folder / "profile.md").write_text(_profile_markdown(profile, book), "utf-8")
        evidence = {"book_id": book["book_id"], "evidence_level": book["evidence_level"], "reason": book["evidence_reason"], "citations": profile["citations"]}
        (folder / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), "utf-8")
    render_atlas(data, output_dir / "atlas.html")
    html_cards = render_cards(data, output_dir / "cards-html")
    export_result = {"status": "skipped", "reason": "未请求 PNG 导出"}
    if export_png:
        from export_cards import export_cards

        export_result = export_cards(output_dir / "cards-html", output_dir / "cards")
    report = validate_output(output_dir, expected_book_count=len(data["books"]))
    report["png_export"] = export_result
    (output_dir / "validation-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), "utf-8")
    return {"data": data, "output": str(output_dir), "card_html_count": len(html_cards), "validation": report}


def main() -> int:
    parser = argparse.ArgumentParser(description="生成一套可追溯的微信读书年度阅读档案。")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--input", type=Path, required=True, help="采集后的原始 JSON；可使用 assets/sample-data.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--export-png", action="store_true")
    args = parser.parse_args()
    result = generate_yearbook(args.year, args.input, args.output, args.export_png)
    print(json.dumps({"status": "ok", "output": result["output"], "validation": result["validation"]["status"]}, ensure_ascii=False))
    return 0 if result["validation"]["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
