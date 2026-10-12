import sys
import tempfile
import unittest
import threading
import time
import json
import urllib.request
import urllib.error
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / 'reading-yearbook-skill/scripts'
sys.path.insert(0, str(SCRIPTS))
from ebook_runner import create_runner
from ebook_agent_bridge import AgentRunner
from serve_ebook import JobStore, create_server
from ebook_agent import Client, local_json, strict_json


class AgentDefaultTests(unittest.TestCase):
    def test_default_needs_no_model_executable(self):
        with patch('ebook_runner.shutil.which', return_value=None):
            info = create_runner().info()
        self.assertEqual(info['name'], 'agent')
        self.assertTrue(info['available'])
        self.assertEqual(info['mode'], 'current-agent-instructed-tools')

    def test_explicit_cli_selection_stays_explicit(self):
        with patch('ebook_runner.shutil.which', return_value=None):
            self.assertEqual(create_runner('auto').info()['name'], 'claude')
            self.assertFalse(create_runner('codex').info()['available'])


class AgentBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.clock = [100.0]
        self.runner = AgentRunner(clock=lambda: self.clock[0]).bind(
            Path(self.tmp.name), 'job', {'session': 'chat-1', 'host': 'test', 'model': 'unknown'})
        self.runner.prepare('stage0', {'source_hash': 'abc', 'focus': ''}, 'digest')
        self.event = threading.Event()
        self.results = []

    def tearDown(self):
        self.runner.revoke('stopped')
        if hasattr(self, 'thread'):
            self.thread.join(2)
        self.tmp.cleanup()

    def start(self):
        def work():
            try:
                self.results.append(self.runner.generate('book data', schema={'type': 'object'}, cancel_event=self.event))
            except Exception as error:
                self.results.append(error)
        self.thread = threading.Thread(target=work)
        self.thread.start()
        for _ in range(100):
            request = self.runner.next('chat-1')
            if request:
                return request
            time.sleep(.005)
        self.fail('No pending stage')

    def test_owner_request_and_idempotent_validated_ack(self):
        request = self.start()
        self.assertEqual(request['stage'], 'stage0')
        self.assertEqual(request['context']['source_hash'], 'abc')
        with self.assertRaises(ValueError):
            self.runner.next('other-chat')
        answer = {'summary': 'candidate'}
        self.assertEqual(self.runner.submit('chat-1', request['request_id'], answer), 'submitted')
        self.thread.join(2)
        self.assertEqual(self.results, [answer])
        self.runner.acknowledge(True)
        self.assertEqual(self.runner.submit('chat-1', request['request_id'], answer), 'accepted')
        with self.assertRaises(ValueError):
            self.runner.submit('chat-1', request['request_id'], {'summary': 'different'})

    def test_cancel_and_expiry_reject_late_output(self):
        request = self.start()
        self.clock[0] += 181
        with self.assertRaises(InterruptedError):
            self.runner.next('chat-1')
        with self.assertRaises(InterruptedError):
            self.runner.submit('chat-1', request['request_id'], {})
        self.thread.join(2)
        self.assertIsInstance(self.results[0], InterruptedError)

    def test_cancel_event_immediately_rejects_late_submit(self):
        request = self.start()
        self.event.set()
        with self.assertRaises(InterruptedError):
            self.runner.submit('chat-1', request['request_id'], {})

    def test_invalid_stage_is_not_accepted(self):
        request = self.start()
        self.runner.submit('chat-1', request['request_id'], {})
        self.thread.join(2)
        self.runner.acknowledge(False, 'schema invalid')
        with self.assertRaises(ValueError):
            self.runner.submit('chat-1', request['request_id'], {})

    def test_unknown_model_cache_identity_is_session_scoped(self):
        other = AgentRunner().bind(Path(self.tmp.name), 'job2',
            {'session': 'chat-2', 'host': 'test', 'model': 'unknown'})
        self.assertNotEqual(self.runner.info()['execution_identity'], other.info()['execution_identity'])

    def test_missing_owner_stale_request_and_expired_cache_commit(self):
        request = self.start()
        with self.assertRaises(ValueError):
            self.runner.next(None)
        with self.assertRaises(ValueError):
            self.runner.submit('chat-1', 'old-attempt', {})
        self.runner.submit('chat-1', request['request_id'], {})
        self.thread.join(2)
        self.clock[0] += 181
        published = []
        with self.assertRaises(InterruptedError):
            self.runner.commit(lambda: published.append(True))
        self.assertEqual(published, [])

    def test_identical_submitted_output_does_not_extend_lease_forever(self):
        request = self.start()
        self.runner.submit('chat-1', request['request_id'], {})
        self.thread.join(2)
        deadline = self.runner.deadline
        self.clock[0] += 10
        self.runner.submit('chat-1', request['request_id'], {})
        self.assertEqual(self.runner.deadline, deadline)


