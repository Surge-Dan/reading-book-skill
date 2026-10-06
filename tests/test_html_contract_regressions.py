import base64
import json
import sys
import tempfile
import threading
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'reading-yearbook-skill/scripts'))
from build_reading_html import adapt_data,merge_annual,merge_materials,embed_image,TZ
from collect_html_materials import call,collect,reviews,PartialReviews
from collect_weread_data import _unwrap,WeReadError
from generate_reading_html import collect_snapshot,annual_data,ScopeRequired


def stamp(year):return int(datetime(year,6,1,tzinfo=TZ).timestamp())
def annual(count=1):return {'readStat':[{'stat':'读过','counts':f'{count}本'}],'readLongest':[]}


class HtmlContractRegressions(unittest.TestCase):
    def test_export_import_preserves_statistics_dates_history_and_coverage(self):
        data=adapt_data({'year':2026,'as_of':'2026-10-06','summary':{'book_count':1,'finished_count':1,'note_count':3,'total_read_seconds':3600,'monthly_read_seconds':[3600]*10},'books':[{'book_id':'one','title':'书','progress':100,'finish_time':'2026-06-01'}]})
        merge_materials(data,{'year':2026,'books':[{'book_id':'one','notes_scope':'all_time','collection':{'highlights':'complete','thoughts':'complete'},'highlights':[{'text':'旧划线','source_id':'old','created_at':'2025-01-01','chapter_uid':3,'range':'10-20'}],'thoughts':[]}]})
        again=adapt_data(json.loads(json.dumps(data)))
        self.assertEqual(again['summary'],data['summary'])
        self.assertEqual(again['books'][0],data['books'][0])
        self.assertEqual(again['material_coverage'],data['material_coverage'])

    def test_started_zero_progress_is_included_but_not_used_as_annual_duration(self):
        shelf={'books':[{'bookId':'one','title':'书','readUpdateTime':stamp(2026)}]}
        with tempfile.TemporaryDirectory() as tmp,patch('generate_reading_html.call',side_effect=[shelf,annual(),{'books':[]},{'book':{'progress':0,'isStartReading':1,'recordReadingTime':180,'updateTime':stamp(2026)}}]):
            book=annual_data(collect_snapshot(2026,'synthetic',tmp))['books'][0]
        self.assertEqual(book['status'],'reading');self.assertIsNone(book['reading_seconds'])

    def test_historical_notes_find_book_read_again_later(self):
        shelf={'books':[{'bookId':'one','title':'书','readUpdateTime':stamp(2026)}]}
        with tempfile.TemporaryDirectory() as tmp,patch('generate_reading_html.call',side_effect=[shelf,annual(),{'books':[]},{'book':{'progress':80,'updateTime':stamp(2026)}},{'updated':[{'createTime':stamp(2025),'markText':'历史原文'}]}]):
            books=annual_data(collect_snapshot(2025,'synthetic',tmp))['books']
        self.assertEqual(len(books),1);self.assertIsNone(books[0]['reading_seconds'])

    def test_large_discovery_stops_before_progress_calls(self):
        shelf={'books':[{'bookId':str(i),'title':'书','readUpdateTime':stamp(2026)} for i in range(101)]}
        with tempfile.TemporaryDirectory() as tmp,patch('generate_reading_html.call',side_effect=[shelf,annual(101),{'books':[]}]) as requests:
            with self.assertRaises(ScopeRequired):collect_snapshot(2026,'synthetic',tmp)
            self.assertEqual(requests.call_count,3)

    def test_english_upgrade_stops_even_with_cached_followup(self):
        def upgrade(*args,**kwargs):return _unwrap({'upgrade_info':{'message':'Please update your skill'}})
        with tempfile.TemporaryDirectory() as tmp:
            stop=threading.Event();cache=Path(tmp)/'response.json'
            with patch('collect_html_materials.gateway_call',side_effect=upgrade):
                with self.assertRaises(WeReadError):call('/book/info',{},'synthetic',cache,stop)
            self.assertTrue(stop.is_set())
            cache.write_text('{"title":"cached"}',encoding='utf-8')
            with self.assertRaises(WeReadError):call('/book/info',{},'synthetic',cache,stop)

    def test_refresh_and_corrupt_cache_recollect_without_writing_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache=Path(tmp)/'response.json';cache.write_text('{"title":"old"}',encoding='utf-8')
            with patch('collect_html_materials.gateway_call',return_value={'title':'new'}) as request:
                self.assertEqual(call('/book/info',{},'synthetic',cache,threading.Event(),refresh=True)['title'],'new');request.assert_called_once()
            cache.write_text('{broken',encoding='utf-8')
            with patch('collect_html_materials.gateway_call',return_value={'title':'fixed'}):
                self.assertEqual(call('/book/info',{},'synthetic',cache,threading.Event())['title'],'fixed')

    def test_category_metadata_and_note_context_survive_collection(self):
        payloads=[{'title':'书','category':{'title':'文学-小说'},'translator':'译者','deepLink':'weread://book/one'}, {'book':{'progress':0,'isStartReading':0}}, {'updated':[{'markText':'原文','bookmarkId':'a','range':'1-2','chapterUid':3}],'chapters':[{'chapterUid':3,'title':'第一章'}]}]
        data=adapt_data({'year':2026,'summary':{},'books':[{'book_id':'one','title':'书'}]})
        with tempfile.TemporaryDirectory() as tmp,patch('collect_html_materials.call',side_effect=payloads),patch('collect_html_materials.reviews',return_value={'reviews':[{'review':{'content':'想法','abstract':'原文','range':'1-2','chapterUid':3}}]}),patch('builtins.print'):
            collect(data,{},tmp,'synthetic');materials=json.loads((Path(tmp)/'materials.json').read_text('utf-8'))
        merge_materials(data,materials);b=data['books'][0]
        self.assertEqual(b['category'],'文学');self.assertEqual(b['status'],'unstarted')
        self.assertEqual(b['thoughts'][0]['quote'],'原文');self.assertEqual(b['thoughts'][0]['chapter_title'],'第一章')

    def test_corrupt_image_signature_does_not_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            image=Path(tmp)/'bad.png';image.write_bytes(b'\x89PNG\r\n\x1a\n')
            with self.assertRaisesRegex(ValueError,'解码'):embed_image(image)

    def test_refresh_failure_keeps_old_materials_with_explicit_stale_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache=Path(tmp)/'response.json';cache.write_text('{"updated":[{"markText":"旧原文"}]}',encoding='utf-8')
            with patch('collect_html_materials.gateway_call',side_effect=WeReadError('temporary','network')):
                result=call('/book/bookmarklist',{},'synthetic',cache,threading.Event(),refresh=True)
            self.assertEqual(result['_cache_status'],'stale')
            self.assertNotIn('_cache_status',json.loads(cache.read_text('utf-8')))
            data=adapt_data({'year':2026,'summary':{},'books':[{'book_id':'one'}]})
            merge_materials(data,{'year':2026,'books':[{'book_id':'one','notes_scope':'all_time','collection':{'highlights':'stale'},'highlights':[{'text':'旧原文','created_at':'2025-06-01'}]}]})
            self.assertEqual(data['books'][0]['highlights'][0]['text'],'旧原文')
            self.assertEqual(data['books'][0]['note_coverage']['highlights'],'stale')

    def test_cache_metadata_and_corrupt_entry_do_not_bypass_request_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache=Path(tmp)/'response.json'
            with patch('collect_html_materials.gateway_call',return_value={'title':'新书'}):
                call('/book/info',{},'synthetic',cache,threading.Event())
            meta=json.loads(cache.with_suffix('.json.meta.json').read_text('utf-8'))
            self.assertEqual(meta['version'],1);self.assertIn('fetched_at',meta)
        shelf={'books':[{'bookId':str(i),'title':'书','readUpdateTime':stamp(2026)} for i in range(2)]}
        with tempfile.TemporaryDirectory() as tmp:
            import hashlib
            raw=Path(tmp)/'raw';raw.mkdir()
            for i in range(2):(raw/(hashlib.sha256(str(i).encode()).hexdigest()[:20]+'-progress.json')).write_text('{broken',encoding='utf-8')
            with patch('generate_reading_html.call',side_effect=[shelf,annual(2),{'books':[]},{'book':{'progress':1,'updateTime':stamp(2026)}}]) as requests:
                with self.assertRaises(ScopeRequired):collect_snapshot(2026,'synthetic',tmp,request_budget=2)
                self.assertEqual(requests.call_count,4)

    def test_empty_upgrade_marker_is_terminal(self):
        with self.assertRaises(WeReadError) as error:_unwrap({'upgrade_info':{}})
        self.assertEqual(error.exception.kind,'upgrade');self.assertTrue(error.exception.terminal)

    def test_bad_nested_shapes_report_the_field_instead_of_attribute_error(self):
        with self.assertRaisesRegex(ValueError,r'books\[0\].note_coverage'):
            adapt_data({'year':2026,'books':[{'book_id':'one','note_coverage':None}]})
        with self.assertRaisesRegex(ValueError,'coverage'):
            adapt_data({'year':2026,'coverage':[]})
        data=adapt_data({'year':2026,'summary':{},'books':[]})
        with self.assertRaisesRegex(ValueError,r'readLongest\[0\].book'):
            merge_annual(data,{'year':2026,'annual':{**annual(),'readLongest':[{'book':'broken'}]}})
        with self.assertRaises(WeReadError):_unwrap([])

    def test_terminal_error_stops_queued_books_and_cover_downloads(self):
        data=adapt_data({'year':2026,'summary':{},'books':[{'book_id':str(i),'title':'书'} for i in range(30)]})
        with tempfile.TemporaryDirectory() as tmp,patch('collect_html_materials.gateway_call',side_effect=WeReadError('update','upgrade')) as request,patch('collect_html_materials.download_cover') as cover:
            with self.assertRaises(WeReadError):collect(data,{},tmp,'synthetic')
            self.assertLessEqual(request.call_count,2);cover.assert_not_called()

    def test_interrupted_pagination_retains_new_rows_and_previous_notes(self):
        with tempfile.TemporaryDirectory() as tmp,patch('collect_html_materials.call',side_effect=[{'reviews':[{'review':{'content':'新想法','reviewId':'new'}}],'hasMore':1,'synckey':2},WeReadError('network')]):
            with self.assertRaises(PartialReviews) as error:reviews('one','synthetic',Path(tmp)/'reviews.json',threading.Event())
            self.assertEqual(len(error.exception.rows),1)
        data=adapt_data({'year':2026,'summary':{},'books':[{'book_id':'one','thoughts':[{'text':'旧想法','source_id':'old'}]}]})
        merge_materials(data,{'year':2026,'books':[{'book_id':'one','notes_scope':'all_time','collection':{'thoughts':'partial'},'thoughts':[{'text':'新想法','source_id':'new'}]}]})
        self.assertEqual([n['source_id'] for n in data['books'][0]['thoughts']],['new','old'])
        self.assertEqual(data['books'][0]['note_coverage']['thoughts'],'partial')

    def test_optional_fields_keep_units_and_hour_order(self):
        data=adapt_data({'year':2026,'summary':{},'books':[]})
        merge_annual(data,{'year':2026,'as_of':'2026-10-06','shelf':{'books':[]},'annual':{**annual(0),'preferTime':list(range(24)),'dailyReadTimes':{str(stamp(2026)):120},'preferCategory':[{'categoryTitle':'真实分类','readingTime':100},{'categoryTitle':'占位分类'}],'wrReadTime':100,'wrListenTime':200,'compare':-.2}})
        f=data['features'];self.assertEqual(f['hourly'][6],0);self.assertEqual(f['hourly'][0],18)
        self.assertEqual(f['daily']['2026-06-01'],120);self.assertEqual(len(f['category_time']),1)
        self.assertEqual(f['comparison'],-.2)

    def test_unknown_total_is_not_loaded_count_and_unsupported_schema_fails(self):
        self.assertIsNone(adapt_data({'year':2026,'summary':{},'books':[{'book_id':'one'}]})['summary']['read'])
        with self.assertRaisesRegex(ValueError,'版本'):adapt_data({'schema_version':'reading-html/99','year':2026,'summary':{},'books':[]})

    def test_audio_does_not_call_ebook_note_apis(self):
        data=adapt_data({'year':2026,'summary':{},'books':[]})
        merge_annual(data,{'year':2026,'shelf':{'books':[]},'annual':{**annual(1),'readLongest':[{'albumInfo':{'albumId':'one','name':'听书','cover':'https://cdn.weread.qq.com/a.png'},'readTime':100}]}})
        with tempfile.TemporaryDirectory() as tmp,patch('collect_html_materials.call') as gateway,patch('collect_html_materials.download_cover',return_value=Path('cover.png')),patch('builtins.print'):
            collect(data,{},tmp,'synthetic');gateway.assert_not_called()
            materials=json.loads((Path(tmp)/'materials.json').read_text('utf-8'))
        merge_materials(data,materials);self.assertEqual(data['books'][0]['kind'],'audio');self.assertEqual(data['books'][0]['note_coverage']['thoughts'],'unsupported')


if __name__=='__main__':unittest.main()
