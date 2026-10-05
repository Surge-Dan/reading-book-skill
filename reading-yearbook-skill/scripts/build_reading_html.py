"""Build a private, offline reading yearbook. No network or credentials required."""
from __future__ import annotations

import argparse
import base64
import html
import json
import math
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from reading_fonts import font_css

ROOT = Path(__file__).resolve().parents[1]
TZ = timezone(timedelta(hours=8))


def number(value):
    if isinstance(value, bool):
        return None
    try:
        value = float(value)
        return value if math.isfinite(value) and value >= 0 else None
    except (ValueError, TypeError):
        return None


def date_value(value):
    if not value:
        return None
    try:
        if isinstance(value, (int, float)) or str(value).isdigit():
            stamp = float(value)
            return datetime.fromtimestamp(stamp / 1000 if stamp > 10**10 else stamp, TZ).strftime('%Y-%m-%d')
        match = re.match(r'^\d{4}-\d{2}-\d{2}(?:$|[ T])', str(value))
        if match:
            return datetime.strptime(str(value)[:10], '%Y-%m-%d').strftime('%Y-%m-%d')
    except (ValueError, OverflowError, OSError):
        pass
    return None


def notes(rows, year):
    result, seen = [], set()
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        text = str(row.get('text') or '').strip()
        when = date_value(row.get('created_at'))
        if not text or (year is not None and when and int(when[:4]) != year):
            continue
        source_id = str(row.get('source_id') or '')
        identity = source_id or (text, when)
        if identity in seen:
            continue
        seen.add(identity)
        result.append({'text': text, 'created_at': when, 'source_id': source_id,
                       'chapter': str(row.get('chapter_uid') or ''), 'chapter_title': str(row.get('chapter_title') or ''),
                       'quote': str(row.get('quote') or '')})
    return result


def adapt_data(raw, year=None):
    year = int(year or raw.get('year') or raw.get('period', {}).get('year') or datetime.now(TZ).year)
    if not 1900 <= year <= 2200:
        raise ValueError('年份须在1900—2200之间')
    share = 'sources' in raw and 'annual_summary' in raw
    sources = raw.get('sources', {}) if share else {}
    summary = raw.get('annual_summary' if share else 'summary', {})
    rows = raw.get('books', [])
    if not isinstance(rows, list) or not isinstance(summary, dict):
        raise ValueError('books须为列表，summary须为对象')
    if 'shelf' in raw and 'stats' in raw:
        from yearbook_core import normalize_yearbook
        return adapt_data(normalize_yearbook(raw, year), year)
    books, seen = [], set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        book_id = str(row.get('book_id') or '').strip()
        if not book_id or book_id in seen:
            continue
        seen.add(book_id)
        if share:
            highlights, thoughts = [], []
            for key, value in sources.items():
                if not key.startswith(book_id + '/') or key.endswith('/date') or not isinstance(value, dict):
                    continue
                dest = highlights if '/highlight/' in key else thoughts if '/thought/' in key else None
                if dest is not None:
                    dest.append({'text': value.get('text'), 'source_id': value.get('source_id', key),
                                 'created_at': value.get('created_at'), 'quote': value.get('abstract', '')})
        else:
            highlights, thoughts = row.get('highlights', []), row.get('thoughts', [])
        progress = number(row.get('progress'))
        if progress is not None and progress > 100:
            progress = None
        category = row.get('category')
        category = category if isinstance(category, str) else None
        primary_category = re.split(r'[-/]', category)[0].strip() if category else '未分类'
        books.append({'book_id': book_id, 'title': str(row.get('title') or '未命名书籍'),
                      'author': str(row.get('author') or '作者未记录'),
                      'category': primary_category or '未分类', 'source_category': category or '', 'category_basis': str(row.get('category_basis') or '来源分类'),
                      'progress': progress, 'status': 'finished' if progress == 100 else 'reading' if progress is not None and progress > 0 else 'unknown',
                      'reading_seconds': number(row.get('annual_reading_seconds', row.get('reading_seconds'))),
                      'highlights': notes(highlights, year), 'thoughts': notes(thoughts, year),
                      'finish_date': date_value(row.get('finish_time')), 'start_date': date_value(row.get('start_time')),
                      'intro': str(row.get('intro') or sources.get(book_id + '/intro', {}).get('text') or ''),
                      'cover': '', 'selected': row.get('selected', True) is True})
    def stat(key, fallback):
        return number(sources.get(key, {}).get('value')) if key in sources else number(fallback)
    total = stat('annual/read', summary.get('book_count'))
    as_of = date_value(raw.get('period', {}).get('as_of') or raw.get('as_of'))
    monthly = summary.get('monthly_read_seconds')
    if monthly is None:
        monthly = [None] * 12
    if not isinstance(monthly, list):
        raise ValueError('monthly_read_seconds须为列表，缺失月份用null')
    observed = summary.get('monthly_observed')
    values = []
    for i in range(12):
        value = number(monthly[i]) if i < len(monthly) else None
        if isinstance(observed, list) and (i >= len(observed) or observed[i] is not True):
            value = None
        if as_of and year == int(as_of[:4]) and i + 1 > int(as_of[5:7]):
            value = None
        values.append(value)
    # Do not present the partly collected current month as a complete month.
    complete_months = int(as_of[5:7]) - 1 if as_of and int(as_of[:4]) == year else 12
    return {'schema_version': 'reading-html/1.1', 'year': year, 'as_of': as_of,
            'source_mode': str(raw.get('source_mode', 'unknown')),
            'verification_status': str(raw.get('coverage', {}).get('verification_status') or raw.get('verification_status') or 'unverified'),
            'coverage': {'loaded_books': len(books), 'annual_books': total,
                         'complete': total is not None and len(books) == total},
            'summary': {'read': total if total is not None else len(books),
                        'finished': stat('annual/finished', summary.get('finished_count')),
                        'read_days': number(summary.get('read_days')),
                        'notes': stat('annual/notes', summary.get('note_count')),
                        'seconds': number(summary.get('total_read_seconds')),
                        'monthly': values, 'complete_months': complete_months}, 'books': books}


