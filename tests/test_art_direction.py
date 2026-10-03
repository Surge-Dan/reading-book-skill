import json
import os
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'reading-yearbook-skill'
sys.path.insert(0, str(SKILL / 'scripts'))
sys.path.insert(0, str(SKILL / 'examples'))
from art_direction import design_packet, validate_artwork
from collage_materials import paper, cutout
from run_share import (prepare_share, content_hash, approve_scope, approve_content,
                       approve_visual, export_share, load_job, write_json)
from workflow_fixture import sample_decisions, build


def plan(page, concept='把当前原话的两种声音并排'):
    ids = [b['id'] for b in page['blocks']]
    return {'concept': concept, 'rationale': '当前材料里的对照决定位置，不按书名选版式。',
            'voice': '字体与留白', 'basis_refs': page['storyboard']['evidence_refs'],
            'reading_path': ids,
            'primary': {'medium': '字样', 'description': concept, 'origin': 'typography', 'asset_paths': []},
            'layers': [{'id': 'words', 'role': 'text', 'purpose': '原话与书目', 'block_ids': ids}],
            'fonts': [{'family': 'Microsoft YaHei', 'role': '文字', 'use_basis': '本机测试字形', 'block_ids': ids}]}


class ArtDirectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.job = prepare_share(2026, SKILL / 'assets/sample-data.json', Path(self.temp.name)/'share', ['sample-002'], 'book-list')
        self.assertEqual(self.job['art_brief']['workflow'], 'material-led')
        sample_decisions(self.job)
        self.job['art_brief']['workflow'] = 'material-led'
        for p in self.job['pages']:
            p['artwork'] = plan(p)

    def tearDown(self):
        self.temp.cleanup()

    def test_unknown_title_does_not_select_style(self):
        packet = design_packet(self.job)
        self.job['books'][0].update(title='完全没出现过的书名', category='未知')
        changed = design_packet(self.job)
        self.assertEqual(packet['pages'], changed['pages'])
        self.assertEqual(changed['status'], 'proposal_only')
        self.assertNotIn('selected_direction', changed)
        validate_artwork(self.job)

    def test_same_book_can_have_different_material_based_artwork(self):
        other = deepcopy(self.job)
        p = other['pages'][-1]
        p['artwork'] = plan(p, '从原话中的全景到局部：一次视觉放大')
        p['artwork']['voice'] = '原创物件与局部观察'
        p['artwork']['primary'].update(origin='original', medium='原创SVG', description='把当前笔记的观察对象切开，保留侧边阅读区')
        validate_artwork(other)
        self.assertEqual(self.job['books'], other['books'])
        self.assertNotEqual(content_hash(self.job), content_hash(other))

    def test_packet_bounds_material_and_preserves_sources(self):
        p = self.job['pages'][-1]
        b = next(b for b in p['blocks'] if b['kind'] == 'thought')
        b['text'] = '原话' * 300
        p['blocks'].extend([{**b, 'id': f'extra-{i}'} for i in range(10)])
        selected = design_packet(self.job)['pages'][-1]['selected_material']
        self.assertEqual(len(selected), 4)
        self.assertTrue(all(len(item['text']) <= 280 for item in selected))
        truncated = next(item for item in selected if item['id'] == b['id'])
        self.assertTrue(truncated['excerpt_only'])
        self.assertEqual(truncated['source_refs'], b['source_refs'])

    def test_missing_plan_fails_new_workflow_but_legacy_remains_usable(self):
        del self.job['pages'][0]['artwork']
        with self.assertRaisesRegex(ValueError, '材料驱动'): validate_artwork(self.job)
        del self.job['art_brief']['workflow']
        validate_artwork(self.job)

    def test_unrelated_source_or_missing_material_rejected(self):
        p = self.job['pages'][-1]
        p['artwork']['basis_refs'] = ['not-in-this-page']
        with self.assertRaisesRegex(ValueError, '证据'): validate_artwork(self.job)
        p['artwork'] = plan(p)
        p['artwork']['primary'].update(origin='registered-assets', asset_paths=['assets/missing.png'])
        with self.assertRaisesRegex(ValueError, '登记'): validate_artwork(self.job)

    def test_core_text_and_data_cannot_bleed(self):
        layer = self.job['pages'][0]['artwork']['layers'][0]
        layer.update(allow_bleed=True, bleed_reason='想要不规则')
        with self.assertRaisesRegex(ValueError, '出血'): validate_artwork(self.job)
        layer.update(role='data', block_ids=[])
        with self.assertRaisesRegex(ValueError, '出血'): validate_artwork(self.job)
        layer.update(role='material')
        self.job['pages'][0]['artwork']['layers'].append({'id': 'text', 'role': 'text', 'purpose': '阅读区', 'block_ids': self.job['pages'][0]['artwork']['reading_path']})
        validate_artwork(self.job)

    def test_font_and_layer_bindings_cannot_omit_reading_path(self):
        p = self.job['pages'][0]
        p['artwork']['fonts'][0]['block_ids'] = [p['blocks'][0]['id']]
        with self.assertRaisesRegex(ValueError, '字体校验'): validate_artwork(self.job)
        p['artwork'] = plan(p)
        p['artwork']['layers'][0]['block_ids'] = []
        with self.assertRaisesRegex(ValueError, '图层绑定'): validate_artwork(self.job)

    def test_original_material_reproducible_and_cutout_does_not_accept_escaping_paths(self):
        self.assertEqual(paper(600, 400, seed=17), paper(600, 400, seed=17))
        self.assertNotEqual(paper(600, 400, seed=17), paper(600, 400, seed=18))
        self.assertIn('clipPath', cutout('assets/original.png', 400, 600, uid='shape', contour='M0 0 L400 0 L200 600 Z'))
        for value in ('../secret.png', '/absolute.png', 'https://site/image.png', 'C:\\image.png'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                cutout(value, 400, 600, uid='shape', contour='M0 0Z')


@unittest.skipUnless(all(os.environ.get(k) for k in ('SHARE_NODE', 'SHARE_PLAYWRIGHT', 'SHARE_BROWSER')), 'Local render paths required.')
class ArtworkBrowserTests(unittest.TestCase):
    def test_material_led_export_cache_and_font_failure_preserves_pngs(self):
        options = {'node': os.environ['SHARE_NODE'], 'playwright_package': os.environ['SHARE_PLAYWRIGHT'], 'browser': os.environ['SHARE_BROWSER']}
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)/'share'
            build(folder)
            job = load_job(folder)
            job['art_brief']['workflow'] = 'material-led'
            for p in job['pages']:
                p['artwork'] = plan(p)
            write_json(folder/'share-job.json', job)
            html = (folder/'deck.html').read_text('utf-8').replace('<main>', '<main data-layer="words">')
            (folder/'deck.html').write_text(html, 'utf-8')
            approve_scope(folder, True)
            approve_content(folder, True)
            first = export_share(folder, 'preview', **options)
            self.assertEqual(first['status'], 'pass', first)
            report = json.loads((folder/'validation-report.json').read_text('utf-8'))
            self.assertTrue(all(p['artwork']['fonts'] and not p['artwork']['errors'] for p in report['pages']))
            approve_visual(folder, True)
            final = export_share(folder, 'final', **options)
            self.assertEqual(final['status'], 'pass', final)
            repeated = export_share(folder, 'final', **options)
            self.assertEqual((repeated['rendered'], repeated['reused']), (0, len(job['pages'])))
            before = {p.name: p.read_bytes() for p in (folder/'images').glob('*.png')}
            (folder/'deck.html').write_text(html.replace('font-family:"Microsoft YaHei",sans-serif', 'font-family:"SimSun",serif'), 'utf-8')
            failed = export_share(folder, 'preview', **options)
            self.assertEqual(failed['status'], 'failed', failed)
            self.assertTrue(any(e['problem'] == 'font_fallback_unapproved' for e in failed['errors']))
            self.assertEqual(before, {p.name: p.read_bytes() for p in (folder/'images').glob('*.png')})

    def test_actual_fonts_opaque_overlay_transparency_and_bindings(self):
        result = subprocess.run([os.environ['SHARE_NODE'], str(ROOT/'tests/fixtures/artwork-browser.cjs'),
                                 os.environ['SHARE_PLAYWRIGHT'], os.environ['SHARE_BROWSER']], capture_output=True, text=True, encoding='utf-8', timeout=45)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        reports = json.loads(result.stdout)
        self.assertFalse(reports['valid']['errors'])
        self.assertEqual(reports['valid']['fonts'][0]['actual'][0]['familyName'], 'Arial')
        self.assertIn('font_fallback_unapproved', [e['problem'] for e in reports['fallback']['errors']])
        self.assertIn('text_occluded', [e['problem'] for e in reports['opaque']['errors']])
        self.assertIn('text_occluded', [e['problem'] for e in reports['opaque_image']['errors']])
        self.assertFalse(reports['transparent']['errors'])
        self.assertFalse(reports['allowed_fallback']['errors'])
        self.assertIn('occlusion_needs_visual_review', [w['problem'] for w in reports['transformed']['warnings']])
        self.assertIn('unplanned_layer_bleed', [e['problem'] for e in reports['bleed']['errors']])
        self.assertIn('layer_asset_missing', [e['problem'] for e in reports['missing']['errors']])
        self.assertTrue(reports['styles_restored'])


if __name__ == '__main__': unittest.main()
