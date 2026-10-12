"""Current-chat handoff; never invokes a model executable or provider API."""
import hashlib
import json
import threading
import time
import uuid
from pathlib import Path
from html_contract import atomic_json
_UNSET = object()


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()).hexdigest()

class AgentRunner:
    def __init__(self, timeout=180, clock=time.monotonic):
        if type(timeout) is not int or not 30 <= timeout <= 900:
            raise ValueError('模型阶段超时应为 30 到 900 秒')
        self.timeout = timeout
        self.clock = clock
        self.condition = threading.Condition(threading.RLock())
        self.identity = None
        self.pending = None
        self.history = {}
        self.revoked = None
        self.cancel_event = None

    def bind(self, directory, job_id, identity, notify=None, cancel_event=None):
        if not isinstance(identity, dict) or any(not isinstance(identity.get(k), str) or not identity[k].strip() or len(identity[k]) > 200 for k in ('session', 'host', 'model')):
            raise ValueError('请声明当前 Agent 的 session、host、model；未知模型填 unknown')
        bound = AgentRunner(self.timeout, self.clock)
        bound.identity = {k: identity[k] for k in ('session', 'host', 'model')}
        bound.directory = Path(directory).resolve() / '.agent' / uuid.uuid4().hex
        bound.directory.mkdir(parents=True)
        bound.attempt = bound.directory.name
        bound.job_id = job_id
        bound.notify = notify
        bound.cancel_event = cancel_event
        bound.deadline = bound.clock() + bound.timeout
        return bound

    def _check(self, owner=_UNSET):
        if not self.identity:
            raise ValueError('任务尚未被当前 Agent 领取')
        if owner is not _UNSET and owner != self.identity['session']:
            raise ValueError('任务由另一个对话持有')
        if self.cancel_event and self.cancel_event.is_set():
            self.revoke('已取消；请同时停止对话中的分析')
        if not self.revoked and self.clock() >= self.deadline:
            self.revoke('当前 Agent 领取已过期，请重试任务')
        if self.revoked:
            raise InterruptedError(self.revoked)

    def prepare(self, stage, context, cache_key):
        with self.condition:
            self._check()
            if self.pending:
                raise ValueError('上一阶段尚未核验')
            self.stage = stage
            self.context = context
            self.cache_key = cache_key

    def generate(self, prompt, schema=None, cancel_event=None):
        with self.condition:
            if cancel_event is not None: self.cancel_event = cancel_event
            self._check()
            request = {'job_id': self.job_id, 'attempt_id': self.attempt,
                       'request_id': uuid.uuid4().hex, 'sequence': len(self.history) + 1,
                       'stage': self.stage, 'context': self.context, 'cache_key': self.cache_key,
                       'execution_identity': self.identity, 'prompt': prompt, 'schema': schema,
                       'lease_seconds': self.timeout,
                       'input_digest': digest({'prompt': prompt, 'schema': schema})}
            atomic_json(self.directory / 'request.json', request)
            self.pending = {'request': request, 'answer': None, 'digest': None, 'status': 'waiting'}
            self.deadline = self.clock() + self.timeout
            if self.notify:
                self.notify({'state': 'awaiting_response', 'message': '等待当前 Agent 分析并提交本阶段'})
            while self.pending['answer'] is None:
                if cancel_event and cancel_event.is_set():
                    self.revoke('已取消；请同时停止对话中的分析')
                self._check()
                self.condition.wait(.1)
            return self.pending['answer']

    def next(self, owner):
        with self.condition:
            self._check(owner)
            if not self.pending:
                return None
            return json.loads(json.dumps(self.pending['request'], ensure_ascii=False))

    def submit(self, owner, request_id, answer):
        with self.condition:
            self._check(owner)
            if not isinstance(answer, dict):
                raise ValueError('阶段输出必须为 JSON 对象')
            fingerprint = digest(answer)
            record = self.history.get(request_id)
            if record:
                if record['status'] != 'accepted' or record['digest'] != fingerprint:
                    raise ValueError('输出冲突或上一阶段核验失败')
                return 'accepted'
            if not self.pending or self.pending['request']['request_id'] != request_id:
                raise ValueError('请求不存在或已过期')
            if self.pending['digest'] and self.pending['digest'] != fingerprint:
                raise ValueError('同一请求禁止提交不同输出')
            if self.pending['digest']:
                return self.pending['status']
            self.pending.update(answer=json.loads(json.dumps(answer)), digest=fingerprint, status='submitted')
            self.deadline = self.clock() + self.timeout
            atomic_json(self.directory / (request_id + '-candidate.json'), answer)
            self.condition.notify_all()
            return 'submitted'

    def acknowledge(self, accepted, error=None):
        with self.condition:
            self._check()
            if self.pending:
                self.history[self.pending['request']['request_id']] = {
                    'digest': self.pending['digest'], 'status': 'accepted' if accepted else 'rejected', 'error': error}
                self.pending = None
            if self.notify:
                self.notify({'state': 'running', 'message': '阶段已核验，准备下一阶段'})
            self.condition.notify_all()

    def commit(self, callback):
        """Lease check and cache publication share the request's critical section."""
        with self.condition:
            self._check()
            callback()
            self.acknowledge(True)

    def check(self):
        with self.condition:
            self._check()

    def revoke(self, reason):
        with self.condition:
            self.revoked = reason
            self.condition.notify_all()

    def info(self):
        info = {'name': 'agent', 'available': True, 'timeout': self.timeout,
                'mode': 'current-agent-instructed-tools'}
        if self.identity:
            info['execution_identity'] = dict(self.identity)
        return info
