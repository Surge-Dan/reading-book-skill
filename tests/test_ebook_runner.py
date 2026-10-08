import subprocess
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'reading-yearbook-skill/scripts'))
from ebook_runner import CLIRunner, create_runner
from ebook_pipeline import distill
from test_ebook_core import ContractRunner


class RunnerTests(unittest.TestCase):
    def test_stage_timeout_is_bounded(self):
        for seconds in (0, 29, 901):
            with self.assertRaisesRegex(ValueError, '30.*900'):
                create_runner('codex', timeout=seconds)
        self.assertEqual(create_runner('codex', timeout=600).timeout, 600)

    def test_timeout_reports_only_safe_diagnostic_metadata(self):
        class Process:
            pid = 123
            returncode = -1
            calls = 0
            def communicate(self, **kwargs):
                self.calls += 1
                if self.calls == 1:
                    raise subprocess.TimeoutExpired('fake-cli', .2)
                return 'private answer', 'private-book-secret\n2026-10-08T00:00:00Z ERROR codex_core::client: HTTP 429 rate limit\n'
            def kill(self):
                pass
        with patch('ebook_runner.shutil.which', return_value='fake-cli.exe'), \
             patch('ebook_runner.subprocess.Popen', return_value=Process()), \
             patch('ebook_runner.subprocess.run'), \
             patch('ebook_runner.time.monotonic', side_effect=[0, 31, 31]):
            runner = CLIRunner('codex', timeout=30)
            with self.assertRaises(ValueError) as caught:
                runner.generate('private-book-secret')
            diagnostic = caught.exception.diagnostic
            self.assertEqual(diagnostic['category'], 'rate_limit')
            self.assertEqual(diagnostic['elapsed_seconds'], 31)
            self.assertGreater(diagnostic['stderr_bytes'], 0)
            self.assertNotIn('private-book-secret', str(diagnostic) + str(caught.exception))

    def test_timeout_change_reuses_semantically_valid_stage_cache(self):
        class Runner(ContractRunner):
            timeout = 180
            def info(self):
                return dict(super().info(), timeout=self.timeout)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'book.txt'
            source.write_text('原文', 'utf-8')
            runner = Runner()
            distill(source, Path(tmp) / 'out', runner)
            count = len(runner.calls)
            runner.timeout = 600
            distill(source, Path(tmp) / 'out', runner)
            self.assertEqual(len(runner.calls), count)

    def test_model_stages_receive_required_top_level_json_schema(self):
        class Runner(ContractRunner):
            schemas = []
            def generate(self, prompt, schema=None, cancel_event=None):
                self.schemas.append(schema)
                return super().generate(prompt, schema, cancel_event)
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'book.txt'
            source.write_text('原文', 'utf-8')
            runner = Runner()
            distill(source, Path(tmp) / 'out', runner)
            for schema in runner.schemas:
                self.assertIsInstance(schema, dict)
                self.assertTrue(schema['required'], 'Generic object schema permits an empty successful output')
                self.assertEqual(set(schema['required']), set(schema['properties']))

    def test_invalid_source_output_is_diagnostic_only_not_reused_cache(self):
        class Runner(ContractRunner):
            def generate(self, prompt, schema=None, cancel_event=None):
                self.assertion_prompt = prompt
                value = super().generate(prompt, schema, cancel_event)
                value['themes'][0]['sources'][0]['quote'] = '不存在于正文的引用'
                return value
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'book.txt'
            source.write_text('原文', 'utf-8')
            runner = Runner()
            output = Path(tmp) / 'out'
            with self.assertRaises(ValueError) as caught:
                distill(source, output, runner)
            self.assertFalse(caught.exception.diagnostic['exact_quote_match'])
            files = list((output / '.diagnostics').glob('*.json'))
            self.assertEqual(len(files), 1)
            self.assertEqual(json.loads(files[0].read_text('utf-8'))['stage'], 'stage0-map')
            self.assertEqual(list((output / '.cache').glob('*.json')), [])
            self.assertFalse((output / 'analysis.json').exists())
            self.assertIn('150 Chinese characters', runner.assertion_prompt)


if __name__ == '__main__':
    unittest.main()