class AgentStoreTests(unittest.TestCase):
    def test_late_release_cannot_cancel_new_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            def pipeline(path, output, runner, **kwargs):
                runner.prepare('test', {'source_hash': 'x'}, 'key')
                runner.generate('data', cancel_event=kwargs['cancel_event'])
            store = JobStore(tmp, AgentRunner(), pipeline=pipeline)
            paused, resume = threading.Event(), threading.Event()
            errors = []
            try:
                job = store.create('book.txt', b'Book content.')
                identity = {'session': 's', 'host': 'test', 'model': 'unknown'}
                store.agent_action(job['id'], 'claim', identity)
                old = store.runners[job['id']]
                original = old.revoke
                def revoke(reason):
                    original(reason)
                    if threading.current_thread().name == 'old-release':
                        paused.set()
                        resume.wait(3)
                def release():
                    try:
                        store.agent_action(job['id'], 'release', {'session': 's'})
                    except ValueError as error:
                        errors.append(error)
                with patch.object(old, 'revoke', revoke):
                    thread = threading.Thread(target=release, name='old-release')
                    thread.start()
                    self.assertTrue(paused.wait(2))
                    for _ in range(100):
                        if store.get(job['id'])['state'] == 'interrupted':
                            break
                        time.sleep(.01)
                    store.action(job['id'], 'retry')
                    store.agent_action(job['id'], 'claim', identity)
                    new_event = store.events[job['id']]
                    resume.set()
                    thread.join(2)
                    self.assertFalse(new_event.is_set())
                    self.assertIn(store.get(job['id'])['state'], {'queued', 'running', 'awaiting_response'})
            finally:
                resume.set()
                store.close()

    def test_saved_agent_job_cannot_retry_through_cli(self):
        class CLI:
            def info(self):
                return {'name': 'test-cli', 'available': True}
        with tempfile.TemporaryDirectory() as tmp:
            agent = JobStore(tmp, AgentRunner())
            job = agent.create('book.txt', b'Book content.')
            agent.close()
            called = threading.Event()
            cli = JobStore(tmp, CLI(), pipeline=lambda *a, **k: called.set())
            try:
                result = cli.action(job['id'], 'retry')
                self.assertEqual(result['state'], 'interrupted')
                self.assertFalse(called.wait(.05))
            finally:
                cli.close()

    def test_release_revokes_publication_after_last_model_stage(self):
        from test_ebook_core import ContractRunner
        import ebook_pipeline
        with tempfile.TemporaryDirectory() as tmp:
            entered, resume = threading.Event(), threading.Event()
            original = ebook_pipeline._render_outputs
            def paused(*args):
                entered.set()
                if not resume.wait(3):
                    raise AssertionError('Release test did not resume render')
                return original(*args)
            store = JobStore(tmp, AgentRunner())
            try:
                with patch('ebook_pipeline._render_outputs', paused):
                    job = store.create('book.txt', b'Original source book content.')
                    store.agent_action(job['id'], 'claim', {'session': 's', 'host': 'test', 'model': 'fixture'})
                    fixture, seen = ContractRunner(), set()
                    runner = store.runners[job['id']]
                    for _ in range(300):
                        if entered.is_set():
                            break
                        request = runner.next('s')
                        if request and request['request_id'] not in seen:
                            runner.submit('s', request['request_id'], fixture.generate(request['prompt'], schema=request['schema']))
                            seen.add(request['request_id'])
                        time.sleep(.01)
                    self.assertTrue(entered.is_set())
                    store.agent_action(job['id'], 'release', {'session': 's'})
                    resume.set()
                    for _ in range(100):
                        if store.get(job['id'])['state'] not in {'running', 'awaiting_response'}:
                            break
                        time.sleep(.01)
                store.close()
                self.assertEqual(store.get(job['id'])['state'], 'interrupted')
                self.assertFalse((store.jobs_dir / job['id'] / 'deep/analysis.json').exists())
            finally:
                resume.set()
                store.close()

    def test_invalid_source_and_large_book_keep_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(tmp, AgentRunner())
            try:
                invalid = store.create('book.epub', b'not a zip')
                self.assertEqual(invalid['state'], 'failed')
                large = store.create('long.txt', ('正文内容。' * 22000).encode())
                store.agent_action(large['id'], 'claim', {'session': 's', 'host': 'test', 'model': 'unknown'})
                for _ in range(100):
                    job = store.get(large['id'])
                    if job['state'] == 'needs_approval':
                        break
                    time.sleep(.01)
                self.assertEqual(job['state'], 'needs_approval')
                self.assertEqual(store.runners[large['id']].history, {})
                self.assertIsNone(store.runners[large['id']].pending)
                store.action(large['id'], 'approve')
                self.assertEqual(store.get(large['id'])['state'], 'awaiting_agent')
            finally:
                store.close()

    def test_upload_waits_for_claim_then_cancel_revokes(self):
        with tempfile.TemporaryDirectory() as tmp:
            started = threading.Event()
            def pipeline(path, output, runner, **kwargs):
                started.set()
                runner.prepare('test', {'source_hash': 'x'}, 'key')
                runner.generate('inert book data', cancel_event=kwargs['cancel_event'])
            store = JobStore(Path(tmp), AgentRunner(), pipeline=pipeline)
            try:
                job = store.create('book.txt', '这是正文。'.encode())
                self.assertEqual(job['state'], 'awaiting_agent')
                self.assertFalse(started.is_set())
                identity = {'session': 's', 'host': 'test', 'model': 'unknown'}
                store.agent_action(job['id'], 'claim', identity)
                self.assertTrue(started.wait(2))
                with self.assertRaises(ValueError):
                    store.agent_action(job['id'], 'claim', dict(identity, session='other'))
                for _ in range(100):
                    pending = store.agent_action(job['id'], 'next', {'session': 's'})
                    if pending['request']:
                        break
                    time.sleep(.01)
                store.action(job['id'], 'cancel')
                with self.assertRaises((ValueError, InterruptedError)):
                    store.agent_action(job['id'], 'submit', {'session': 's',
                        'request_id': pending['request']['request_id'], 'answer': {}})
            finally:
                store.close()

    def test_full_pipeline_via_current_agent_protocol_is_not_blind_validation(self):
        from test_ebook_core import ContractRunner
        with tempfile.TemporaryDirectory() as tmp:
            fixture = ContractRunner(methods=True)
            store = JobStore(tmp, AgentRunner())
            server = create_server(store)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                client = Client(tmp)
                job = store.create('方法书.txt', '测试书\n\n先检查输入，输入不全时停止，条件符合时执行检查。'.encode())
                client.call('claim', {'session': 'controlled-test', 'host': 'test', 'model': 'fixture'}, job['id'])
                seen = set()
                for _ in range(400):
                    result = client.next(job['id'], 'controlled-test')
                    if result['job']['state'] in {'completed', 'failed', 'interrupted'}:
                        break
                    request = result['request']
                    if request and request['request_id'] not in seen:
                        answer = fixture.generate(request['prompt'], schema=request['schema'])
                        client.call('submit', {'session': 'controlled-test', 'request_id': request['request_id'], 'answer': answer}, job['id'])
                        seen.add(request['request_id'])
                    time.sleep(.01)
                final = store.get(job['id'])
                self.assertEqual(final['state'], 'completed', final.get('error'))
                analysis = final['analysis']
                self.assertEqual(analysis['quality_status'], 'needs_review')
                self.assertEqual(analysis['methods'][0]['verification']['status'], 'needs_review')
                self.assertEqual(analysis['coverage']['candidate_dispositions'][0]['final_status'], 'needs_review')
                report = json.loads((store.jobs_dir / job['id'] / 'deep/validation-report.json').read_text('utf-8'))
                self.assertTrue(report['actual_task_trials'])
                self.assertTrue(all(t['comparative_outcome'] == 'non_isolated_comparative_exercise' for t in report['actual_task_trials']))
                self.assertNotIn('validated：', final['digest'])
            finally:
                server.shutdown()
                server.server_close()
                store.close()

    def test_invalid_quote_never_becomes_cache_or_result(self):
        from test_ebook_core import ContractRunner
        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(tmp, AgentRunner())
            try:
                job = store.create('book.txt', b'Actual original book text.')
                store.agent_action(job['id'], 'claim', {'session': 's', 'host': 'test', 'model': 'fixture'})
                runner = store.runners[job['id']]
                for _ in range(100):
                    request = runner.next('s')
                    if request:
                        break
                    time.sleep(.01)
                answer = ContractRunner().generate(request['prompt'], schema=request['schema'])
                answer['themes'][0]['sources'][0]['quote'] = 'Invented quotation never in book.'
                runner.submit('s', request['request_id'], answer)
                for _ in range(100):
                    final = store.get(job['id'])
                    if final['state'] == 'failed':
                        break
                    time.sleep(.01)
                self.assertEqual(final['state'], 'failed')
                deep = store.jobs_dir / job['id'] / 'deep'
                self.assertFalse((deep / 'analysis.json').exists())
                self.assertEqual(list((deep / '.cache').glob('*.json')), [])
                self.assertTrue(list((deep / '.diagnostics').glob('*.json')))
            finally:
                store.close()


