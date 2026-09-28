from __future__ import annotations

import argparse
import json
import re
import zipfile
from collections import Counter
from html import unescape
from pathlib import Path


HEADING_RE = re.compile(r"^(?:第[一二三四五六七八九十百0-9]+[章节部篇]|[0-9]+[.、])\s*(.+)$")
METHOD_MARKERS = ("方法", "步骤", "原则", "应该", "可以", "先", "再", "不要", "避免")
BOUNDARY_MARKERS = ("不适用", "不要", "避免", "停止", "风险", "边界", "除非", "不能")


def _clean_text(text: str) -> str:
    text = unescape(re.sub(r"<[^>]+>", " ", text))
    text = re.sub(r"[ \t\r]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def load_legal_text(path: Path) -> tuple[str, str]:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return path.read_text("utf-8"), "verified"
    if suffix == ".epub":
        chunks = []
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                if name.lower().endswith((".xhtml", ".html", ".htm")):
                    chunks.append(_clean_text(archive.read(name).decode("utf-8", errors="ignore")))
        return "\n\n".join(chunks), "verified" if chunks else "failed"
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("PDF 解析需要安装 pypdf；当前环境未验证 PDF 支持。") from exc
        reader = PdfReader(str(path))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages), "verified"
    raise ValueError("仅支持 PDF、EPUB、TXT、MD。")


def distill_text(text: str, title: str, source_name: str, full_text_confirmed: bool = False) -> dict:
    clean = _clean_text(text)
    if len(clean) < 40:
        raise ValueError("文本过短，无法形成可验证的深度蒸馏。")
    paragraphs = [{"source_id": f"p-{index:04d}", "text": line.strip()} for index, line in enumerate(clean.splitlines(), start=1) if line.strip()]
    sections = []
    current = {"heading": "开篇", "content": [], "source_ids": []}
    for paragraph in paragraphs:
        line = paragraph["text"]
        if not line:
            continue
        match = HEADING_RE.match(line)
        if match:
            if current["content"]:
                sections.append({"heading": current["heading"], "content": " ".join(current["content"]), "source_ids": current["source_ids"]})
            current = {"heading": line[:80], "content": [], "source_ids": [paragraph["source_id"]]}
        else:
            current["content"].append(line)
            current["source_ids"].append(paragraph["source_id"])
    if current["content"]:
        sections.append({"heading": current["heading"], "content": " ".join(current["content"]), "source_ids": current["source_ids"]})

    sentence_rows = []
    for paragraph in paragraphs:
        for part in re.split(r"[。！？!?；;]\s*", paragraph["text"]):
            sentence = part.strip()
            if len(sentence) >= 8:
                sentence_rows.append({"text": sentence, "source_id": paragraph["source_id"]})
    methods = [row for row in sentence_rows if any(marker in row["text"] for marker in METHOD_MARKERS)][:12]
    boundaries = [row for row in sentence_rows if any(marker in row["text"] for marker in BOUNDARY_MARKERS)][:8]
    words = re.findall(r"[\u4e00-\u9fff]{2,6}", clean)
    terms = [word for word, _ in Counter(words).most_common(12)]
    skill_eligible = full_text_confirmed and len(methods) >= 2 and len(sections) >= 2 and bool(boundaries)
    return {
        "title": title,
        "source_name": source_name,
        "evidence_level": "E3" if full_text_confirmed else "E2",
        "full_text_confirmed": full_text_confirmed,
        "character_count": len(clean),
        "sections": sections,
        "candidate_methods": methods,
        "boundaries": boundaries,
        "candidate_terms": terms,
        "test_questions": [
            "正向：在什么具体场景下，这个方法应改变下一步行动？",
            "反向：缺少哪些输入时，这个方法不能可靠使用？",
            "边界：什么结果出现时应该停止或改用别的方法？",
        ],
        "skill_eligible": skill_eligible,
        "boundary": "E3 只表示用户确认提供了完整合法文本；候选方法仍需逐项核对来源、步骤、验证方式和不适用场景。",
    }


def _write_outputs(result: dict, output_dir: Path, create_skill: bool) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "analysis.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
    lines = [f"# 《{result['title']}》深度蒸馏", "", f"来源：`{result['source_name']}`", "", "## 结构"]
    for section in result["sections"]:
        lines.extend(["", f"### {section['heading']}", "", section["content"][:600]])
    lines.extend(["", "## 候选方法"])
    lines.extend(f"- `{item['source_id']}` {item['text']}" for item in result["candidate_methods"])
    if not result["candidate_methods"]:
        lines.append("- 未识别到足够明确的方法句，暂不生成子 Skill。")
    lines.extend(["", "## 不适用场景与停止条件"])
    lines.extend(f"- `{item['source_id']}` {item['text']}" for item in result["boundaries"] or [{"source_id": "missing", "text": "未识别到边界证据，不生成子 Skill。"}])
    lines.extend(["", "## 测试问题"])
    lines.extend(f"- {item}" for item in result["test_questions"])
    lines.extend(["", "## 边界", "", result["boundary"]])
    (output_dir / "profile.md").write_text("\n".join(lines) + "\n", "utf-8")
    if create_skill and result["skill_eligible"]:
        skill_dir = output_dir / "generated-skill"
        skill_dir.mkdir(exist_ok=True)
        method_lines = "\n".join(f"- [{item['source_id']}] {item['text']}" for item in result["candidate_methods"])
        skill = f"""---
name: {re.sub(r'[^a-z0-9-]+', '-', result['source_name'].lower()).strip('-') or 'book-method'}
description: Apply the verified methods extracted from {result['title']} when the user explicitly asks to use this book's framework.
---

# {result['title']}

Use only the methods supported by the user-provided source IDs. Distinguish source claims, user interpretation, and new inference.

## Candidate methods requiring human review

{method_lines}

Before relying on a method, state its applicable situation, steps, expected evidence, and when it should not be used.
"""
        (skill_dir / "SKILL.md").write_text(skill, "utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="从用户合法提供的全文生成 E3 深度蒸馏。")
    parser.add_argument("source", type=Path)
    parser.add_argument("--title", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--create-skill", action="store_true")
    parser.add_argument("--full-text-confirmed", action="store_true", help="确认输入是用户有权处理的完整文本")
    args = parser.parse_args()
    if args.create_skill and not args.full_text_confirmed:
        parser.error("--create-skill 必须同时提供 --full-text-confirmed")
    text, status = load_legal_text(args.source)
    result = distill_text(text, args.title, args.source.name, args.full_text_confirmed)
    result["parser_status"] = status
    _write_outputs(result, args.output, args.create_skill)
    print(json.dumps({"status": "ok", "output": str(args.output), "skill_eligible": result["skill_eligible"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
