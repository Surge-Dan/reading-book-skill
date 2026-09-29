from __future__ import annotations

import math
import re
import hashlib
from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta, timezone


SKILL_VERSION = "1.0.4"
YEARBOOK_TIMEZONE = timezone(timedelta(hours=8))


def build_gateway_payload(api_name: str, params: dict | None = None) -> dict:
    if not api_name.startswith("/"):
        raise ValueError("api_name 必须以 / 开头")
    payload = {"api_name": api_name, "skill_version": SKILL_VERSION}
    for key, value in (params or {}).items():
        if key in {"api_name", "skill_version", "params"}:
            continue
        if value is not None:
            payload[key] = value
    return payload


def classify_evidence(progress: float, highlights: int, thoughts: int, has_full_text: bool) -> str:
    if has_full_text:
        return "E3"
    annotations = highlights + thoughts
    if progress >= 70 or highlights >= 3 or thoughts >= 2 or annotations >= 4:
        return "E2"
    if progress > 1 or annotations > 0:
        return "E1"
    return "E0"


def _timestamp_parts(value) -> tuple[int | None, int | None]:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return None, None
    if numeric <= 0:
        return None, None
    if numeric > 10_000_000_000:
        numeric //= 1000
    try:
        moment = datetime.fromtimestamp(numeric, tz=YEARBOOK_TIMEZONE)
        return moment.year, moment.month
    except (OverflowError, OSError, ValueError):
        return None, None


def _as_list(value, key: str | None = None) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, dict) and key and isinstance(value.get(key), list):
        return value[key]
    return []


def _note_book_map(notebooks: dict) -> dict[str, dict]:
    result = {}
    for item in _as_list(notebooks, "books"):
        book = item.get("book") or item
        book_id = str(item.get("bookId") or book.get("bookId") or "")
        if book_id:
            result[book_id] = item
    return result


def _review_rows(value) -> list[dict]:
    rows = _as_list(value, "reviews")
    return [item.get("review", item) for item in rows if isinstance(item, dict) and item.get("review", item)]


def _bookmark_rows(value) -> list[dict]:
    return [row for row in _as_list(value, "updated") if row.get("markText")]


def _book_activity_timestamps(book: dict, progress: dict, bookmarks: list, reviews: list) -> list:
    progress_book = progress.get("book", progress) if isinstance(progress, dict) else {}
    values = [book.get("readUpdateTime"), book.get("updateTime"), progress_book.get("updateTime"), progress_book.get("finishTime")]
    values.extend(row.get("createTime") for row in bookmarks)
    values.extend(row.get("createTime") for row in reviews)
    return [value for value in values if value]


def _stable_source_id(book_id: str, kind: str, row: dict, text: str) -> str:
    raw = "|".join(str(value or "") for value in (book_id, kind, row.get("createTime"), row.get("chapterUid"), row.get("range"), text))
    return f"{book_id}-{kind}-{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:12]}"


def _annual_read_map(stats: dict) -> dict[str, int]:
    result = {}
    for item in stats.get("readLongest", []) or []:
        book = item.get("book") or {}
        book_id = str(book.get("bookId") or "")
        if book_id:
            result[book_id] = int(item.get("readTime", 0) or 0)
    return result


