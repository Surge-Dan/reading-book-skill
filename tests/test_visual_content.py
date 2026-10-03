import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SKILL=ROOT/'reading-yearbook-skill'
sys.path.insert(0,str(SKILL/'scripts'))
sys.path.insert(0,str(SKILL/'examples'))
from content_plan import representative_ids, validate_storyboards
from static_graphics import calendar_cells, monthly_points, render_graphic, validate_graphics
from run_share import prepare_share, approve_scope, approve_content, require_content, write_json, file_digest, approve_visual, export_share
from workflow_fixture import sample_decisions


class VisualContentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.folder=Path(self.temp.name)/'share'
        self.job=prepare_share(2026,SKILL/'assets/sample-data.json',self.folder,['sample-001','sample-002','sample-005'])
        sample_decisions(self.job)
        self.job['art_brief']={'focus':'technical validation'}

    def tearDown(self):
        self.temp.cleanup()

    def test_representatives_cover_different_structures_without_previewing_every_book(self):
        books=self.job['pages'][2:]
        books[0]['storyboard']['main_visual']['structure']='relations'
        books[1]['storyboard']['main_visual']['structure']='relations'
        books[2]['storyboard']['main_visual']['structure']='photo-notes'
        self.assertEqual(representative_ids(self.job),['cover','overview',books[0]['id'],books[2]['id']])
        self.job['preview_page_ids']=['cover','overview',books[0]['id'],books[1]['id']]
        with self.assertRaisesRegex(ValueError,'不同内容结构'):
            representative_ids(self.job)
        self.job['preview_page_ids']=['cover','overview',books[0]['id'],books[2]['id']]
        self.assertEqual(len(representative_ids(self.job)),4)

    def test_incomplete_plan_and_unknown_auxiliary_block_are_rejected(self):
        self.job['pages'][2]['storyboard']['supporting_blocks']=['not-a-block']
        with self.assertRaisesRegex(ValueError,'本页内容块'):
            validate_storyboards(self.job)
        self.job['pages'][2].pop('storyboard')
        with self.assertRaisesRegex(ValueError,'分镜'):
            validate_storyboards(self.job)

    def test_storyboard_and_preview_plan_changes_invalidate_content_confirmation(self):
        write_json(self.folder/'share-job.json',self.job)
        approve_scope(self.folder,True)
        for mutate in (lambda j:j['pages'][2]['storyboard'].update(reading_task='另一种理解'),
                       lambda j:j.update(preview_page_ids=[p['id'] for p in j['pages']])):
            job=approve_content(self.folder,True)
            mutate(job)
            with self.assertRaisesRegex(ValueError,'未确认'):
                require_content(job)

    def test_calendar_preserves_real_dates_zero_missing_future_and_leap_boundary(self):
        rows=calendar_cells(2024,{'2024-02-28':0,'2024-02-29':3600},'2024-02-29')
        values={r['date']:r for r in rows}
        self.assertEqual(len(rows),366)
        self.assertEqual(values['2024-02-28']['state'],'zero')
        self.assertEqual(values['2024-02-29']['state'],'observed')
        self.assertEqual(values['2024-02-27']['state'],'missing')
        self.assertEqual(values['2024-03-01']['state'],'future')
        self.assertEqual(values['2024-02-29']['weekday'],3)
        self.assertEqual(max(r['week'] for r in calendar_cells(2012,{},'2012-12-31')),53) # 54 partial/full calendar columns.
        for data in ({'2023-02-29':1},{'2024-03-01':3},{'2024-02-28':-1}):
            with self.assertRaises(ValueError):
                calendar_cells(2024,data,'2024-02-29')
        with self.assertRaises(ValueError):
            calendar_cells(2024,[3600]*12,'2024-12-31')

    def test_monthly_missing_is_not_zero_and_future_values_are_rejected(self):
        value={'seconds':[0,3600]+[0]*10,'observed':[True,True]+[False]*10}
        rows=monthly_points(2026,value,'2026-06-01')
        self.assertEqual([r['state'] for r in rows[:3]],['zero','observed','missing'])
        self.assertIsNone(rows[2]['seconds'])
        self.assertEqual(rows[6]['state'],'future')
        value['seconds'][6]=1
        with self.assertRaises(ValueError):
            monthly_points(2026,value,'2026-06-01')

    def test_interpretive_edges_need_sources_and_cannot_encode_fake_weights(self):
        page=self.job['pages'][2]
        a,b=page['blocks'][:2]
        page['graphics']=[{'id':'test-graph','kind':'relations','nodes':[
            {'id':'a','block_id':a['id'],'x':8,'y':8,'width':300,'height':160},
            {'id':'b','block_id':b['id'],'x':430,'y':200,'width':300,'height':160}],
            'edges':[{'from':'a','to':'b','source_refs':a['source_refs']}]}]
        svg=render_graphic(self.job,page['id'],'test-graph',780,380)
        self.assertIn('data-ready="true"',svg)
        self.assertIn(f'data-block="{a["id"]}"',svg)
        edge=page['graphics'][0]['edges'][0]
        edge['weight']=.8
        with self.assertRaisesRegex(ValueError,'权重'):
            validate_graphics(self.job)
        edge.pop('weight')
        edge['source_refs']=[]
        with self.assertRaisesRegex(ValueError,'依据'):
            validate_graphics(self.job)

    def test_normalization_retains_missing_months_and_note_dates(self):
        self.assertTrue(all(self.job['sources']['summary/monthly-records']['value']['observed']))
        self.assertIsNotNone(self.job['sources']['sample-001/thought/s1-r1']['created_at'])
        raw=json.loads((SKILL/'assets/sample-data.json').read_text('utf-8'))
        raw['stats']['readTimes']={'1767225600':0}
        source=Path(self.temp.name)/'sparse.json'
        write_json(source,raw)
        job=prepare_share(2026,source,Path(self.temp.name)/'sparse',['sample-001'])
        self.assertEqual(job['sources']['summary/monthly-records']['value']['observed'],[True]+[False]*11)