def merge_annual(data, snapshot):
    """Merge positively identified year activity, never the entire shelf."""
    annual = snapshot.get('annual') or {}
    years = {int(date[:4]) for key in (annual.get('readTimes') or {})
             if (date := date_value(key))}
    declared_year = snapshot.get('year')
    if declared_year is not None:
        years.add(int(declared_year))
    if years != {data['year']}:
        raise ValueError('年度快照缺少可核验年份，或与年鉴年份不一致')
    # Official annual totals and current per-book progress are separate scopes.
    # Prefer an actual annual response to stale hand-entered share facts.
    for row in annual.get('readStat', []):
        key = {'读过': 'read', '读完': 'finished', '笔记': 'notes'}.get(row.get('stat'))
        count = re.fullmatch(r'\s*(\d+)\s*(?:本|条)?\s*', str(row.get('counts') or ''))
        if key and count:
            data['summary'][key] = int(count[1])
    for field, key in [('readDays', 'read_days'), ('totalReadTime', 'seconds')]:
        if number(annual.get(field)) is not None:
            data['summary'][key] = number(annual[field])
    if date_value(snapshot.get('as_of')):
        data['as_of'] = date_value(snapshot['as_of'])
        data['summary']['complete_months'] = int(data['as_of'][5:7])-1 if int(data['as_of'][:4]) == data['year'] else 12
    if annual.get('readTimes'):
        monthly = [None]*12
        for timestamp, seconds in annual['readTimes'].items():
            date = date_value(timestamp)
            if date and int(date[:4]) == data['year']:
                month = int(date[5:7])-1
                if not data['as_of'] or int(data['as_of'][:4]) != data['year'] or month < int(data['as_of'][5:7]):
                    monthly[month] = number(seconds)
        data['summary']['monthly'] = monthly
    shelf = {str(b.get('bookId')): b for b in snapshot.get('shelf', {}).get('books', [])}
    existing = {b['book_id']: b for b in data['books']}
    ranked = {str(x.get('book', {}).get('bookId')): x for x in annual.get('readLongest', []) if number(x.get('readTime')) and x.get('book', {}).get('bookId')}
    candidates = {key: {**shelf.get(key, {}), **item['book']} for key, item in ranked.items()}
    status = {}
    for item in snapshot.get('non_ranked_progress', []):
        key = str(item.get('book_id') or '')
        status[key] = item
        date = date_value(item.get('last_read'))
        if item.get('is_started') and date and int(date[:4]) == data['year']:
            candidates.setdefault(key, {**shelf.get(key, {}), 'title': item.get('title')})
    for key, row in candidates.items():
        b = existing.get(key)
        if not b:
            b = adapt_data({'year': data['year'], 'books': [{'book_id': key, 'title': row.get('title'), 'author': row.get('author')}], 'summary': {}})['books'][0]
            b['selected'] = False
            existing[key] = b
        category = row.get('category')
        if isinstance(category, str) and category:
            b['source_category'] = category
            b['category'] = re.split(r'[-/]', category)[0].strip() or '未分类'
        elif isinstance(category, dict):
            b['category'] = str(category.get('title') or category.get('categoryTitle') or '未分类')
        info = status.get(key, {})
        progress = number(info.get('progress'))
        if progress is not None and progress <= 100:
            b['progress'] = progress
            b['status'] = 'finished' if progress == 100 else 'reading' if progress > 0 else 'unknown'
        if key in ranked:
            b['reading_seconds'] = number(ranked[key]['readTime'])
        if info.get('finished_on'):
            b['finish_date'] = date_value(info['finished_on'])
    data['books'] = list(existing.values())
    data['coverage']['annual_books'] = data['summary']['read']
    data['coverage']['loaded_books'] = len(existing)
    data['coverage']['complete'] = len(existing) == data['coverage']['annual_books']
    return data


