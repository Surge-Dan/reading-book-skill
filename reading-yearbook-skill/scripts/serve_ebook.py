"""Loopback-only ebook workbench. Credentials and source books never enter exports."""
from __future__ import annotations

import argparse
import hmac
import json
import os
import re
import secrets
import threading
import uuid
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from html_contract import atomic_json, atomic_text

ROOT = Path(__file__).resolve().parents[1]
MAX_UPLOAD = 32 * 1024 * 1024
EXTENSIONS = {'.txt', '.md', '.epub', '.pdf'}
JOB_ID = re.compile(r'^[a-f0-9]{32}$')
ACTIVE = {'queued', 'running'}
STATES = ACTIVE | {'needs_approval', 'completed', 'failed', 'cancelled', 'interrupted'}


def public_error(error):
    if isinstance(error, OSError):
        return '本地文件读写失败，请让助手检查输出目录与 Skill 安装资源'
    message = str(error)[:1000]
    message = re.sub(r"(?:[A-Za-z]:[\\/]|\\\\)[^\n\"']+", '[本地路径]', message)
    message = re.sub(r"(?<![\w:])/(?:[^\s/]+/)+[^\s,;]*", '[本地路径]', message)
    return message


def valid_saved_job(job, expected_id):
    if not isinstance(job, dict) or job.get('id') != expected_id or job.get('state') not in STATES:
        return False
    if any(not isinstance(job.get(k), str) for k in ('filename', 'created_at', 'suffix', 'focus', 'stage', 'message')):
        return False
    if job['suffix'] not in EXTENSIONS or len(job['focus']) > 1000:
        return False
    if any(type(job.get(k)) is not int or job[k] < 0 for k in ('completed', 'total')):
        return False
    if job['state'] == 'completed' and (not isinstance(job.get('analysis'), dict) or not isinstance(job.get('digest'), str)):
        return False
    return True


def safe_json(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False).replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')


def asset(name):
    path = ROOT / 'assets' / name
    return path.read_text('utf-8') if path.is_file() else ''


def workbench_page(config=None, result=None, yearbook=None):
    section = asset('ebook-section.html') or '<main id="ebook"><h1>电子书精华</h1></main>'
    css = asset('ebook-app.css')
    if yearbook:
        page = Path(yearbook).read_text('utf-8')
        if 'id="ebook"' not in page:
            page = page.replace('</main>', section + '</main>', 1)
        if 'ebook-app-mounted' not in page:
            page = page.replace('</body>', '<script id="ebook-app-mounted">' + asset('ebook-app.js') + '</script></body>', 1)
        page = page.replace('</head>', '<style>' + css + '</style></head>', 1)
    else:
        page = ('<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
                '<meta name="viewport" content="width=device-width,initial-scale=1">'
                '<title>年年阅 · 电子书精华</title><style>' + asset('reading-app.css') + '\n' + asset('reading-art.css') + '\n' + css +
                '</style></head><body class="ebook-standalone"><div class="paper"><header class="masthead"><a href="#ebook">年年阅</a>'
                '<span>电子书精华</span></header><main>' + section + '</main></div>'
                '<script>' + asset('reading-share-art.js') + '</script>'
                '<script id="ebook-app-mounted">' + asset('ebook-app.js') + '</script></body></html>')
    # Configuration precedes deferred mounting; data is never executable HTML.
    injection = '<script id="ebook-config">window.EBOOK_CONFIG=' + safe_json(config or {}) + ';window.EBOOK_RESULT=' + safe_json(result) + ';</script>'
    return page.replace('</head>', injection + '</head>', 1)


def offline_page(analysis, digest):
    return workbench_page(result={'analysis': analysis, 'digest': digest})


class BusyError(ValueError):
    pass


