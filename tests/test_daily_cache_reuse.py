import json
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'reading-yearbook-skill/scripts'))
from collect_html_materials import call, cache_expired, reuse_previous_materials, TZ
from collect_weread_data import WeReadError


class DailyReuseTests(unittest.TestCase):
    def seed(self, base):
        today = datetime.now(TZ).date()
        previous = Path(base) / 'owner' / '2026' / str(today - timedelta(days=1))
        raw = previous / 'raw'; raw.mkdir(parents=True)
        source = raw / 'book-info.json'
        source.write_text(json.dumps({'title': 'Book'}), 'utf-8')
        source.with_suffix('.json.meta.json').write_text(json.dumps({
            'version': 1, 'api': '/book/info',
            'fetched_at': datetime.now(TZ).replace(hour=0).isoformat()[:10].replace(str(today), str(today - timedelta(days=1))) + 'T00:00:00+08:00',
        }), 'utf-8')
        return Path(base) / 'owner' / '2026' / str(today)

    def test_cross_day_data_refreshes_and_preserves_fetch_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = self.seed(tmp)
            self.assertEqual(reuse_previous_materials(cache), 1)
            target = cache / 'raw/book-info.json'
            self.assertTrue(cache_expired(target))
            with patch('collect_html_materials.gateway_call', return_value={'title': 'New'}) as request:
                result = call('/book/info', {}, 'synthetic', target, threading.Event())
            request.assert_called_once()
            self.assertEqual(result['title'], 'New')
            self.assertFalse(cache_expired(target))

    def test_cross_day_failure_is_stale_instead_of_fresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = self.seed(tmp); reuse_previous_materials(cache)
            with patch('collect_html_materials.gateway_call', side_effect=WeReadError('temporary', 'network')):
                result = call('/book/info', {}, 'synthetic', cache / 'raw/book-info.json', threading.Event())
            self.assertEqual(result['_cache_status'], 'stale')

    def test_does_not_import_unstamped_responses_or_other_owner(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = self.seed(tmp)
            previous = next(cache.parent.iterdir())
            (previous / 'raw/unstamped.json').write_text('{}', 'utf-8')
            self.assertEqual(reuse_previous_materials(Path(tmp) / 'another' / '2026' / cache.name), 0)
            reuse_previous_materials(cache)
            self.assertFalse((cache / 'raw/unstamped.json').exists())

    def test_does_not_overwrite_current_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = self.seed(tmp); target = cache / 'raw/book-info.json'
            target.parent.mkdir(parents=True); target.write_text('current', 'utf-8')
            reuse_previous_materials(cache)
            self.assertEqual(target.read_text('utf-8'), 'current')