def merge_materials(data, materials):
    """Fill known books only. Failed collection never means an empty notebook."""
    if materials.get('year') != data['year']:
        raise ValueError('书籍材料年份与年鉴不一致')
    existing = {b['book_id']: b for b in data['books']}
    for row in materials.get('books', []):
        b = existing.get(str(row.get('book_id') or ''))
        if b is None:
            continue
        coverage = row.get('collection') or {}
        for key in ('title', 'author', 'intro'):
            if row.get(key):
                b[key] = str(row[key])
        if coverage.get('progress') == 'complete':
            progress = number(row.get('progress'))
            if progress is not None and progress <= 100:
                b['progress'] = progress
                b['status'] = 'finished' if progress == 100 else 'reading' if progress > 0 else 'unknown'
            finish = date_value(row.get('finish_time'))
            if finish and int(finish[:4]) == data['year']:
                b['finish_date'] = finish
        note_year = None if row.get('notes_scope') == 'all_time' else data['year']
        for key in ('highlights', 'thoughts'):
            if coverage.get(key) == 'complete':
                b[key] = notes(row.get(key, []), note_year)
        b['note_coverage'] = {'scope': 'all_time' if note_year is None else 'year',
                              'highlights': 'complete' if coverage.get('highlights') == 'complete' else 'unverified',
                              'thoughts': 'complete' if coverage.get('thoughts') == 'complete' else 'unverified',
                              'collected_on': date_value(row.get('collected_on'))}
    data['material_coverage'] = {'books_with_checked_highlights': sum(b.get('note_coverage', {}).get('highlights') == 'complete' for b in data['books']),
                                 'books_with_checked_thoughts': sum(b.get('note_coverage', {}).get('thoughts') == 'complete' for b in data['books']),
                                 'current_finished': sum(b['status'] == 'finished' for b in data['books']),
                                 'states_collected_on': max((b.get('note_coverage', {}).get('collected_on') or '' for b in data['books']), default='')}
    return data


def embed_image(path):
    path = Path(path)
    content = path.read_bytes()
    if content.startswith(b'\x89PNG\r\n\x1a\n'):
        mime = 'image/png'
    elif content.startswith(b'\xff\xd8\xff'):
        mime = 'image/jpeg'
    elif content[:4] == b'RIFF' and content[8:12] == b'WEBP':
        mime = 'image/webp'
    else:
        raise ValueError(f'书封须为PNG/JPEG/WebP：{path.name}')
    if len(content) > 8 * 1024 * 1024:
        raise ValueError('单张书封不能超过8MB')
    return 'data:' + mime + ';base64,' + base64.b64encode(content).decode('ascii')