class AgentFileTests(unittest.TestCase):
    def test_reply_cannot_escape_task_or_use_non_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'job'
            root.mkdir()
            outside = Path(tmp) / 'outside.json'
            outside.write_text('{}', 'utf-8')
            with self.assertRaises(ValueError):
                local_json(outside, root)
            text = root / 'reply.txt'
            text.write_text('{}', 'utf-8')
            with self.assertRaises(ValueError):
                local_json(text, root)

    def test_strict_json_rejects_duplicate_and_nonfinite(self):
        for text in ('{"x":1,"x":2}', '{"x":NaN}', '[]'):
            with self.assertRaises(ValueError):
                strict_json(text)

    def test_waiting_job_restored_as_interrupted(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(tmp, AgentRunner())
            job = store.create('book.txt', b'Local book content.')
            store.close()
            restored = JobStore(tmp, AgentRunner())
            try:
                self.assertEqual(restored.get(job['id'])['state'], 'interrupted')
                self.assertNotIn('execution_identity', restored.runner.info())
            finally:
                restored.close()

    def test_private_agent_endpoint_uses_separate_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = JobStore(tmp, AgentRunner())
            server = create_server(store)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            origin = f'http://127.0.0.1:{server.server_port}'
            try:
                request = urllib.request.Request(origin + '/api/agent/list', data=b'{}',
                    headers={'Origin': origin, 'X-Ebook-Token': store.token})
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(request)
                self.assertEqual(error.exception.code, 403)
                runtime = json.loads((Path(tmp) / '.ebook-workbench/agent-runtime.json').read_text('utf-8'))
                self.assertEqual(runtime['token'], store.agent_token)
                request = urllib.request.Request(origin + '/api/agent/list', data=b'{}',
                    headers={'Origin': origin, 'X-Ebook-Agent-Token': runtime['token']})
                with urllib.request.urlopen(request) as response:
                    self.assertEqual(json.load(response)['jobs'], [])
            finally:
                server.shutdown()
                server.server_close()
                store.close()


if __name__ == '__main__':
    unittest.main()
