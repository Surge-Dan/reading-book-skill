"""Complete materials for an already selected yearbook, not the whole shelf.

Raw API responses and covers belong in a private output directory. Credentials
are read from the environment and never written to caches or status reports.
"""
import argparse
import hashlib
import json
import os
import shutil
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from build_reading_html import adapt_data, embed_image, merge_annual
from collect_weread_data import WeReadError, gateway_call
from html_contract import atomic_json, valid_response
from build_reading_html import TZ


CACHE_VERSION = 1


class PartialReviews(WeReadError):
    def __init__(self,message,rows):
        super().__init__(message,'pagination');self.rows=rows


def cached_response(api, cache):
    """Read legacy raw caches too; reject malformed or incompatible entries."""
    cache = Path(cache)
    try:
        meta = cache.with_suffix(cache.suffix + '.meta.json')
        if meta.exists():
            info = json.loads(meta.read_text('utf-8'))
            if info.get('version') != CACHE_VERSION or info.get('api') != api:
                return None
        value = json.loads(cache.read_text('utf-8'))
        return value if valid_response(api, value) else None
    except (ValueError, OSError, AttributeError):
        return None


def cache_expired(cache):
    """Daily reading records must refresh; retain old cache only for recovery."""
    meta = Path(cache).with_suffix(Path(cache).suffix + '.meta.json')
    if not meta.exists():
        return False  # Legacy cache in the current dated directory.
    try:
        fetched = datetime.fromisoformat(json.loads(meta.read_text('utf-8'))['fetched_at'])
        return fetched.astimezone(TZ).date() < datetime.now(TZ).date()
    except (ValueError, KeyError, TypeError, OSError):
        return True


def reuse_previous_materials(cache):
    """Seed same-owner/year caches; fresh records are still fetched daily."""
    cache = Path(cache)
    try:
        today = datetime.strptime(cache.name, '%Y-%m-%d').date()
    except ValueError:
        return 0
    if not cache.parent.exists():
        return 0
    candidates = []
    for previous in cache.parent.iterdir():
        if not previous.is_dir():
            continue
        try:
            day = datetime.strptime(previous.name, '%Y-%m-%d').date()
        except ValueError:
            continue
        if day < today:
            candidates.append(previous)
    if not candidates:
        return 0
    previous = max(candidates, key=lambda p: p.name)
    copied = 0
    for directory, pattern in [('raw', '*.json'), ('covers', '*.image')]:
        for source in (previous / directory).glob(pattern):
            if directory == 'raw' and source.name.endswith('.meta.json'):
                continue
            target = cache / directory / source.name
            if target.exists():
                continue
            if directory == 'covers':
                try:
                    embed_image(source)
                except (ValueError, OSError):
                    continue
            else:
                source_meta = source.with_suffix(source.suffix + '.meta.json')
                # Unstamped legacy responses cannot be silently marked fresh.
                if not source_meta.is_file():
                    continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            if directory == 'raw':
                shutil.copy2(source_meta, target.with_suffix(target.suffix + '.meta.json'))
            copied += 1
    return copied


def call(api, params, api_key, cache, stopped, refresh=False):
    if stopped.is_set():
        raise WeReadError('鉴权或版本问题，已停止后续采集', 'stopped')
    cached = cached_response(api, cache)
    if cached is not None and not refresh and not cache_expired(cache):
        return cached
    try:
        result = gateway_call(api, params, api_key, timeout=20, retries=1)
        if not valid_response(api, result):
            raise WeReadError('接口响应结构或业务状态异常', 'schema')
    except WeReadError as error:
        if error.terminal:
            stopped.set()
        elif cached is not None:
            return {**cached, '_cache_status': 'stale'}
        raise
    atomic_json(cache, result)
    atomic_json(cache.with_suffix(cache.suffix + '.meta.json'),
                {'version': CACHE_VERSION, 'api': api, 'fetched_at': datetime.now(TZ).isoformat()})
    return result


def reviews(book_id, api_key, cache, stopped, refresh=False):
    cursor, seen, rows, stale = 0, set(), [], False
    def incomplete(message):
        raise PartialReviews(message,rows) if rows else WeReadError(message)
    for _ in range(20):
        if cursor in seen:
            incomplete('想法分页游标重复')
        seen.add(cursor)
        try:
            page = call('/review/list/mine', {'bookid': book_id, 'count': 50, 'synckey': cursor}, api_key,
                        cache.with_name(cache.stem + '-' + str(cursor) + '.json'), stopped, refresh=refresh)
        except WeReadError as error:
            if error.terminal:raise
            incomplete('想法分页中断，已保留取得的部分')
        if not isinstance(page.get('reviews'), list):
            incomplete('个人想法响应缺少reviews列表')
        rows.extend(page.get('reviews', []))
        stale = stale or page.get('_cache_status') == 'stale'
        if not page.get('hasMore'):
            return {'reviews': rows, 'hasMore': 0, **({'_cache_status':'stale'} if stale else {})}
        cursor = page.get('synckey')
        if cursor is None:
            incomplete('想法分页缺少游标')
    incomplete('想法超过20页，本次停止扩批；已保留取得的部分')


