"""Bounded live CLI smoke/cancellation check; does not print model envelopes."""
import argparse
import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'reading-yearbook-skill/scripts'))
from ebook_runner import create_runner

parser = argparse.ArgumentParser()
parser.add_argument('--runner', default='auto', choices=['auto', 'codex', 'claude'])
parser.add_argument('--cancel', action='store_true')
parser.add_argument('--timeout', type=int, default=180)
args = parser.parse_args()
runner = create_runner(args.runner, timeout=args.timeout)
prompt = 'Return exactly one JSON object with ready set to boolean true. No other text.'
schema = {'type': 'object', 'properties': {'ready': {'type': 'boolean', 'const': True}},
          'required': ['ready'], 'additionalProperties': False}
start = time.monotonic()
if args.cancel:
    event = threading.Event()
    timer = threading.Timer(2, event.set)
    timer.start()
    try:
        runner.generate(prompt, schema=schema, cancel_event=event)
        raise AssertionError('Expected real subprocess cancellation')
    except InterruptedError:
        elapsed = time.monotonic() - start
        assert elapsed < 15, 'Cancellation did not stop the CLI promptly'
        print(json.dumps({'runner': runner.name, 'cancelled': True, 'elapsed_seconds': round(elapsed, 2)}))
    finally:
        timer.cancel()
else:
    try:
        result = runner.generate(prompt, schema=schema)
    except ValueError as error:
        print(json.dumps({'runner': runner.name, 'error': str(error), 'diagnostic': getattr(error, 'diagnostic', {})}, ensure_ascii=False))
        sys.exit(1)
    assert result.get('ready') is True, 'CLI did not return requested structured response'
    print(json.dumps({'runner': runner.name, 'structured_output': 'pass', 'elapsed_seconds': round(time.monotonic() - start, 2)}))
