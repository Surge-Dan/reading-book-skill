"""Opt-in installed-copy workbench smoke; no AI generation or credential output."""
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path


def main():
    installed = Path(sys.argv[1]).resolve()
    output = Path(sys.argv[2]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.pop('PYTHONPATH', None)
    command = [sys.executable, '-X', 'utf8', str(installed / 'scripts/serve_ebook.py'),
               '--output', str(output), '--port', '0', '--runner', 'auto']
    process = subprocess.Popen(command, cwd=output, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, encoding='utf-8')
    try:
        runtime = json.loads(process.stdout.readline())
        url = runtime['url']
        assert re.fullmatch(r'http://127\.0\.0\.1:\d+/', url)
        with urllib.request.urlopen(url, timeout=5) as response:
            html = response.read().decode('utf-8')
        assert 'id="ebookFile"' in html and 'ReadingShareArtwork' in html
        assert 'ebook-app-mounted' in html
        config = json.loads(re.search(r'window.EBOOK_CONFIG=(.*?);window.EBOOK_RESULT=', html).group(1))
        request = urllib.request.Request(url + 'api/state', headers={'X-Ebook-Token': config['token']})
        with urllib.request.urlopen(request, timeout=5) as response:
            state = json.load(response)
        assert state['jobs'] == []
        assert state['runner']['name'] in ('codex', 'claude')
        # Bad extension must be rejected before any model invocation.
        request = urllib.request.Request(url + 'api/jobs?name=unsupported.exe', data=b'not a book',
                                         headers={'X-Ebook-Token': config['token'], 'Origin': url.rstrip('/')})
        try:
            urllib.request.urlopen(request, timeout=5)
            raise AssertionError('Unsupported upload accepted')
        except urllib.error.HTTPError as error:
            assert error.code == 400
        print(json.dumps({'installed_copy': 'pass', 'standalone_ui': 'pass',
                          'api': 'pass', 'unsupported_upload': 'rejected'}, ensure_ascii=False))
    finally:
        process.terminate()
        process.communicate(timeout=15)


if __name__ == '__main__':
    main()