def build_html(data, output, covers=None, art_assets=None, require_all_covers=False):
    """Whitelist data at adapter boundary; no raw payload embedded."""
    for b in data['books']:
        for removed in ('review', 'full_text_review', 'full_text_search'):
            b.pop(removed, None)
        if (covers or {}).get(b['book_id']):
            b['cover'] = embed_image(covers[b['book_id']])
    missing = sum(not b['cover'] for b in data['books'])
    if require_all_covers and missing:
        raise ValueError(f'有{missing}本书缺少真实封面，请补采后再生成正式年鉴')
    serialized = json.dumps(data, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    if re.search(r'wrk-[A-Za-z0-9_-]{8,}', serialized):
        raise ValueError('交付内容中检测到密钥格式，请移除后重试')
    template = (ROOT / 'assets' / 'reading-template.html').read_text('utf-8')
    # Art belongs to presentation, never the user's exported reading JSON.
    unknown = set(art_assets or {}) - {'hero', 'reading', 'rhythm'}
    if unknown:
        raise ValueError('未知艺术素材字段：' + ', '.join(sorted(unknown)))
    art = {name: embed_image((art_assets or {}).get(name) or ROOT / 'assets' / 'yearbook-art' / file)
           for name, file in [('hero', 'hero-book.png'), ('reading', 'reading.png'), ('rhythm', 'rhythm.png')]}
    fonts, font_info = font_css(data)
    replacements = {'__DATA__': serialized, '__FONTS__': fonts, '__STYLE__': (ROOT / 'assets' / 'reading-app.css').read_text('utf-8') + '\n' + (ROOT / 'assets' / 'reading-art.css').read_text('utf-8') + '\n' + (ROOT / 'assets' / 'reading-refined.css').read_text('utf-8') + '\n' + (ROOT / 'assets' / 'reading-share.css').read_text('utf-8'),
                    '__ART__': json.dumps(art),
                    '__APP__': (ROOT / 'assets' / 'vendor' / 'html-to-image.js').read_text('utf-8').replace('//# sourceMappingURL=html-to-image.js.map', '') + '\n' + (ROOT / 'assets' / 'reading-share-art.js').read_text('utf-8') + '\n' + (ROOT / 'assets' / 'reading-app.js').read_text('utf-8'),
                    '__LICENSE__': html.escape((ROOT / 'assets' / 'lieflat-LICENSE.txt').read_text('utf-8')),
                    '__FONTLICENSE__': html.escape((ROOT / 'assets' / 'vendor' / 'Noto-OFL.txt').read_text('utf-8')),
                    '__EXPORTLICENSE__': html.escape((ROOT / 'assets' / 'vendor' / 'html-to-image-LICENSE.txt').read_text('utf-8'))}
    # One-pass replacement: user text may itself contain template delimiters.
    page = re.sub(r'__(?:DATA|FONTS|STYLE|APP|LICENSE|FONTLICENSE|EXPORTLICENSE|ART)__', lambda m: replacements[m.group()], template)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, 'utf-8')
    return {'output': str(output), 'bytes': output.stat().st_size, 'books': len(data['books']), 'coverage': data['coverage'], 'font': font_info}


def main():
    parser = argparse.ArgumentParser(description='生成单文件离线阅读年鉴，保留原分享与atlas流程')
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--year', type=int)
    parser.add_argument('--annual-snapshot', type=Path)
    parser.add_argument('--covers', type=Path, help='JSON：book_id到本地书封路径，路径相对该JSON')
    parser.add_argument('--art-assets', type=Path, help='JSON：hero/reading/rhythm到本地透明图片路径，可按认可方向替换')
    parser.add_argument('--book-materials', type=Path, help='补采的进度与完整笔记材料，不能用精选摘录冒充完整采集')
    parser.add_argument('--require-all-covers', action='store_true', help='正式年鉴缺任一本封面时停止，不覆盖上一版')
    args = parser.parse_args()
    raw = json.loads(args.input.read_text('utf-8-sig'))
    data = adapt_data(raw, args.year)
    if args.annual_snapshot:
        merge_annual(data, json.loads(args.annual_snapshot.read_text('utf-8-sig')))
    if args.book_materials:
        merge_materials(data, json.loads(args.book_materials.read_text('utf-8-sig')))
    covers = {}
    if args.covers:
        covers = {k: args.covers.parent / v for k, v in json.loads(args.covers.read_text('utf-8-sig')).items()}
    art_assets = {}
    if args.art_assets:
        art_assets = {k: args.art_assets.parent / v for k, v in json.loads(args.art_assets.read_text('utf-8-sig')).items()}
    print(json.dumps(build_html(data, args.output, covers, art_assets, args.require_all_covers), ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
