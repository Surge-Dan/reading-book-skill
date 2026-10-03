"""Small, versioned contracts for scope, creation decisions and confirmation records.

Records are supplied by the host assistant, not authenticated by this module.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from content_plan import representative_ids, validate_storyboards
from art_direction import validate_artwork


RATIOS = {"1:1": (900, 900), "3:4": (900, 1200), "4:5": (900, 1125)}
FORMATS = {"annual", "book-list", "single-book", "single-image"}


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def make_canvas(ratio: str, width: int | None = None, height: int | None = None) -> dict:
    if ratio == "custom":
        if width is None or height is None:
            raise ValueError("自定义比例需要明确宽高。")
    elif ratio in RATIOS:
        base_width, base_height = RATIOS[ratio]
        width = base_width if width is None else width
        scaled = width * base_height / base_width
        height = int(scaled) if height is None and scaled.is_integer() else height
        if height is None or width * base_height != height * base_width:
            raise ValueError("画布宽高与所选比例不一致。")
    else:
        raise ValueError("选择1:1、3:4、4:5，或提供custom宽高。")
    if any(type(value) is not int or not 375 <= value <= 4096 for value in (width, height)):
        raise ValueError("画布宽高须为375–4096的整数；更大尺寸先讨论运行成本。")
    if ratio == "custom":
        divisor = math.gcd(width, height)
        ratio = f"{width // divisor}:{height // divisor}"
    return {"ratio": ratio, "width": width, "height": height}


def validate_canvas(canvas: dict | None) -> None:
    if not isinstance(canvas, dict):
        raise ValueError("先和用户确认图片比例；任务尚未设置画布。")
    width, height = canvas.get("width"), canvas.get("height")
    validated = make_canvas("custom", width, height)
    if canvas.get("ratio") != validated["ratio"]:
        raise ValueError("画布比例与宽高不一致。")


def require_current(job: dict) -> None:
    if job.get("schema_version") != "share-3":
        raise ValueError("旧任务缺少逐页分镜：保留原文件，复用输入在新目录创建share-3任务；不能补写历史认可。")


def scope_payload(job: dict) -> dict:
    return {"year": job["year"], "period": job["period"], "brief": job.get("brief"), "canvas": job.get("canvas"),
            "books": [{key: book[key] for key in ("book_id", "title", "author")} for book in job["books"]],
            "page_plan": [{key: page[key] for key in ("id", "role", "book_ids")} for page in job["pages"]]}


def validate_scope(job: dict) -> None:
    require_current(job)
    validate_canvas(job.get("canvas"))
    brief = job.get("brief", {})
    if not isinstance(brief, dict) or brief.get("format") not in FORMATS or not str(brief.get("platform", "")).strip() or not str(brief.get("focus", "")).strip():
        raise ValueError("简报需要发布场景、产物类型和内容主角。")
    roles = [page["role"] for page in job["pages"]]
    if not roles or roles[0] != "cover" or roles.count("cover") != 1 or any(role not in {"cover", "overview", "book"} for role in roles):
        raise ValueError("页面角色或封面顺序无效。")
    if brief["format"] == "annual" and (len(roles) < 3 or roles[1] != "overview" or roles.count("overview") != 1 or "book" not in roles):
        raise ValueError("年度组图需要封面、独立年度概览和精选书卡。")
    if brief["format"] == "single-image" and len(roles) != 1:
        raise ValueError("单图任务只能有一页，不扩展组图。")
    if brief["format"] == "single-book" and len(job["books"]) != 1:
        raise ValueError("单书任务须选择一本书。")
    if {book["book_id"] for book in job["books"]} != {book_id for page in job["pages"] for book_id in page["book_ids"]}:
        raise ValueError("页面计划和当前书目不一致。")


def confirmation_record(job: dict, stage: str, version: str, confirmation: dict | None, sample_test: bool) -> dict:
    if sample_test:
        if job["source_mode"] != "sample":
            raise ValueError("技术测试确认不能用于真实数据。")
        evidence = {"reply": "仅样例技术测试，不代表用户认可。", "context_ref": "sample-test"}
    else:
        if not isinstance(confirmation, dict) or any(not isinstance(confirmation.get(key), str) or not confirmation[key].strip() for key in ("reply", "context_ref")):
            raise ValueError("确认须包含用户实际回复reply及对应会话context_ref，不能由脚本推断同意。")
        evidence = {key: confirmation[key].strip() for key in ("reply", "context_ref")}
        if any(len(value) > 2000 for value in evidence.values()):
            raise ValueError("只记录当前确认的回复或摘要，不复制完整对话。")
    if re.search(r"\bwrk-[a-zA-Z0-9_-]{12,}|WEREAD_API_KEY\s*[:=]", json.dumps(evidence, ensure_ascii=False)):
        raise ValueError("确认记录疑似包含密钥，不能保存；仅记录当前方案的选择。")
    return {"stage": stage, "hash": version, "actor": "sample-test" if sample_test else "user",
            "at": datetime.now(timezone.utc).isoformat(), "evidence": evidence}


def require_confirmation(job: dict, stage: str, version: str) -> None:
    approval = job.get("approvals", {}).get(stage, {})
    evidence = approval.get("evidence", {})
    if (approval.get("stage") != stage or approval.get("hash") != version or approval.get("actor") not in ("user", "sample-test")
            or any(not isinstance(evidence.get(key), str) or not evidence[key].strip() for key in ("reply", "context_ref"))
            or (job["source_mode"] == "live" and approval.get("actor") != "user")):
        raise ValueError(f"{stage}阶段当前版本未确认；先展示相应方案或图片并记录实际回复。")


def require_scope(job: dict) -> None:
    validate_scope(job)
    require_confirmation(job, "scope", digest(scope_payload(job)))


def validate_creation(job: dict) -> None:
    validate_storyboards(job)
    validate_artwork(job)
    representative_ids(job)
    directions = job.get("directions", [])
    if not isinstance(directions, list) or len(directions) != 2:
        raise ValueError("先提供两个有参考依据的视觉方向，不先做两套成品。")
    ids = []
    for direction in directions:
        if not isinstance(direction, dict) or any(not isinstance(direction.get(key), str) or not direction[key].strip() for key in ("id", "label", "concept")):
            raise ValueError("每个方向须有id、名称label和具体视觉策略concept。")
        if not isinstance(direction.get("fonts"), list) or not direction["fonts"] or any(not isinstance(font, dict) or any(not isinstance(font.get(key), str) or not font[key].strip() for key in ("family", "role")) for font in direction["fonts"]):
            raise ValueError("方向须说明实际字体family及职责role。")
        if not isinstance(direction.get("references"), list) or not direction["references"] or any(not isinstance(ref, dict) or any(not isinstance(ref.get(key), str) or not ref[key].strip() for key in ("source", "lesson")) for ref in direction["references"]):
            raise ValueError("方向须记录参考来源source及具体借鉴lesson。")
        ids.append(direction["id"])
    if len(set(ids)) != 2 or directions[0]["concept"].strip() == directions[1]["concept"].strip():
        raise ValueError("两个方向须有不同的标识和视觉策略，不能仅换名称。")
    if job.get("selected_direction") not in ids or not job.get("art_brief"):
        raise ValueError("先确认一个视觉方向及艺术简报。")
    if job["brief"].get("focus") == "reading-takeaways":
        for page in job["pages"]:
            if page["role"] != "book" and job["brief"]["format"] != "single-image":
                continue
            if not any(block["kind"] in ("thought", "user_input") or
                       (block["kind"] == "editorial" and any(job["sources"].get(ref, {}).get("kind") == "thought" for ref in block.get("source_refs", [])))
                       for block in page["blocks"]):
                raise ValueError(f"{page['id']}没有个人想法来源；先追问、换书或确认改为摘录表达。")


def preview_ids(job: dict) -> list[str]:
    return representative_ids(job)