def download_cover(url, target, refresh=False):
    if target.exists():
        try:
            embed_image(target)
            if not refresh:
                return target
        except ValueError:
            pass
    parts = urlsplit(url)
    allowed = {'cdn.weread.qq.com', 'res.weread.qq.com', 'wfqqreader-1252317822.image.myqcloud.com'}
    if parts.scheme != 'https' or parts.hostname not in allowed:
        raise ValueError('封面来源须为已核验的微信读书HTTPS资源域名')
    req = urllib.request.Request(url, headers={'User-Agent': 'reading-yearbook-skill/1.0'})
    with urllib.request.urlopen(req, timeout=20) as response:
        final = urlsplit(response.geturl())
        if final.scheme != 'https' or final.hostname not in allowed:
            raise ValueError('封面重定向到未经核验的来源')
        content = response.read(8*1024*1024 + 1)
    if len(content) > 8*1024*1024:
        raise ValueError('封面超过8MB')
    temporary = target.with_suffix('.tmp')
    temporary.write_bytes(content)
    try:
        embed_image(temporary)
    except ValueError:
        temporary.unlink()
        raise
    temporary.replace(target)
    return target


def collect(data, snapshot, output, api_key, legacy_cache=None, refresh=False):
    output = Path(output).resolve(); output.mkdir(parents=True, exist_ok=True)
    cache = output/'raw';cache.mkdir(exist_ok=True)
    cover_dir = output/'covers';cover_dir.mkdir(exist_ok=True)
    shelf = {str(b['bookId']): b for b in snapshot.get('shelf', {}).get('books', [])}
    stopped = threading.Event()

    def one(book):
        if stopped.is_set():raise WeReadError('已停止后续采集', 'stopped')
        book_id = book['book_id']; safe = hashlib.sha256(book_id.encode()).hexdigest()[:20]
        row = {'book_id': book_id, 'title': book['title'], 'collected_on': datetime.now(TZ).strftime('%Y-%m-%d'),
               'notes_scope': 'all_time', 'collection': {}, 'errors': []}
        responses = {}
        if book.get('kind') == 'audio':
            row.update({k: book.get(k) for k in ('title','author','intro','category','deep_link')})
            row.update({'highlights':[], 'thoughts':[], 'notes_scope':'all_time'})
            row['collection'] = {'info':'complete', 'progress':'unsupported', 'highlights':'unsupported', 'thoughts':'unsupported'}
            try:
                row['cover_path'] = str(download_cover(book.get('cover_url',''),cover_dir/f'{safe}.image',refresh=refresh))
                row['collection']['cover'] = 'complete'
            except Exception as error:
                row['errors'].append({'scope':'cover','message':type(error).__name__})
            return row
        for kind, api, params in [('info','/book/info',{'bookId':book_id}),
                                  ('progress','/book/getprogress',{'bookId':book_id}),
                                  ('highlights','/book/bookmarklist',{'bookId':book_id})]:
            legacy = Path(legacy_cache)/f'{book_id}-{kind}.json' if legacy_cache else None
            try:
                responses[kind] = json.loads(legacy.read_text('utf-8')) if legacy and legacy.exists() and not refresh else call(api,params,api_key,cache/f'{safe}-{kind}.json',stopped,refresh=refresh)
                reply = responses[kind]
                if kind == 'highlights' and not isinstance(reply.get('updated'), list):
                    raise WeReadError('划线响应缺少updated列表')
                if kind == 'progress' and not isinstance(reply.get('book'), dict):
                    raise WeReadError('进度响应缺少book对象')
                if kind == 'info' and not (reply.get('title') or (reply.get('book') or {}).get('title')):
                    raise WeReadError('书籍信息响应缺少书名')
                row['collection'][kind] = 'stale' if reply.get('_cache_status') == 'stale' else 'complete'
                if row['collection'][kind] == 'stale':
                    row['errors'].append({'scope':kind, 'message':'刷新失败，保留上次材料'})
            except (WeReadError, ValueError) as error:
                row['collection'][kind] = 'failed';row['errors'].append({'scope':kind,'message':str(error)})
                responses.pop(kind, None)
                if isinstance(error,WeReadError) and error.terminal:
                    raise
        try:
            legacy = Path(legacy_cache)/f'{book_id}-thoughts.json' if legacy_cache else None
            cached = json.loads(legacy.read_text('utf-8')) if legacy and legacy.exists() and not refresh else None
            responses['thoughts'] = cached if cached is not None and not cached.get('hasMore') else reviews(book_id,api_key,cache/f'{safe}-thoughts.json',stopped,refresh=refresh)
            if not isinstance(responses['thoughts'].get('reviews'), list):
                raise WeReadError('个人想法缓存缺少reviews列表')
            row['collection']['thoughts'] = 'stale' if responses['thoughts'].get('_cache_status') == 'stale' else 'complete'
            if row['collection']['thoughts'] == 'stale':
                row['errors'].append({'scope':'thoughts','message':'刷新失败，保留上次材料'})
        except PartialReviews as error:
            responses['thoughts']={'reviews':error.rows}
            row['collection']['thoughts']='partial';row['errors'].append({'scope':'thoughts','message':str(error)})
        except (WeReadError, ValueError) as error:
            row['collection']['thoughts'] = 'failed';row['errors'].append({'scope':'thoughts','message':str(error)})
            responses.pop('thoughts',None)
            if isinstance(error,WeReadError) and error.terminal:
                raise
        info = responses.get('info', {}); info = info.get('book') or info
        row.update({k: info[k] for k in ['title','author','intro','category','translator','publisher','isbn','deepLink'] if info.get(k)})
        progress = responses.get('progress', {}).get('book', {})
        if 'progress' in progress: row['progress'] = progress['progress']
        if 'isStartReading' in progress: row['is_started'] = bool(progress['isStartReading'])
        if progress.get('finishTime'): row['finish_time'] = progress['finishTime']
        chapter_rows=responses.get('highlights', {}).get('chapters') or []
        chapters = {str(c['chapterUid']): str(c.get('title') or '') for c in chapter_rows if isinstance(c,dict) and c.get('chapterUid') is not None}
        row['highlights'] = [{'text': n.get('markText',''), 'created_at': n.get('createTime'), 'source_id': n.get('bookmarkId'),
                              'chapter_uid': n.get('chapterUid'), 'chapter_title':chapters.get(str(n.get('chapterUid')), ''), 'range':n.get('range')}
                             for n in responses.get('highlights', {}).get('updated', []) if n.get('markText')]
        row['thoughts'] = []
        for wrapped in responses.get('thoughts', {}).get('reviews', []):
            n = wrapped.get('review') or wrapped
            if n.get('content'):
                row['thoughts'].append({'text':n['content'], 'created_at':n.get('createTime'), 'source_id':n.get('reviewId'),
                                        'chapter_uid':n.get('chapterUid'), 'chapter_title':n.get('chapterName') or chapters.get(str(n.get('chapterUid')),''), 'quote':n.get('abstract',''), 'range':n.get('range')})
        url = info.get('cover') or shelf.get(book_id, {}).get('cover')
        if stopped.is_set():raise WeReadError('已停止后续采集', 'stopped')
        try:
            if not url: raise ValueError('来源没有返回封面地址')
            row['cover_path'] = str(download_cover(url,cover_dir/f'{safe}.image',refresh=refresh))
            row['collection']['cover'] = 'complete'
        except Exception as error:
            row['collection']['cover'] = 'failed';row['errors'].append({'scope':'cover','message':type(error).__name__})
            old_cover=cover_dir/f'{safe}.image'
            if old_cover.exists():
                try:
                    embed_image(old_cover);row['cover_path']=str(old_cover);row['collection']['cover']='stale'
                except ValueError:
                    pass
        print(json.dumps({'book_id':book_id,'collection':row['collection'],'highlights':len(row['highlights']),'thoughts':len(row['thoughts'])},ensure_ascii=False),flush=True)
        return row

    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(one, data['books']))
    materials = {'year':data['year'], 'books':rows}
    atomic_json(output/'materials.json',materials)
    covers = {b['book_id']: b['cover_path'] for b in rows if b.get('cover_path')}
    atomic_json(output/'covers.json',covers)
    complete = all(not b['errors'] for b in rows)
    print(json.dumps({'complete':complete,'books':len(rows),'covers':len(covers),'highlights':sum(len(b['highlights']) for b in rows),'thoughts':sum(len(b['thoughts']) for b in rows)},ensure_ascii=False))
    return complete


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description='补齐已确认年鉴书目的封面、进度、划线和个人想法；复用缓存')
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--annual-snapshot',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--legacy-cache',type=Path)
    args=parser.parse_args()
    key=os.environ.get('WEREAD_API_KEY')
    if not key: raise SystemExit('WEREAD_API_KEY未设置')
    data=adapt_data(json.loads(args.input.read_text('utf-8-sig')))
    snapshot=json.loads(args.annual_snapshot.read_text('utf-8-sig'));merge_annual(data,snapshot)
    raise SystemExit(0 if collect(data,snapshot,args.output,key,args.legacy_cache) else 3)
