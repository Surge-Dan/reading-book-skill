from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from yearbook_core import YEARBOOK_TIMEZONE, build_gateway_payload


GATEWAY_URL = "https://i.weread.qq.com/api/agent/gateway"


class WeReadError(RuntimeError):
    pass


def _unwrap(response: dict) -> dict:
    if response.get("upgrade_info"):
        message = response["upgrade_info"].get("message", "微信读书 Skill 需要升级")
        raise WeReadError(message)
    data = response.get("data")
    return data if isinstance(data, dict) else response


def gateway_call(api_name: str, params: dict, api_key: str, timeout: int = 30, retries: int = 2) -> dict:
    body = json.dumps(build_gateway_payload(api_name, params), ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        GATEWAY_URL,
        data=body,
        method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "User-Agent": "reading-yearbook-skill/0.1"},
    )
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return _unwrap(json.loads(response.read().decode("utf-8")))
        except urllib.error.HTTPError as exc:
            if exc.code in {401, 403, 422, 499} or attempt == retries:
                raise WeReadError(f"微信读书接口返回 HTTP {exc.code}；请检查 Key、参数或 Skill 版本。") from None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            if attempt == retries:
                raise WeReadError(f"微信读书接口暂时不可用：{type(exc).__name__}") from None
        time.sleep(0.6 * (attempt + 1))
    raise WeReadError("微信读书接口请求失败")


def collection_status(errors: list, truncated: bool) -> str:
    return "partial_unverified" if errors or truncated else "implemented_unverified"


def _in_year(value, year: int) -> bool:
    try:
        numeric = int(value)
        if numeric > 10_000_000_000:
            numeric //= 1000
        return datetime.fromtimestamp(numeric, tz=YEARBOOK_TIMEZONE).year == year
    except (TypeError, ValueError, OSError, OverflowError):
        return False


def select_candidate_books(year: int, shelf: dict, notebooks: dict, stats: dict, scan_all: bool = False) -> list[dict]:
    candidates = {}
    for book in shelf.get("books", []) or []:
        book_id = str(book.get("bookId") or "")
        if book_id and (scan_all or _in_year(book.get("readUpdateTime") or book.get("updateTime"), year)):
            candidates[book_id] = dict(book)
    for item in notebooks.get("books", []) or []:
        book = item.get("book") or item
        book_id = str(item.get("bookId") or book.get("bookId") or "")
        if book_id and (scan_all or _in_year(item.get("sort"), year)):
            candidates[book_id] = {**book, **candidates.get(book_id, {})}
    for item in stats.get("readLongest", []) or []:
        book = item.get("book") or {}
        book_id = str(book.get("bookId") or "")
        if book_id:
            candidates[book_id] = {**book, **candidates.get(book_id, {})}
    return list(candidates.values())


def _collect_notebooks(api_key: str) -> tuple[dict, list[dict]]:
    books, cursor = [], None
    total_note_count = 0
    errors = []
    while True:
        params = {"count": 50, "lastSort": cursor}
        try:
            page = gateway_call("/user/notebooks", params, api_key)
        except WeReadError as exc:
            if not books:
                raise
            errors.append({"scope": "notebooks", "cursor": cursor, "error": str(exc)})
            break
        page_books = page.get("books", [])
        books.extend(page_books)
        total_note_count = int(page.get("totalNoteCount", total_note_count) or total_note_count)
        if not page.get("hasMore") or not page_books:
            break
        next_cursor = page_books[-1].get("sort")
        if next_cursor is None or next_cursor == cursor:
            errors.append({"scope": "notebooks", "cursor": cursor, "error": "笔记本分页游标没有前进，已停止以避免重复请求。"})
            break
        cursor = next_cursor
    return {"books": books, "totalBookCount": len(books), "totalNoteCount": total_note_count, "hasMore": 1 if errors else 0}, errors


def _collect_reviews(book_id: str, api_key: str) -> dict:
    reviews, cursor = [], 0
    while True:
        page = gateway_call("/review/list/mine", {"bookid": book_id, "count": 50, "synckey": cursor}, api_key)
        reviews.extend(page.get("reviews", []))
        if not page.get("hasMore"):
            break
        next_cursor = page.get("synckey")
        if next_cursor is None or next_cursor == cursor:
            raise WeReadError(f"{book_id} 的想法分页游标没有前进。")
        cursor = next_cursor
    return {"reviews": reviews, "totalCount": len(reviews), "hasMore": 0}


def collect_year(year: int, api_key: str, max_books: int | None = None, scan_all_shelf: bool = False) -> dict:
    base_time = int(datetime(year, 1, 1, tzinfo=YEARBOOK_TIMEZONE).timestamp())
    shelf = gateway_call("/shelf/sync", {}, api_key)
    notebooks, pagination_errors = _collect_notebooks(api_key)
    stats = gateway_call("/readdata/detail", {"mode": "annually", "baseTime": base_time}, api_key)
    shelf_books = select_candidate_books(year, shelf, notebooks, stats, scan_all_shelf)
    truncated = max_books is not None and len(shelf_books) > max_books
    if max_books is not None:
        shelf_books = shelf_books[:max_books]
    details, errors = {}, list(pagination_errors)
    for index, book in enumerate(shelf_books, start=1):
        book_id = str(book.get("bookId") or "")
        if not book_id:
            continue
        try:
            details[book_id] = {
                "book": gateway_call("/book/info", {"bookId": book_id}, api_key),
                "progress": gateway_call("/book/getprogress", {"bookId": book_id}, api_key),
                "bookmarks": gateway_call("/book/bookmarklist", {"bookId": book_id}, api_key),
                "reviews": _collect_reviews(book_id, api_key),
            }
        except WeReadError as exc:
            errors.append({"book_id": book_id, "index": index, "error": str(exc)})
    return {
        "source_mode": "live",
        "verification_status": collection_status(errors, truncated),
        "collection_complete": not errors and not truncated,
        "truncated": truncated,
        "year": year,
        "shelf": shelf,
        "notebooks": notebooks,
        "stats": stats,
        "book_details": details,
        "collection_errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="从微信读书官方 Agent Gateway 采集年度数据。")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-books", type=int, help="只用于调试；正式年报应省略")
    parser.add_argument("--scan-all-shelf", action="store_true", help="逐本扫描整个书架；耗时较长，仅在年度候选明显缺失时使用")
    args = parser.parse_args()
    api_key = os.environ.get("WEREAD_API_KEY", "").strip()
    if not api_key:
        print(json.dumps({"status": "missing_credentials", "message": "未检测到 WEREAD_API_KEY；可先运行样例模式。"}, ensure_ascii=False))
        return 2
    try:
        result = collect_year(args.year, api_key, args.max_books, args.scan_all_shelf)
    except WeReadError as exc:
        print(json.dumps({"status": "failed", "message": str(exc)}, ensure_ascii=False))
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
    print(json.dumps({"status": "ok", "output": str(args.output), "books": len(result["book_details"]), "errors": len(result["collection_errors"])}, ensure_ascii=False))
    return 0 if not result["collection_errors"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