class JobStore:
    def __init__(self, output, runner, pipeline=None):
        self.output = Path(output).resolve()
        self.jobs_dir = self.output / '.ebook-workbench' / 'jobs'
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.runner = runner
        self.pipeline = pipeline
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='ebook')
        self.jobs = {}
        self.events = {}
        for state_file in self.jobs_dir.glob('*/state.json'):
            if not JOB_ID.fullmatch(state_file.parent.name):
                continue
            try:
                job = json.loads(state_file.read_text('utf-8'))
                if not valid_saved_job(job, state_file.parent.name):
                    continue
                if job.get('state') in ACTIVE:
                    job.update(state='interrupted', message='上次服务已停止，可重试并复用已完成阶段')
                self.jobs[job['id']] = job
                self._save(job)
            except (ValueError, OSError, TypeError):
                continue

    def _save(self, job):
        atomic_json(self.jobs_dir / job['id'] / 'state.json', job)

    def _job(self, job_id):
        if not JOB_ID.fullmatch(job_id) or job_id not in self.jobs:
            raise KeyError('任务不存在')
        return self.jobs[job_id]

    def get(self, job_id):
        with self.lock:
            return json.loads(json.dumps(self._job(job_id), ensure_ascii=False))

    def state(self):
        with self.lock:
            jobs = sorted(self.jobs.values(), key=lambda j: j['created_at'], reverse=True)[:30]
            return {'runner': self.runner.info(), 'jobs': json.loads(json.dumps(jobs, ensure_ascii=False))}

    def _check_busy(self):
        if any(j['state'] in ACTIVE for j in self.jobs.values()):
            raise BusyError('当前正在蒸馏一本书，请等待完成或先取消')

    def create(self, filename, content, focus=''):
        suffix = Path(filename).suffix.lower()
        if suffix not in EXTENSIONS:
            raise ValueError('支持 EPUB、PDF、TXT 和 MD 文件')
        if not content:
            raise ValueError('文件为空，请选择有正文的电子书')
        if len(content) > MAX_UPLOAD:
            raise ValueError('文件超过 32 MB，请使用文本版或拆分为明确的处理范围')
        if not self.runner.info().get('available'):
            raise ValueError('AI 尚未连接，请让启动 Skill 的助手检查 Codex 或 Claude 登录')
        if len(focus) > 1000:
            raise ValueError('应用方向最多 1000 字')
        with self.lock:
            self._check_busy()
            job_id = uuid.uuid4().hex
            job_dir = self.jobs_dir / job_id
            job_dir.mkdir()
            (job_dir / ('source' + suffix)).write_bytes(content)
            name = filename.replace('\\', '/').rsplit('/', 1)[-1][:200]
            job = {'id': job_id, 'filename': name, 'suffix': suffix, 'focus': focus,
                   'created_at': datetime.now(timezone.utc).isoformat(),
                   'state': 'queued', 'stage': 'queued', 'message': '正在准备正文',
                   'completed': 0, 'total': 0, 'error': None}
            self.jobs[job_id] = job
            self._start(job)
            return self.get(job_id)

    def _start(self, job, allow_large=False):
        event = threading.Event()
        self.events[job['id']] = event
        job.pop('diagnostic', None)
        job.update(state='queued', error=None, message='准备继续处理', allow_large=allow_large)
        self._save(job)
        self.executor.submit(self._run, job['id'], event, allow_large)

    def _run(self, job_id, event, allow_large):
        def progress(update):
            with self.lock:
                if not event.is_set():
                    fields = {k: update[k] for k in ('stage', 'message', 'completed', 'total') if k in update}
                    self.jobs[job_id].update(fields)
                    self._save(self.jobs[job_id])

        with self.lock:
            job = self.jobs[job_id]
            if event.is_set():
                return
            job['state'] = 'running'
            self._save(job)
        job_dir = self.jobs_dir / job_id
        deep = job_dir / 'deep'
        try:
            pipeline = self.pipeline
            if pipeline is None:
                from ebook_pipeline import distill
                pipeline = distill
            result = pipeline(job_dir / ('source' + job['suffix']), deep, self.runner,
                              progress=progress, cancel_event=event, focus=job['focus'], allow_large=allow_large,
                              **({'source_name':job['filename']} if self.pipeline is None else {}))
            if event.is_set():
                raise InterruptedError('已取消')
            digest = (deep / 'DIGEST.md').read_text('utf-8')
            page = offline_page(result, digest)
            with self.lock:
                if event.is_set():
                    raise InterruptedError('已取消')
                atomic_text(deep / 'index.html', page)
                job.update(state='completed', stage='complete', message='精华已生成，请查看来源与核验状态',
                           analysis=result, digest=digest, result_url=f'/results/{job_id}.html', error=None)
        except InterruptedError:
            with self.lock:
                job.update(state='cancelled', message='已取消，可重试继续', error=None)
        except Exception as error:
            with self.lock:
                if event.is_set():
                    job.update(state='cancelled', message='已取消，可重试继续', error=None)
                elif hasattr(error, 'estimate'):
                    job.update(state='needs_approval', stage='budget', message=str(error), estimate=error.estimate)
                else:
                    job.update(state='failed', message='本次蒸馏未完成，可检查提示后重试', error=public_error(error))
                    if hasattr(error, 'diagnostic'):
                        job['diagnostic'] = error.diagnostic
        finally:
            with self.lock:
                self._save(job)

    def action(self, job_id, action):
        with self.lock:
            job = self._job(job_id)
            if action == 'cancel':
                if job['state'] in ACTIVE:
                    self.events[job_id].set()
                    if job['state'] == 'queued':
                        job.update(state='cancelled', message='已取消，可重试继续')
                    else:
                        job['message'] = '正在停止当前阶段…'
                elif job['state'] == 'needs_approval':
                    job.update(state='cancelled', message='已取消')
                else:
                    raise ValueError('该任务已停止')
                self._save(job)
            elif action in {'retry', 'approve'}:
                allowed = {'needs_approval'} if action == 'approve' else {'failed', 'cancelled', 'interrupted'}
                if job['state'] not in allowed:
                    raise ValueError('当前任务状态不支持此操作')
                self._check_busy()
                self._start(job, action == 'approve' or job.get('allow_large', False))
            else:
                raise ValueError('不支持的操作')
            return self.get(job_id)

    def close(self):
        with self.lock:
            for event in self.events.values():
                event.set()
        self.executor.shutdown(wait=True, cancel_futures=True)


