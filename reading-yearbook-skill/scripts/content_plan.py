"""Evidence-bound storyboards and representative previews, independent of art style."""
from __future__ import annotations


def validate_storyboards(job: dict) -> None:
    for page in job["pages"]:
        plan = page.get("storyboard", {})
        if not isinstance(plan, dict) or not str(plan.get("reading_task", "")).strip():
            raise ValueError(f"{page['id']}缺少逐页阅读任务；先展示完整分镜。")
        visual = plan.get("main_visual", {})
        if not isinstance(visual, dict) or any(not isinstance(visual.get(key), str) or not visual[key].strip() for key in ("structure", "description")):
            raise ValueError(f"{page['id']}需要主视觉结构及其具体含义。")
        refs = plan.get("evidence_refs")
        if not isinstance(refs, list) or not refs or any(ref not in job["sources"] for ref in refs):
            raise ValueError(f"{page['id']}分镜证据缺失或不存在。")
        if not isinstance(plan.get("supporting_blocks"), list) or any(block not in {b['id'] for b in page['blocks']} for block in plan["supporting_blocks"]):
            raise ValueError(f"{page['id']}辅助内容须指向本页内容块。")
        if not isinstance(plan.get("omit"), str) or not plan["omit"].strip():
            raise ValueError(f"{page['id']}需要记录内容取舍。")


def representative_ids(job: dict) -> list[str]:
    """At most two distinct book structures by default, never a fixed page count."""
    pages = job["pages"]
    basics = [p["id"] for role in ("cover", "overview") for p in pages if p["role"] == role]
    books = [p for p in pages if p["role"] == "book"]
    structure = lambda p: p.get("storyboard", {}).get("main_visual", {}).get("structure", "unplanned")
    types = {structure(p) for p in books}
    explicit = job.get("preview_page_ids")
    if explicit is not None:
        if (not isinstance(explicit, list) or not explicit or any(not isinstance(i, str) for i in explicit)
                or len(set(explicit)) != len(explicit) or set(explicit) - {p['id'] for p in pages}
                or set(basics) - set(explicit)):
            raise ValueError("样张计划须使用唯一的本次页面ID，并覆盖封面和已有概览。")
        represented = {structure(p) for p in books if p['id'] in explicit}
        if len(represented) < min(2, len(types)):
            raise ValueError("样张须覆盖不同内容结构的代表书卡。")
        return [p['id'] for p in pages if p['id'] in explicit]
    chosen, seen = set(basics), set()
    for page in books:
        if structure(page) not in seen and len(seen) < 2:
            chosen.add(page['id'])
            seen.add(structure(page))
    return [p['id'] for p in pages if p['id'] in chosen]
