from __future__ import annotations

import html
import json
import math
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]


def _replace(template: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        template = template.replace(f"__{key}__", value)
    return template


def render_atlas(data: dict, output_path: Path) -> None:
    template = (SKILL_ROOT / "assets" / "yearbook-template.html").read_text("utf-8")
    safe_json = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    summary = data["summary"]
    page = _replace(
        template,
        {
            "YEAR": str(data["year"]),
            "MODE": html.escape(data["source_mode"]),
            "STATUS": html.escape(data["verification_status"]),
            "THESIS": html.escape(data["thesis"]),
            "BOOK_COUNT": str(summary["book_count"]),
            "HOURS": f"{summary['total_read_seconds'] / 3600:.1f}",
            "NOTE_COUNT": str(summary["note_count"]),
            "DATA": safe_json,
        },
    )
    output_path.write_text(page, "utf-8")


def _profile_body(layout: str, profile: dict) -> str:
    about = html.escape(profile["about"])
    reflection = html.escape(profile["reflection"])
    if layout == "vertical":
        return f'<div class="thread"></div><div class="content"><section class="block"><div class="label">这本书讲了啥</div><p class="copy">{about}</p></section><section class="block"><div class="label">我的思考</div><p class="copy">{reflection}</p></section></div>'
    if layout == "spread":
        return f'<div class="thread"></div><div class="content"><section class="block"><div class="label">这本书讲了啥</div><p class="copy">{about}</p></section><section class="block"><div class="label">我的思考</div><p class="copy">{reflection}</p></section></div>'
    topics = " / ".join(profile.get("topics", [])) or "尚未形成主题"
    return f'<div class="content"><section class="block"><div class="label">问题</div><p class="copy">{about}</p></section><section class="block"><div class="label">线索</div><p class="copy">{html.escape(topics)}</p></section><section class="block"><div class="label">我的思考</div><p class="copy">{reflection}</p></section></div>'


def _point(radius: float, degrees: float) -> tuple[float, float]:
    radians = math.radians(degrees - 90)
    return 280 + radius * math.cos(radians), 280 + radius * math.sin(radians)


def _arc_path(radius: float, start: float, end: float) -> str:
    sx, sy = _point(radius, end)
    ex, ey = _point(radius, start)
    return f"M {sx:.2f} {sy:.2f} A {radius} {radius} 0 0 0 {ex:.2f} {ey:.2f}"


def _cover_orbit(data: dict) -> str:
    monthly = data["summary"]["monthly_read_seconds"]
    maximum = max(monthly or [0]) or 1
    parts = ['<svg class="orbit-data" viewBox="0 0 560 560" aria-label="年度阅读年轮">']
    for index, seconds in enumerate(monthly):
        ratio = seconds / maximum
        width = 3 + 22 * ratio
        opacity = 0.25 + 0.75 * ratio
        parts.append(f'<path class="month-arc" d="{_arc_path(178, index * 30 + 2, (index + 1) * 30 - 3)}" stroke-width="{width:.1f}" opacity="{opacity:.2f}"/>')
        x, y = _point(225, index * 30 + 15)
        parts.append(f'<text class="month-label" x="{x:.2f}" y="{y:.2f}" text-anchor="middle">{index + 1:02d}</text>')
    for index, book in enumerate(data["books"]):
        month = (book.get("months") or [1])[0]
        x, y = _point(205 + (index % 3) * 8, (month - 1) * 30 + 15 + (index % 3 - 1) * 4)
        css = "book-node important" if book.get("book_of_year_candidate") else "book-node"
        radius = 7 if book.get("book_of_year_candidate") else 3
        parts.append(f'<circle class="{css}" cx="{x:.2f}" cy="{y:.2f}" r="{radius}"><title>{html.escape(book["title"])}</title></circle>')
    parts.append(f'<text x="280" y="270" text-anchor="middle" style="font:500 58px Iowan Old Style,serif;fill:var(--ink)">{data["year"]}</text>')
    parts.append('<text x="280" y="296" text-anchor="middle" style="font:10px ui-monospace,monospace;letter-spacing:.18em;fill:var(--muted)">READING ORBIT</text></svg>')
    return "".join(parts)


def render_cards(data: dict, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    template = (SKILL_ROOT / "assets" / "card-template.html").read_text("utf-8")
    rendered = []
    cover = _replace(template, {"LAYOUT": "cover", "META": f"READING YEARBOOK / {data['year']}", "TITLE": html.escape(data["thesis"]), "AUTHOR": "", "BODY": _cover_orbit(data), "FOOT_LEFT": f"{data['summary']['book_count']} 本书", "FOOT_RIGHT": data["source_mode"]})
    cover_path = output_dir / "01-cover.html"
    cover_path.write_text(cover, "utf-8")
    rendered.append(cover_path)
    profile_map = {item["book_id"]: item for item in data["profiles"]}
    cards = [book for book in data["books"] if book["selected"] or book["book_of_year_candidate"]]
    layouts = ("vertical", "spread", "fold")
    for index, book in enumerate(cards, start=2):
        profile = dict(profile_map[book["book_id"]])
        profile["topics"] = book.get("topics", [])
        layout = layouts[(index - 2) % len(layouts)]
        page = _replace(template, {"LAYOUT": layout, "META": f"{index:02d} / {book['evidence_level']} / SCORE {book['score']}", "TITLE": html.escape(book["title"]), "AUTHOR": html.escape(book["author"]), "BODY": _profile_body(layout, profile), "FOOT_LEFT": html.escape(book["score_reason"]), "FOOT_RIGHT": f"{data['year']} · {book['progress']}%"})
        path = output_dir / f"{index:02d}-{book['book_id']}.html"
        path.write_text(page, "utf-8")
        rendered.append(path)
    return rendered