def normalize_yearbook(raw: dict, year: int) -> dict:
    shelf = raw.get("shelf") or {}
    note_map = _note_book_map(raw.get("notebooks") or {})
    details = raw.get("book_details") or {}
    stats = raw.get("stats") or {}
    annual_read_seconds = _annual_read_map(stats)
    normalized_books = []
    source_books = {}
    for item in _as_list(shelf, "books"):
        if item.get("bookId"):
            source_books[str(item["bookId"])] = dict(item)
    for item in _as_list(raw.get("notebooks") or {}, "books"):
        note_book = item.get("book") or item
        book_id = str(item.get("bookId") or note_book.get("bookId") or "")
        if book_id:
            source_books[book_id] = {**note_book, **source_books.get(book_id, {})}
    for item in stats.get("readLongest", []) or []:
        stat_book = item.get("book") or {}
        book_id = str(stat_book.get("bookId") or "")
        if book_id:
            source_books[book_id] = {**stat_book, **source_books.get(book_id, {})}
    for shelf_book in source_books.values():
        book_id = str(shelf_book.get("bookId") or "")
        if not book_id:
            continue
        detail = details.get(book_id, {})
        progress_payload = detail.get("progress") or {}
        progress_book = progress_payload.get("book", progress_payload)
        note_summary = note_map.get(book_id, {})
        all_bookmarks = _bookmark_rows(detail.get("bookmarks") or [])
        all_reviews = _review_rows(detail.get("reviews") or [])
        bookmarks = [row for row in all_bookmarks if _timestamp_parts(row.get("createTime"))[0] == year]
        reviews = [row for row in all_reviews if _timestamp_parts(row.get("createTime"))[0] == year]
        activity = _book_activity_timestamps(shelf_book, progress_payload, bookmarks, reviews)
        if note_summary.get("sort"):
            activity.append(note_summary["sort"])
        year_activity = [value for value in activity if _timestamp_parts(value)[0] == year]
        annual_seconds = annual_read_seconds.get(book_id, 0)
        if not year_activity and not annual_seconds:
            continue

        progress = float(progress_book.get("progress", note_summary.get("readingProgress", 0)) or 0)
        lifetime_reading_seconds = int(progress_book.get("recordReadingTime", 0) or 0)
        highlight_rows = [
            {
                "text": str(row.get("markText", "")).strip(),
                "source_id": str(row.get("bookmarkId") or _stable_source_id(book_id, "highlight", row, str(row.get("markText", "")))),
                "chapter_uid": row.get("chapterUid"),
                "range": row.get("range"),
                "created_at": row.get("createTime"),
            }
            for index, row in enumerate(bookmarks)
        ]
        thought_rows = []
        for index, row in enumerate(reviews):
            content = str(row.get("content", "")).strip()
            if content:
                thought_rows.append(
                    {
                        "text": content,
                        "source_id": str(row.get("reviewId") or _stable_source_id(book_id, "thought", row, content)),
                        "quote": str(row.get("abstract", "")).strip(),
                        "chapter_uid": row.get("chapterUid"),
                        "range": row.get("range"),
                        "created_at": row.get("createTime"),
                    }
                )
        months = sorted({month for value in year_activity for event_year, month in [_timestamp_parts(value)] if event_year == year and month})
        category = str(shelf_book.get("category") or detail.get("book", {}).get("category") or "未分类")
        topics = [str(item).strip() for item in shelf_book.get("topics", []) if str(item).strip()]
        if not topics and category != "未分类":
            topics = [item.strip() for item in re.split(r"[-/·,，]", category) if item.strip()][:3]
        bookmark_count = int(note_summary.get("bookmarkCount", 0) or 0)
        finished_in_year = progress == 100 and _timestamp_parts(progress_book.get("finishTime"))[0] == year
        has_year_progress_event = any(_timestamp_parts(value)[0] == year for value in (progress_book.get("updateTime"), progress_book.get("finishTime"), shelf_book.get("readUpdateTime")))
        progress_signal = 100 if finished_in_year else (2 if annual_seconds or has_year_progress_event else 0)
        evidence_level = classify_evidence(progress_signal, len(highlight_rows), len(thought_rows), False)
        normalized_books.append(
            {
                "book_id": book_id,
                "title": str(shelf_book.get("title") or "未命名书籍"),
                "author": str(shelf_book.get("author") or "未知作者"),
                "cover": str(shelf_book.get("cover") or ""),
                "category": category,
                "intro": str(shelf_book.get("intro") or detail.get("book", {}).get("intro") or ""),
                "progress": round(progress, 1),
                "reading_seconds": annual_seconds,
                "annual_reading_seconds": annual_seconds,
                "lifetime_reading_seconds": lifetime_reading_seconds,
                "finish_time": progress_book.get("finishTime"),
                "read_update_time": progress_book.get("updateTime") or shelf_book.get("readUpdateTime"),
                "months": months,
                "highlights": highlight_rows,
                "thoughts": thought_rows,
                "bookmark_count": bookmark_count,
                "lifetime_bookmark_count": bookmark_count,
                "finished_in_year": finished_in_year,
                "topics": topics,
                "evidence_level": evidence_level,
                "evidence_reason": f"{evidence_level}：年内进度信号 {progress_signal:g}%，年内划线 {len(highlight_rows)} 条，年内想法 {len(thought_rows)} 条。",
                "reusability_hint": float(shelf_book.get("reusabilityHint", 0) or 0),
            }
        )

    monthly = [0] * 12
    for key, seconds in (stats.get("readTimes") or {}).items():
        event_year, month = _timestamp_parts(key)
        if month and event_year == year:
            monthly[month - 1] += int(seconds or 0)
    return {
        "schema_version": "1.0",
        "year": int(year),
        "source_mode": raw.get("source_mode", "unknown"),
        "verification_status": raw.get("verification_status", "sample_verified" if raw.get("source_mode") == "sample" else "implemented_unverified"),
        "summary": {
            "book_count": len(normalized_books),
            "total_read_seconds": int(stats.get("totalReadTime", sum(monthly)) or 0),
            "read_days": int(stats.get("readDays", 0) or 0),
            "note_count": sum(len(book["highlights"]) + len(book["thoughts"]) for book in normalized_books),
            "monthly_read_seconds": monthly,
        },
        "books": normalized_books,
    }