@unittest.skipUnless(all(os.environ.get(k) for k in ('SHARE_NODE','SHARE_PLAYWRIGHT','SHARE_BROWSER')),'Local render paths required.')
class ExhibitionRenderTests(unittest.TestCase):
    def test_four_previews_six_final_pages_svg_copy_and_static_readiness(self):
        from build_exhibition_demo import build
        options={'node':os.environ['SHARE_NODE'],'playwright_package':os.environ['SHARE_PLAYWRIGHT'],'browser':os.environ['SHARE_BROWSER']}
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)/'exhibition'
            build(folder)
            approve_scope(folder,True)
            approve_content(folder,True)
            preview=export_share(folder,'preview',**options)
            self.assertEqual((preview['status'],preview.get('pages')),('pass',4))
            approve_visual(folder,True)
            final=export_share(folder,'final',**options)
            self.assertEqual((final['rendered'],final['reused']),(2,4))
            cached=export_share(folder,'final',**options)
            self.assertEqual((cached['rendered'],cached['reused']),(0,6))
            old_images={p.name:file_digest(p) for p in (folder/'images').glob('*.png')}
            good=(folder/'deck.html').read_text('utf-8')
            # Change only a SVG node. Its original content binding must still reject it.
            bad=good.replace('>写下你相信什么<','>一个未经确认的结论<')
            self.assertNotEqual(good,bad)
            (folder/'deck.html').write_text(bad,'utf-8')
            failed=export_share(folder,'preview',**options)
            self.assertEqual(failed['status'],'failed')
            self.assertIn('可见内容',failed['reason'])
            # Graph has valid text but has not completed static drawing.
            pending=good.replace('data-graphic="decision-path" data-ready="true"','data-graphic="decision-path" data-ready="false"')
            (folder/'deck.html').write_text(pending,'utf-8')
            failed=export_share(folder,'preview',**options)
            self.assertTrue(any(e['problem']=='graphic_not_ready_or_clipped' for e in failed['errors']))
            self.assertEqual(old_images,{p.name:file_digest(p) for p in (folder/'images').glob('*.png')})
            # Deferred renderer is called explicitly, not left to an observer.
            hook='''<script>window.renderForExport=async ids=>{await new Promise(r=>setTimeout(r,30));for(const id of ids)document.getElementById(id)?.querySelectorAll('[data-graphic]').forEach(g=>g.dataset.ready='true');};</script>'''
            (folder/'deck.html').write_text(pending.replace('</body>',hook+'</body>'),'utf-8')
            self.assertEqual(export_share(folder,'preview',**options)['status'],'pass')


if __name__=='__main__':
    unittest.main()
