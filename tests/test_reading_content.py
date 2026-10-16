import copy
import importlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'reading-yearbook-skill/scripts'))


class ReadingContentTests(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('ebook_reading'), '缺少共享阅读整理契约')
        return importlib.import_module('ebook_reading')

    def setUp(self):
        self.source = {'element_id':'e1','quote':'先观察，再决定。','location':'第一章'}
        self.elements = [{'element_id':'e1','text':'先观察，再决定。信息不足时暂缓。','location':'第一章'}]
        self.topics = [{'id':'t1','title':'观察与决定','importance':'core','status':'read',
                        'sources':[self.source],'gap':''}]
        self.analysis = {'book':{'title':'测试书','author':''},'overview':'观察与决定', 'themes':[{'title':'先观察','explanation':'分开观察和判断','sources':[self.source]}],
                         'methods':[], 'topic_coverage':[{'topic_id':'t1','status':'explained','item_refs':['themes:0'],'reason':'解释了原则'}]}

    def test_map_missing_topic_requires_explicit_gap(self):
        m=self.module(); topics=copy.deepcopy(self.topics)
        topics[0].update(status='missing', sources=[], gap='')
        with self.assertRaises(ValueError): m.validate_map(topics,self.elements)
        topics[0]['gap']='没有取得正文'
        self.assertEqual(m.validate_map(topics,self.elements)[0]['status'],'missing')

    def test_every_topic_requires_actual_destination_with_shared_evidence(self):
        m=self.module()
        m.validate_coverage(self.analysis,self.topics)
        self.analysis['topic_coverage']=[]
        with self.assertRaises(ValueError): m.validate_coverage(self.analysis,self.topics)
        self.analysis['topic_coverage']=[{'topic_id':'t1','status':'explained','item_refs':['methods:0'],'reason':'fake'}]
        with self.assertRaises(ValueError): m.validate_coverage(self.analysis,self.topics)

    def test_thin_evidence_never_becomes_deep_reading(self):
        m=self.module()
        status=m.reading_status(self.analysis, self.topics, 'title', [])
        self.assertEqual(status['level'],'introduction')
        topics=copy.deepcopy(self.topics)+[dict(self.topics[0],id='t2',status='missing',sources=[],gap='缺正文')]
        self.assertEqual(m.reading_status(self.analysis,topics,'title',[])['level'],'partial')

    def test_literature_does_not_need_methods_and_marketing_is_not_deep_evidence(self):
        m=self.module()
        self.assertEqual(m.reading_status(self.analysis,self.topics,'title',[{'type':'preview','content_kind':'excerpt'}])['level'],'public_reading')
        self.analysis['methods']=[{'title':'营销页提及的方法'}]
        self.assertEqual(m.reading_status(self.analysis,self.topics,'title',[{'type':'publisher','content_kind':'introduction'}])['level'],'introduction')

    def test_review_rejects_invented_quote_and_unbound_paragraph(self):
        m=self.module()
        review={'status':'ready','reason':'','paragraphs':[{'text':'我更在意作者如何处理信息不足。','sources':[self.source],'quotes':[]}]}
        m.validate_review(review,self.elements,{'e1'})
        review['paragraphs'][0]['text']='作者写道“未经证实的名句”。'
        with self.assertRaises(ValueError): m.validate_review(review,self.elements,{'e1'})
        review['paragraphs'][0].update(text='我更在意作者的判断。',sources=[])
        with self.assertRaises(ValueError): m.validate_review(review,self.elements,{'e1'})

    def test_review_direct_quote_must_be_present_and_exact(self):
        m=self.module()
        review={'status':'ready','reason':'','paragraphs':[{'text':'我留意到“先观察，再决定。”这句话。','sources':[self.source],'quotes':[self.source]}]}
        m.validate_review(review,self.elements,{'e1'})
        review['paragraphs'][0]['quotes'][0]=dict(self.source,quote='先决定，再观察。')
        with self.assertRaises(ValueError): m.validate_review(review,self.elements,{'e1'})

    def test_review_failure_preserves_other_content_without_fake_success(self):
        m=self.module()
        def call(*args,**kwargs):
            kwargs['validate']({'status':'ready','reason':'','paragraphs':[{'text':'“假名句”','sources':[self.source],'quotes':[]}]})
        result=m.add_review(copy.deepcopy(self.analysis),{'elements':self.elements},call,'title','')
        self.assertEqual(result['review']['status'],'unavailable')
        self.assertEqual(len(result['themes']),1)

    def test_research_keeps_paraphrased_reading_notes_separate_from_quotes(self):
        from test_book_title import evidence, candidate
        from ebook_title import source_document
        package=evidence()
        package['sources'][0]['notes']='作者要求先把问题记录下来，再对照不同方案；条件不足的场景另行处理。'
        doc=source_document(package,candidate())
        self.assertEqual(doc['source_notes'][0]['text'],package['sources'][0]['notes'])
        self.assertEqual(doc['elements'][0]['text'],package['sources'][0]['excerpts'][0])

    def test_research_without_content_map_is_rejected(self):
        from test_book_title import evidence, candidate
        from ebook_title import source_document
        package=evidence(); package.pop('content_map')
        with self.assertRaises(ValueError): source_document(package,candidate())

    def test_upload_generates_separate_review_and_insights_contract(self):
        from ebook_pipeline import distill
        from test_ebook_core import ContractRunner
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'book.txt'; path.write_text('先观察，再决定。信息不足时暂缓。',encoding='utf-8')
            result=distill(path,Path(tmp)/'deep',ContractRunner())
            self.assertEqual(result['review']['status'],'ready')
            self.assertEqual(result['reading_status']['level'],'provided_text')
            self.assertTrue(result['content_map'])

    def test_non_object_review_does_not_discard_upload(self):
        from ebook_pipeline import distill
        from test_ebook_core import ContractRunner
        class MalformedReview(ContractRunner):
            def generate(self,prompt,*args,**kwargs):
                if 'OUTPUT_CONTRACT:reading_review' in prompt: return ['wrong response']
                return super().generate(prompt,*args,**kwargs)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'book.txt'; path.write_text('先观察，再决定。',encoding='utf-8')
            result=distill(path,Path(tmp)/'deep',MalformedReview())
            self.assertEqual(result['review']['status'],'unavailable')
            self.assertTrue((Path(tmp)/'deep/analysis.json').is_file())
        def failed_call(*args,**kwargs): raise ValueError('provider authentication failed')
        with self.assertRaisesRegex(ValueError,'authentication'):
            self.module().add_review(self.analysis,{'elements':self.elements},failed_call,'title','')

    def test_review_provider_failure_keeps_partial_result_and_cancel_still_stops(self):
        from ebook_pipeline import distill
        from test_ebook_core import ContractRunner
        class FailedReview(ContractRunner):
            cancel=False
            def generate(self,prompt,*args,**kwargs):
                if 'OUTPUT_CONTRACT:reading_review' in prompt:
                    if self.cancel: raise InterruptedError('cancelled')
                    raise ValueError('provider authentication failed with private detail')
                return super().generate(prompt,*args,**kwargs)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'book.txt'; path.write_text('先观察，再决定。',encoding='utf-8')
            result=distill(path,Path(tmp)/'deep',FailedReview())
            self.assertEqual(result['review']['status'],'unavailable')
            self.assertEqual(result['quality_status'],'needs_review')
            self.assertNotIn('private detail',str(result))
            self.assertTrue((Path(tmp)/'deep/analysis.json').is_file())
            runner=FailedReview(); runner.cancel=True
            with self.assertRaises(InterruptedError): distill(path,Path(tmp)/'cancel',runner)
            self.assertFalse((Path(tmp)/'cancel/analysis.json').exists())


if __name__ == '__main__': unittest.main()
