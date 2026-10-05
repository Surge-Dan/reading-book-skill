"""Complete materials for an already selected yearbook, not the whole shelf.

Raw API responses and covers belong in a private output directory. Credentials
are read from the environment and never written to caches or status reports.
"""
import argparse
import hashlib
import json
import os
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from build_reading_html import adapt_data, embed_image, merge_annual
from collect_weread_data import WeReadError, gateway_call


def call(api, params, api_key, cache, stopped):
    if cache.exists():
        return json.loads(cache.read_text('utf-8'))
    if stopped.is_set():
        raise WeReadError('鉴权或版本问题，已停止后续采集')
    try:
        result = gateway_call(api, params, api_key, timeout=20, retries=1)
        if result.get('errcode') not in (None, 0):
            raise WeReadError('接口业务错误：' + str(result['errcode']))
    except WeReadError as error:
        if any(word in str(error) for word in ('HTTP 401', 'HTTP 403', 'HTTP 422', 'HTTP 499', '升级')):
            stopped.set()
        raise
    cache.write_text(json.dumps(result, ensure_ascii=False), 'utf-8')
    return result


def reviews(book_id, api_key, cache, stopped):
    cursor, seen, rows = 0, set(), []
    for _ in range(20):
        if cursor in seen:
            raise WeReadError('想法分页游标重复')
        seen.add(cursor)
        page = call('/review/list/mine', {'bookid': book_id, 'count': 50, 'synckey': cursor}, api_key,
                    cache.with_name(cache.stem + '-' + str(cursor) + '.json'), stopped)
        if not isinstance(page.get('reviews'), list):
            raise WeReadError('个人想法响应缺少reviews列表')
        rows.extend(page.get('reviews', []))
        if not page.get('hasMore'):
            return {'reviews': rows, 'hasMore': 0}
        cursor = page.get('synckey')
        if cursor is None:
            raise WeReadError('想法分页缺少游标')
    raise WeReadError('想法超过20页，本次停止扩批')


def download_cover(url, target):
    if target.exists():
        embed_image(target)
        return target
    parts = urlsplit(url)
    allowed = {'cdn.weread.qq.com', 'res.weread.qq.com', 'wfqqreader-1252317822.image.myqcloud.com'}
    if parts.scheme != 'https' or parts.hostname not in allowed:
        raise ValueError('封面来源须为已核验的微信读书HTTPS资源域名')
    req = urllib.request.Request(url, headers={'User-Agent': 'reading-yearbook-skill/1.0'})
    with urllib.request.urlopen(req, timeout=20) as response:
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


def collect(data, snapshot, output, api_key, legacy_cache=None):
    output = Path(output).resolve(); output.mkdir(parents=True, exist_ok=True)
    cache = output/'raw';cache.mkdir(exist_ok=True)
    cover_dir = output/'covers';cover_dir.mkdir(exist_ok=True)
    shelf = {str(b['bookId']): b for b in snapshot.get('shelf', {}).get('books', [])}
    stopped = threading.Event()

    def one(book):
        book_id = book['book_id']; safe = hashlib.sha256(book_id.encode()).hexdigest()[:20]
        row = {'book_id': book_id, 'title': book['title'], 'collected_on': datetime.now().strftime('%Y-%m-%d'),
               'notes_scope': 'all_time', 'collection': {}, 'errors': []}
        responses = {}
        for kind, api, params in [('info','/book/info',{'bookId':book_id}),
                                  ('progress','/book/getprogress',{'bookId':book_id}),
                                  ('highlights','/book/bookmarklist',{'bookId':book_id})]:
            legacy = Path(legacy_cache)/f'{book_id}-{kind}.json' if legacy_cache else None
            try:
                responses[kind] = json.loads(legacy.read_text('utf-8')) if legacy and legacy.exists() else call(api,params,api_key,cache/f'{safe}-{kind}.json',stopped)
                reply = responses[kind]
                if kind == 'highlights' and not isinstance(reply.get('updated'), list):
                    raise WeReadError('划线响应缺少updated列表')
                if kind == 'progress' and not isinstance(reply.get('book'), dict):
                    raise WeReadError('进度响应缺少book对象')
                if kind == 'info' and not (reply.get('title') or (reply.get('book') or {}).get('title')):
                    raise WeReadError('书籍信息响应缺少书名')
                row['collection'][kind] = 'complete'
            except (WeReadError, ValueError) as error:
                row['collection'][kind] = 'failed';row['errors'].append({'scope':kind,'message':str(error)})
        try:
            legacy = Path(legacy_cache)/f'{book_id}-thoughts.json' if legacy_cache else None
            cached = json.loads(legacy.read_text('utf-8')) if legacy and legacy.exists() else None
            responses['thoughts'] = cached if cached is not None and not cached.get('hasMore') else reviews(book_id,api_key,cache/f'{safe}-thoughts.json',stopped)
            if not isinstance(responses['thoughts'].get('reviews'), list):
                raise WeReadError('个人想法缓存缺少reviews列表')
            row['collection']['thoughts'] = 'complete'
        except (WeReadError, ValueError) as error:
            row['collection']['thoughts'] = 'failed';row['errors'].append({'scope':'thoughts','message':str(error)})
        info = responses.get('info', {}); info = info.get('book') or info
        row.update({k: info[k] for k in ['title','author','intro'] if info.get(k)})
        progress = responses.get('progress', {}).get('book', {})
        if 'progress' in progress: row['progress'] = progress['progress']
        if progress.get('finishTime'): row['finish_time'] = progress['finishTime']
        chapters = {str(c['chapterUid']): str(c.get('title') or '') for c in responses.get('highlights', {}).get('chapters', [])}
        row['highlights'] = [{'text': n.get('markText',''), 'created_at': n.get('createTime'), 'source_id': n.get('bookmarkId'),
                              'chapter_uid': n.get('chapterUid'), 'chapter_title':chapters.get(str(n.get('chapterUid')), '')}
                             for n in responses.get('highlights', {}).get('updated', []) if n.get('markText')]
        row['thoughts'] = []
        for wrapped in responses.get('thoughts', {}).get('reviews', []):
            n = wrapped.get('review') or wrapped
            if n.get('content'):
                row['thoughts'].append({'text':n['content'], 'created_at':n.get('createTime'), 'source_id':n.get('reviewId'),
                                        'chapter_uid':n.get('chapterUid'), 'chapter_title':n.get('chapterName',''), 'quote':n.get('abstract','')})
        url = info.get('cover') or shelf.get(book_id, {}).get('cover')
        try:
            if not url: raise ValueError('来源没有返回封面地址')
            row['cover_path'] = str(download_cover(url,cover_dir/f'{safe}.image'))
            row['collection']['cover'] = 'complete'
        except Exception as error:
            row['collection']['cover'] = 'failed';row['errors'].append({'scope':'cover','message':type(error).__name__})
        print(json.dumps({'book_id':book_id,'collection':row['collection'],'highlights':len(row['highlights']),'thoughts':len(row['thoughts'])},ensure_ascii=False),flush=True)
        return row

    with ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(one, data['books']))
    materials = {'year':data['year'], 'books':rows}
    (output/'materials.json').write_text(json.dumps(materials,ensure_ascii=False,indent=2),'utf-8')
    covers = {b['book_id']: b['cover_path'] for b in rows if b.get('cover_path')}
    (output/'covers.json').write_text(json.dumps(covers,ensure_ascii=False,indent=2),'utf-8')
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