def create_server(store, port=0, yearbook=None):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            # Do not log source names, request URLs, tokens, or model payloads.
            pass

        def send(self, status, body, content_type='application/json; charset=utf-8'):
            if not isinstance(body, bytes):
                body = (safe_json(body) if 'json' in content_type else body).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(body)

        def authorize(self, api=False, mutation=False):
            expected_host = f'127.0.0.1:{self.server.server_port}'
            if self.headers.get('Host') != expected_host:
                self.send(403, {'error': '只允许本机工作台访问'})
                return False
            if api and not hmac.compare_digest(self.headers.get('X-Ebook-Token', '').encode('utf-8'), store.token.encode('ascii')):
                self.send(403, {'error': '连接已过期，请重新打开工作台'})
                return False
            if mutation and self.headers.get('Origin') != 'http://' + expected_host:
                self.send(403, {'error': '请从年年阅工作台上传文件'})
                return False
            return True

        def do_GET(self):
            path = urlsplit(self.path).path
            if not self.authorize(path.startswith('/api/')):
                return
            try:
                if path == '/':
                    self.send(200, workbench_page({'apiBase': '', 'token': store.token}, yearbook=yearbook), 'text/html; charset=utf-8')
                elif path == '/api/state':
                    self.send(200, store.state())
                elif path.startswith('/api/jobs/'):
                    self.send(200, {'job': store.get(path.removeprefix('/api/jobs/'))})
                elif path.startswith('/results/') and path.endswith('.html'):
                    job_id = path.removeprefix('/results/').removesuffix('.html')
                    job = store.get(job_id)
                    if job['state'] != 'completed':
                        raise KeyError('精华尚未生成')
                    self.send(200, offline_page(job['analysis'], job['digest']), 'text/html; charset=utf-8')
                else:
                    self.send(404, {'error': '页面不存在'})
            except KeyError as error:
                self.send(404, {'error': str(error).strip("'")})

        def do_POST(self):
            parsed = urlsplit(self.path)
            if not self.authorize(api=True, mutation=True):
                return
            try:
                length = int(self.headers.get('Content-Length', '-1'))
                if length < 0 or length > MAX_UPLOAD:
                    self.send(413, {'error': '文件超过 32 MB 或请求长度无效'})
                    return
                self.connection.settimeout(30)
                body = self.rfile.read(length)
                if len(body) != length:
                    raise ValueError('文件上传不完整，请重新选择文件')
                if parsed.path == '/api/jobs':
                    query = parse_qs(parsed.query)
                    filename = query.get('name', [''])[0]
                    job = store.create(filename, body, query.get('focus', [''])[0])
                    self.send(202, {'job': job})
                else:
                    match = re.fullmatch(r'/api/jobs/([a-f0-9]{32})/(cancel|retry|approve)', parsed.path)
                    if not match:
                        self.send(404, {'error': '操作不存在'})
                        return
                    self.send(202, {'job': store.action(*match.groups())})
            except BusyError as error:
                self.send(409, {'error': str(error)})
            except (ValueError, OSError) as error:
                self.send(400, {'error': public_error(error)})
            except KeyError:
                self.send(404, {'error': '任务不存在'})

    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def main():
    parser = argparse.ArgumentParser(description='由助手启动年年阅电子书工作台')
    parser.add_argument('--output', type=Path, default=Path('output/books'))
    parser.add_argument('--runner', choices=['auto', 'codex', 'claude'], default='auto')
    parser.add_argument('--stage-timeout', type=int, default=180, help='每个模型阶段的等待上限，30–900 秒；不自动重试')
    parser.add_argument('--port', type=int, default=0)
    parser.add_argument('--yearbook', type=Path)
    parser.add_argument('--open', action='store_true')
    args = parser.parse_args()
    from ebook_runner import create_runner
    store = JobStore(args.output, create_runner(args.runner, timeout=args.stage_timeout))
    server = create_server(store, args.port, args.yearbook)
    url = f'http://127.0.0.1:{server.server_port}/'
    atomic_json(store.output / '.ebook-workbench/runtime.json', {'pid': os.getpid(), 'url': url})
    print(safe_json({'url': url, 'pid': os.getpid(), 'runner': store.runner.info()}), flush=True)
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        store.close()


if __name__ == '__main__':
    main()
