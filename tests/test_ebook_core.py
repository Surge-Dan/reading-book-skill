import importlib
import sys
import tempfile
import unittest
import threading
import zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'reading-yearbook-skill/scripts'))

class CoreTests(unittest.TestCase):
    def module(self, name):
        try: return importlib.import_module(name)
        except ImportError: self.fail('Missing required module ' + name)

    def test_long_paragraph_and_last_chapter_are_preserved(self):
        m = self.module('ebook_document')
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'book.md'; p.write_text('# First\n' + '甲'*19000 + '\n# Last\n末章证据', encoding='utf-8')
            doc = m.parse_document(p)
            chunks = m.build_chunks(doc, max_chars=3000)
            self.assertEqual(''.join(e['text'] for e in doc['elements']), ''.join(e['text'] for c in chunks for e in c['elements']))
            self.assertIn('末章证据', chunks[-1]['elements'][-1]['text'])
            self.assertEqual(doc['source_hash'], m.parse_document(p)['source_hash'])

    def test_literary_pipeline_runs_all_stages_and_reuses_cache(self):
        m = self.module('ebook_pipeline')
        class Runner:
            calls = []
            def info(self): return {'name':'test', 'available':True}
            def generate(self, prompt, schema=None, cancel_event=None):
                self.calls.append(prompt)
                if 'OUTPUT_CONTRACT:analysis' in prompt:
                    return {'schema_version':1,'book':{'title':'小说','author':''},'overview':'人物与时代','themes':[], 'methods':[], 'cases':[], 'counterexamples':[], 'glossary':[], 'limitations':[]}
                return {'notes':'文学内容', 'candidates':[], 'tasks':[]}
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'novel.txt'; p.write_text('人物在河边回忆童年。', encoding='utf-8'); r=Runner()
            result=m.distill(p,Path(d)/'out',r)
            self.assertEqual(result['methods'],[]); self.assertTrue(result['coverage']['complete'])
            self.assertGreaterEqual(len(r.calls),11)
            count=len(r.calls); m.distill(p,Path(d)/'out',r); self.assertEqual(count,len(r.calls))
            self.assertTrue((Path(d)/'out/DIGEST.md').exists())

    def test_budget_gate_precedes_ai(self):
        m=self.module('ebook_pipeline')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'large.txt'; p.write_text('字'*200000,encoding='utf-8')
            with self.assertRaises(m.BudgetRequired): m.distill(p,Path(d)/'out',None)

    def test_runner_rejects_non_json(self):
        m=self.module('ebook_runner')
        with self.assertRaises(ValueError): m.parse_json('Here is an answer {"x":1}')
        self.assertEqual(m.parse_json('{"x":1}'), {'x':1})

    def test_epub_spine_order_and_archive_safety(self):
        m=self.module('ebook_document')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'book.epub'
            with zipfile.ZipFile(p,'w') as z:
                z.writestr('META-INF/container.xml','<container><rootfile full-path="book.opf"/></container>')
                z.writestr('book.opf','<package xmlns="urn:test"><metadata><title>T</title></metadata><manifest><item id="a" href="a.xhtml"/><item id="b" href="b.xhtml"/></manifest><spine><itemref idref="b"/><itemref idref="a"/></spine></package>')
                z.writestr('a.xhtml','<p>first</p>'); z.writestr('b.xhtml','<p>second</p>')
            doc=m.parse_document(p); self.assertEqual(doc['elements'][0]['text'],'second\n')
            with zipfile.ZipFile(p,'a') as z: z.writestr('../escape','bad')
            with self.assertRaisesRegex(ValueError,'Unsafe'): m.parse_document(p)

    def test_bad_source_never_validated(self):
        m=self.module('ebook_pipeline')
        doc={'elements':[{'element_id':'e1','text':'真实原文','location':'line 1'}]}
        data={'themes':[],'methods':[{'title':'伪造','sources':[{'element_id':'e1','quote':'不存在'}],'verification':{'status':'validated'}}],'cases':[],'counterexamples':[],'glossary':[]}
        self.assertEqual(m._validate_sources(data,doc),['伪造'])
        self.assertEqual(data['methods'][0]['verification']['status'],'needs_review')

    def test_cancel_precedes_work(self):
        m=self.module('ebook_pipeline'); event=threading.Event(); event.set()
        with self.assertRaises(InterruptedError): m.distill('does-not-exist', 'out',None,cancel_event=event)

    def test_manifest_verifies_vendored_resources(self):
        m=self.module('ebook_pipeline'); manifest=m.upstream_manifest()
        self.assertEqual(manifest['commit'],'a28de55ba881b9928956a55048f743f7a9e3b23e')
        self.assertGreater(len(manifest['files']),10)

    def test_failed_retry_removes_formal_completion(self):
        m=self.module('ebook_pipeline')
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)/'out'; out.mkdir(); (out/'analysis.json').write_text('{"quality_status":"completed"}')
            p=Path(d)/'empty.txt'; p.write_text('')
            with self.assertRaises(ValueError): m.distill(p,out,None)
            self.assertFalse((out/'analysis.json').exists())

    def test_malformed_source_entries_raise_value_error(self):
        m=self.module('ebook_pipeline')
        data={'themes':[{'title':'T','explanation':'E','sources':['not-an-object']}], 'methods':[],'cases':[],'counterexamples':[],'glossary':[],'limitations':[],'schema_version':1,'book':{'title':'T','author':''},'overview':'O'}
        with self.assertRaises(ValueError): m._analysis_contract(data)

    def test_chinese_quote_limit_is_enforced(self):
        m=self.module('ebook_pipeline'); quote='书'*151
        doc={'elements':[{'element_id':'e1','text':quote,'location':'line 1'}]}
        data={'themes':[],'methods':[{'title':'T','sources':[{'element_id':'e1','quote':quote}], 'verification':{}}],'cases':[],'counterexamples':[],'glossary':[]}
        self.assertEqual(m._validate_sources(data,doc),['T'])

    def test_pressure_trials_use_real_batch_outputs_and_matching_ids(self):
        m=self.module('ebook_pipeline')
        class Runner:
            calls=[]
            def info(self): return {'name':'test','available':True}
            def generate(self,prompt,schema=None,cancel_event=None):
                self.calls.append(prompt)
                if 'OUTPUT_CONTRACT:analysis\n' in prompt:
                    return {'schema_version':1,'book':{'title':'T','author':''},'overview':'O','themes':[], 'methods':[{'id':'m1','title':'M','interpretation':'I','trigger':'T','steps':['check'],'example':'E','boundaries':['B'],'sources':[{'element_id':'e0000001','quote':'原文','location':'line 1'}],'verification':{'status':'validated','V1':True,'V2':True,'V3':True,'source_sufficiency':{'reason':'complete rule'},'walkthrough':{'input':'x','steps':['check'],'output':'y'},'task_utility':'check omissions'}}], 'cases':[],'counterexamples':[],'glossary':[],'limitations':[]}
                if 'OUTPUT_CONTRACT:pressure_suite' in prompt:
                    return {'test_cases':[{'id':k,'method_id':'m1','kind':k,'task':'Perform '+k,'input':{},'checks':['result correct']} for k in ('normal','missing_input','negative','adjacent')]}
                if 'OUTPUT_CONTRACT:baseline_results' in prompt or 'OUTPUT_CONTRACT:execution_results' in prompt:
                    return {'results':[{'case_id':k,'answer':'actual completed task','chosen_method':'m1'} for k in ('normal','missing_input','negative','adjacent')]}
                if 'OUTPUT_CONTRACT:judgment_results' in prompt:
                    return {'results':[{'case_id':k,'passed':True,'baseline_passed':True,'reasons':['criteria match'],'check_results':[{'check':'result correct','passed':True}]} for k in ('normal','missing_input','negative','adjacent')]}
                return {'notes':'N','candidates':[],'tasks':[]}
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'b.txt'; p.write_text('原文',encoding='utf-8'); r=Runner()
            result=m.distill(p,Path(d)/'out',r)
            self.assertEqual(len(r.calls),15)
            self.assertEqual(result['methods'][0]['verification']['status'],'validated')

    def test_short_chapters_are_batched_without_cost_pause(self):
        m=self.module('ebook_pipeline')
        class Runner:
            calls=0
            def info(self): return {'name':'test','available':True}
            def generate(self,prompt,schema=None,cancel_event=None):
                self.calls+=1
                if 'OUTPUT_CONTRACT:analysis\n' in prompt:
                    return {'schema_version':1,'book':{'title':'T','author':''},'overview':'O','themes':[],'methods':[],'cases':[],'counterexamples':[],'glossary':[],'limitations':[]}
                return {'notes':'N','candidates':[],'tasks':[]}
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'b.md'; p.write_text('\n'.join('# Chapter '+str(i)+'\n'+'字'*100 for i in range(13)),encoding='utf-8'); r=Runner()
            result=m.distill(p,Path(d)/'out',r)
            self.assertEqual(result['coverage']['chunks_total'],13)
            self.assertEqual(r.calls,11)

if __name__ == '__main__': unittest.main()
