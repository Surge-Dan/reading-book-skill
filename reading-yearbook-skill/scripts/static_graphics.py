"""Original static SVG helpers: no copied Lieflat source, dependencies or theme.

Deck builders call render_graphic with a registered source and current palette.
The CLI emits an SVG fragment to inline in the deck (not an external img).
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
from html import escape
import json
import math
from pathlib import Path
import re

KINDS = {"relations", "monthly-trace", "calendar"}


def number(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def calendar_cells(year: int, records: dict, as_of: str) -> list[dict]:
    """Monday-first real dates, including partial weeks and leap days."""
    start, end, cutoff = date(year, 1, 1), date(year, 12, 31), date.fromisoformat(as_of)
    if not isinstance(records, dict):
        raise ValueError("日历需要逐日来源；不能使用月度汇总。")
    for key, value in records.items():
        day = date.fromisoformat(key)
        if day.year != year or day.isoformat() != key or (value is not None and not number(value)):
            raise ValueError("逐日记录必须使用本年ISO日期及非负秒数，未知为null。")
        if day > cutoff and value is not None:
            raise ValueError("逐日记录包含截至日期之后的数值。")
    origin = start - timedelta(days=start.weekday())
    cells, day = [], start
    while day <= end:
        value = records.get(day.isoformat())
        state = "future" if day > cutoff else ("missing" if value is None else ("zero" if value == 0 else "observed"))
        cells.append({"date": day.isoformat(), "week": (day-origin).days//7, "weekday": day.weekday(), "month": day.month,
                      "seconds": value, "state": state})
        day += timedelta(days=1)
    return cells


def monthly_points(year: int, value: dict, as_of: str) -> list[dict]:
    seconds, observed = value.get("seconds"), value.get("observed")
    if (not isinstance(seconds, list) or len(seconds) != 12 or not all(number(v) for v in seconds)
            or not isinstance(observed, list) or len(observed) != 12 or any(type(v) is not bool for v in observed)):
        raise ValueError("月度轨迹须有12个非负秒数及12个真实记录标记；旧数组不能证明零值。")
    cutoff = date.fromisoformat(as_of)
    result = []
    for month, (amount, known) in enumerate(zip(seconds, observed), 1):
        future = date(year, month, 1) > cutoff
        if (not known or future) and amount != 0:
            raise ValueError("缺失或未来月份不能带有时长数值。")
        result.append({"month": month, "seconds": amount if known and not future else None,
                       "state": "future" if future else ("missing" if not known else ("zero" if amount == 0 else "observed"))})
    return result


def validate_graphics(job: dict) -> None:
    seen = set()
    for page in job["pages"]:
        blocks = {b['id']: b for b in page['blocks']}
        for graphic in page.get("graphics", []):
            gid = graphic.get("id", "")
            if not isinstance(gid, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,79}", gid) or gid in seen:
                raise ValueError("图形ID须唯一，以字母开头。")
            seen.add(gid)
            kind = graphic.get("kind")
            if kind not in KINDS:
                raise ValueError("未知静态图形；先按材料选择索引中的能力。")
            if kind == "relations":
                nodes = graphic.get("nodes", [])
                if not nodes:
                    raise ValueError("内容图解需要有文字证据的节点。")
                ids = set()
                for node in nodes:
                    nid = node.get("id")
                    if not isinstance(nid, str) or not nid or nid in ids or node.get("block_id") not in blocks:
                        raise ValueError("图解节点须唯一并绑定本页内容块。")
                    ids.add(nid)
                    if not blocks[node['block_id']].get('source_refs'):
                        raise ValueError("解释性节点须有来源；用户补充可先登记对应来源。")
                    if any(not number(node.get(k)) for k in ("x", "y", "width", "height")) or min(node['width'], node['height']) <= 0:
                        raise ValueError("图解节点需要明确的非负位置及正尺寸。")
                for edge in graphic.get("edges", []):
                    if edge.get("from") not in ids or edge.get("to") not in ids or edge['from'] == edge['to']:
                        raise ValueError("关系连接引用了不存在或相同的节点。")
                    refs = edge.get("source_refs", [])
                    if not refs or any(ref not in job["sources"] for ref in refs):
                        raise ValueError("关系连接必须记录编辑依据。")
                    if any(key in edge for key in ("weight", "score", "percentage")):
                        raise ValueError("解释性关系不能编码虚构权重或分值。")
            else:
                source = job['sources'].get(graphic.get('source_ref'), {})
                if source.get('kind') != 'fact' or 'value' not in source:
                    raise ValueError("统计图须绑定含实际数值的事实来源。")
                if kind == 'calendar':
                    calendar_cells(job['year'], source['value'], job['period']['as_of'])
                else:
                    if not isinstance(source['value'], dict):
                        raise ValueError("月度图需要明确数据与覆盖标记。")
                    monthly_points(job['year'], source['value'], job['period']['as_of'])


def wrap_text(text: str, capacity: float) -> list[str]:
    """Conservative estimate; real export still checks rendered bounds."""
    lines, line, used = [], '', 0.
    for char in text:
        advance = .56 if ord(char) < 256 else 1.
        if char == '\n' or (line and used + advance > capacity):
            lines.append(line)
            line, used = '', 0.
        if char != '\n':
            line += char
            used += advance
    if line:
        lines.append(line)
    return lines or ['']


def render_graphic(job: dict, page_id: str, graphic_id: str, width: int = 780, height: int = 380, palette: dict | None = None) -> str:
    validate_graphics(job)
    if not (type(width) is int and type(height) is int and width >= 240 and height >= 180):
        raise ValueError("SVG尺寸须为整数，至少240×180；手机可读性另外检查。")
    page = next(p for p in job['pages'] if p['id'] == page_id)
    spec = next(g for g in page.get('graphics', []) if g['id'] == graphic_id)
    colors = {key: f'var(--chart-{key})' for key in ('ink', 'muted', 'accent', 'paper', 'line')}
    colors.update(palette or {})
    if set(colors) - {'ink', 'muted', 'accent', 'paper', 'line'} or any(not re.fullmatch(r'#[0-9A-Fa-f]{3,8}|var\(--[a-zA-Z0-9_-]+\)', v) for v in colors.values()):
        raise ValueError("图形颜色使用本次色彩角色，传入hex或CSS变量。")
    font = spec.get('font_size', 28)
    if not number(font) or not 24 <= font <= 96:
        raise ValueError("图形字号需24–96，按实际画布检查手机阅读。")
    parts = []
    def text(x, y, value, attrs='', color='ink'):
        return f'<text x="{x:.2f}" y="{y:.2f}" fill="{colors[color]}" font-size="{font}" {attrs}>{escape(str(value))}</text>'
    def line(x1, y1, x2, y2, attrs=''):
        return f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{colors["line"]}" stroke-width="2" {attrs}/>'
    kind = spec['kind']
    if kind == 'relations':
        nodes = {n['id']: n for n in spec['nodes']}
        marker = f'arrow-{graphic_id}'
        parts.append(f'<defs><marker id="{marker}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{colors["line"]}"/></marker></defs>')
        for edge in spec.get('edges', []):
            a, b = nodes[edge['from']], nodes[edge['to']]
            dx, dy = b['x']-a['x'], b['y']-a['y']
            if abs(dx) > abs(dy):
                x1, x2 = a['x']+(a['width'] if dx>0 else 0), b['x']+(0 if dx>0 else b['width'])
                y1, y2 = a['y']+a['height']/2, b['y']+b['height']/2
            else:
                x1, x2 = a['x']+a['width']/2, b['x']+b['width']/2
                y1, y2 = a['y']+(a['height'] if dy>0 else 0), b['y']+(0 if dy>0 else b['height'])
            parts.append(line(x1, y1, x2, y2, f'marker-end="url(#{marker})"'))
        blocks = {b['id']: b for b in page['blocks']}
        for node in nodes.values():
            x,y,w,h = (node[k] for k in ('x','y','width','height'))
            if x+w > width or y+h > height:
                raise ValueError("图解节点超出画布；重新组织构图。")
            lines = wrap_text(blocks[node['block_id']]['text'], (w-36)/font)
            if len(lines)*font*1.4+32 > h:
                raise ValueError("图解节点文字放不下；缩短选材或扩大节点，不能静默裁切。")
            parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{colors["paper"]}" stroke="{colors["line"]}" stroke-width="2"/>')
            content = ''.join(f'<tspan x="{x+18}" y="{y+26+font+i*font*1.4}">{escape(v)}</tspan>' for i,v in enumerate(lines))
            parts.append(f'<text fill="{colors["ink"]}" font-size="{font}" data-block="{node["block_id"]}">{content}</text>')
    elif kind == 'monthly-trace':
        records = monthly_points(job['year'], job['sources'][spec['source_ref']]['value'], job['period']['as_of'])
        maximum = max((r['seconds'] or 0 for r in records), default=0) or 3600
        left,right,top,bottom = 64,width-32,58,height-116
        if bottom <= top+font:
            raise ValueError("轨迹高度不足以容纳图例和标签。")
        parts += [text(left,42,'小时','data-label'), text(14,top+font*.3,f'{maximum/3600:g}','data-label','muted'), text(14,bottom,'0','data-label','muted'), line(left,bottom,right,bottom)]
        previous = None
        for row in records:
            x = left+(right-left)*(row['month']-1)/11
            parts.append(text(x,height-62,row['month'],'data-label text-anchor="middle"','muted'))
            amount = row['seconds']
            if amount is None:
                parts.append(text(x,bottom-16,'·' if row['state']=='future' else '×','data-label text-anchor="middle"','muted'))
                previous = None
                continue
            y = bottom-(bottom-top)*amount/maximum
            if previous:
                parts.append(line(*previous,x,y,f'style="stroke:{colors["accent"]};stroke-width:3"'))
            parts.append(f'<circle cx="{x}" cy="{y}" r="6" fill="{colors["accent"]}"/>')
            previous = (x,y)
        parts.append(text(64,height-18,'月份 / ×缺记录 ·未到日期','data-label','muted'))
    else:
        rows = calendar_cells(job['year'], job['sources'][spec['source_ref']]['value'], job['period']['as_of'])
        columns = max(r['week'] for r in rows)+1
        cell = min((width-74)/columns,(height-148)/7)
        if cell < 5:
            raise ValueError("日历网格太小；扩大主视觉，不缩成装饰纹理。")
        maximum = max((r['seconds'] or 0 for r in rows if r['state']=='observed'), default=1)
        months = set()
        for row in rows:
            x,y = 62+row['week']*cell,82+row['weekday']*cell
            if row['month'] not in months:
                parts.append(text(x,36 if row['month']%2 else 66,row['month'],'data-label','muted'))
                months.add(row['month'])
            state = row['state']
            fill = colors['accent'] if state=='observed' else (colors['paper'] if state=='zero' else 'none')
            opacity = .25+.75*(row['seconds'] or 0)/maximum if state=='observed' else 1
            parts.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{cell-2:.2f}" height="{cell-2:.2f}" fill="{fill}" opacity="{opacity:.3f}" stroke="{colors["line"]}" stroke-width="1" data-date="{row["date"]}" data-state="{state}"/>')
            if state=='missing':
                parts.append(line(x+2,y+2,x+cell-4,y+cell-4))
            elif state=='future':
                parts.append(f'<circle cx="{x+cell/2:.2f}" cy="{y+cell/2:.2f}" r="1.2" fill="{colors["muted"]}"/>')
        for day,label in ((0,'一'),(6,'日')):
            parts.append(text(12,82+day*cell+font*.75,label,'data-label','muted'))
        parts.append(text(64,height-18,'浅底零 / 斜线缺 / 点未到 / 深浅时长','data-label','muted'))
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" data-graphic="{graphic_id}" data-ready="true" role="img" aria-label="{escape(kind,quote=True)}">{"".join(parts)}</svg>'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job',type=Path,required=True)
    parser.add_argument('--page',required=True)
    parser.add_argument('--graphic',required=True)
    parser.add_argument('--width',type=int,default=780)
    parser.add_argument('--height',type=int,default=380)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    svg = render_graphic(json.loads(args.job.read_text('utf-8')),args.page,args.graphic,args.width,args.height)
    args.output.write_text(svg,'utf-8')