def _ratio(value: float, maximum: float) -> float:
    return 0.0 if maximum <= 0 else min(1.0, max(0.0, value / maximum))


def score_books(books: list[dict]) -> list[dict]:
    if not books:
        return []
    max_seconds = max(float(book.get("annual_reading_seconds", book.get("reading_seconds", 0)) or 0) for book in books) or 1
    topic_counts = Counter(topic for book in books for topic in book.get("topics", []))
    scored = []
    for source in books:
        book = deepcopy(source)
        highlights = len(book.get("highlights", []))
        thoughts = len(book.get("thoughts", []))
        annual_seconds = float(book.get("annual_reading_seconds", book.get("reading_seconds", 0)) or 0)
        active_months = len(book.get("months", []))
        reading = 0.7 * _ratio(annual_seconds, max_seconds) + 0.2 * _ratio(active_months, 4) + (0.1 if book.get("finished_in_year") else 0.0)
        personal = min(1.0, (highlights + thoughts * 2) / 8)
        annual = max((_ratio(topic_counts[topic], max(2, len(books) * 0.4)) for topic in book.get("topics", [])), default=0.0)
        turning = min(1.0, (0.55 if thoughts else 0.0) + (0.25 if len(book.get("months", [])) > 1 else 0.0) + (0.2 if book.get("finished_in_year") else 0.0))
        reusable = min(1.0, max(float(book.get("reusability_hint", 0) or 0), 0.15 * len(book.get("topics", [])) + 0.1 * thoughts))
        parts = {
            "reading_investment": round(reading * 100, 1),
            "personal_investment": round(personal * 100, 1),
            "annual_relevance": round(annual * 100, 1),
            "turning_signal": round(turning * 100, 1),
            "reusability": round(reusable * 100, 1),
        }
        total = reading * 20 + personal * 25 + annual * 25 + turning * 15 + reusable * 15
        book["score_parts"] = parts
        book["score"] = round(total, 1)
        labels = {"reading_investment": "阅读投入", "personal_investment": "个人投入", "annual_relevance": "年度关联", "turning_signal": "转折信号", "reusability": "可复用性"}
        leaders = sorted(parts, key=parts.get, reverse=True)[:2]
        book["score_reason"] = "、".join(f"{labels[key]} {parts[key]:g}" for key in leaders)
        scored.append(book)
    scored.sort(key=lambda item: (-item["score"], item["title"], item["book_id"]))
    selected_count = max(1, math.ceil(len(scored) * 0.2))
    candidate_count = min(3, len(scored))
    for index, book in enumerate(scored):
        book["selected"] = index < selected_count
        book["book_of_year_candidate"] = index < candidate_count
    return scored


def build_profiles(books: list[dict]) -> list[dict]:
    profiles = []
    for book in books:
        evidence = book.get("evidence_level", "E0")
        intro = re.sub(r"\s+", " ", str(book.get("intro", "")).strip())
        if evidence == "E0":
            about = "仅保留书目信息；当前阅读证据不足，不生成内容结论。"
        elif intro:
            about = intro[:180] + ("……" if len(intro) > 180 else "")
        elif book.get("highlights"):
            about = "当前只能从已保存划线确认这本书触及的局部问题，不能据此还原完整论证。"
        else:
            about = "已有阅读行为，但缺少可引用文本，暂不补写作者观点。"
        citations = [
            {"source_id": row["source_id"], "type": kind, "text": row["text"]}
            for kind, rows in (("highlight", book.get("highlights", [])), ("thought", book.get("thoughts", [])))
            for row in rows[:3]
        ]
        if book.get("thoughts"):
            thoughts = [row["text"].rstrip("。！？!?；; ") for row in book["thoughts"][:2]]
            reflection = "；".join(thoughts) + "。"
        elif book.get("highlights"):
            reflection = f"这一年的明确阅读痕迹集中在：{book['highlights'][0]['text']}"
        else:
            reflection = "没有可引用的个人想法，暂不代替用户补写感受。"
        profiles.append({"book_id": book["book_id"], "title": book["title"], "author": book.get("author", "未知作者"), "evidence_level": evidence, "about": about, "reflection": reflection, "citations": citations})
    return profiles


def derive_yearly_topics(books: list[dict], limit: int = 3) -> list[dict]:
    counts = Counter(topic for book in books for topic in book.get("topics", []))
    return [{"name": topic, "book_count": count, "book_ids": [book["book_id"] for book in books if topic in book.get("topics", [])]} for topic, count in counts.most_common(limit)]


def choose_yearly_thesis(year: int, topics: list[dict], books: list[dict]) -> str:
    if topics:
        return f"{year}，我沿着“{topics[0]['name']}”反复折返"
    if books:
        return f"{year}，阅读留下了 {len(books)} 个可追溯的坐标"
    return f"{year}，这一页暂时留白"
