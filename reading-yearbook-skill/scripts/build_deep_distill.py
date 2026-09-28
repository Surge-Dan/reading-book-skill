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


def distill_text(text: str, title: str, source_name: str) -> dict:
    clean = _clean_text(text)
    if len(clean) < 40:
        raise ValueError("文本过短，无法形成可验证的深度蒸馏。")
    sections = []
    current = {"heading": "开篇", "content": []}
    for raw_line in clean.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = HEADING_RE.match(line)
        if match:
            if current["content"]:
                sections.append({"heading": current["heading"], "content": " ".join(current["content"])})
            current = {"heading": line[:80], "content": []}
        else:
            current["content"].append(line)
    if current["content"]:
        sections.append({"heading": current["heading"], "content": " ".join(current["content"])})

    sentences = [part.strip() for part in re.split(r"[。！？!?；;]\s*", clean) if len(part.strip()) >= 8]
    methods = [sentence for sentence in sentences if any(marker in sentence for marker in METHOD_MARKERS)][:12]
    words = re.findall(r"[\u4e00-\u9fff]{2,6}", clean)
    terms = [word for word, _ in Counter(words).most_common(12)]
    return {
        "title": title,
        "source_name": source_name,
        "evidence_level": "E3",
        "character_count": len(clean),
        "sections": sections,
        "candidate_methods": methods,
        "candidate_terms": terms,
        "skill_eligible": len(methods) >= 2 and len(sections) >= 2,
        "boundary": "该结果来自用户提供文本；生成子 Skill 前仍需人工核对方法、反例和不适用场景。",
    }


def _write_outputs(result: dict, output_dir: Path, create_skill: bool) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "analysis.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
    lines = [f"# 《{result['title']}》深度蒸馏", "", f"来源：`{result['source_name']}`", "", "## 结构"]
    for section in result["sections"]:
        lines.extend(["", f"### {section['heading']}", "", section["content"][:600]])
    lines.extend(["", "## 候选方法"])
    lines.extend(f"- {item}" for item in result["candidate_methods"] or ["未识别到足够明确的方法句，暂不生成子 Skill。"])
    lines.extend(["", "## 边界", "", result["boundary"]])
    (output_dir / "profile.md").write_text("\n".join(lines) + "\n", "utf-8")
    if create_skill and result["skill_eligible"]:
        skill_dir = output_dir / "generated-skill"
        skill_dir.mkdir(exist_ok=True)
        method_lines = "\n".join(f"- {item}" for item in result["candidate_methods"])
        skill = f"""---
name: {re.sub(r'[^a-z0-9-]+', '-', result['source_name'].lower()).strip('-') or 'book-method'}
description: Apply the verified methods extracted from {result['title']} when the user explicitly asks to use this book's framework.
---

# {result['title']}

Use only the methods supported by the user-provided source. Distinguish source claims, user interpretation, and new inference.

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
    args = parser.parse_args()
    text, status = load_legal_text(args.source)
    result = distill_text(text, args.title, args.source.name)
    result["parser_status"] = status
    _write_outputs(result, args.output, args.create_skill)
    print(json.dumps({"status": "ok", "output": str(args.output), "skill_eligible": result["skill_eligible"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
