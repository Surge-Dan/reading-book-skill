"""Regression checks for source-bound book context and shared writing rules."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'reading-yearbook-skill/scripts'))
import ebook_reading as reading


class BookContextTests(unittest.TestCase):
    def setUp(self):
        self.source = {'element_id':'e1','quote':'先观察，再决定。','location':'第一章'}
        self.elements = [{'element_id':'e1','text':'先观察，再决定。','location':'第一章'}]
        self.context = [{'kind':'logic','title':'先弄清问题，再做选择',
                         'explanation':'观察提供判断的基础。','sources':[self.source]}]

    def test_context_is_optional_for_legacy_results_but_source_bound_when_present(self):
        self.assertTrue(hasattr(reading, 'validate_context'), '缺少书籍理解层来源校验')
        reading.validate_context({}, self.elements)
        reading.validate_context({'book_context':self.context}, self.elements)
        self.assertTrue(self.context[0].get('source_verified'), '通过引文核对的理解层应记录来源匹配状态')
        for change in ('quote','kind','empty'):
            rows = copy.deepcopy(self.context)
            if change == 'quote': rows[0]['sources'][0]['quote'] = '虚构的书中情节'
            if change == 'kind': rows[0]['kind'] = 'unknown'
            if change == 'empty': rows[0]['explanation'] = ''
            with self.subTest(change=change), self.assertRaises(ValueError):
                reading.validate_context({'book_context':rows}, self.elements)

    def test_review_can_use_context_evidence_and_receives_shared_writing_rules(self):
        def call(stage, rules, payload, validate):
            self.assertIn('随书调整', rules)
            self.assertEqual(payload['book_context'], self.context)
            value = {'status':'ready','reason':'','paragraphs':[{
                'text':'我认同先观察再判断的谨慎。','sources':[self.source],'quotes':[]}]}
            validate(value)
            return value
        result = reading.add_review({'book':{'title':'测试书'}, 'overview':'观察与决定',
                                     'book_context':self.context}, {'elements':self.elements}, call, 'title', '')
        self.assertEqual(result['review']['status'], 'ready')

    def test_markdown_keeps_process_at_bottom_and_includes_context(self):
        from test_book_title import analysis_reply
        from ebook_pipeline import _render_outputs
        a = analysis_reply()
        a.update(book_context=self.context, references=[], input_mode='title', quality_status='needs_review',
                 coverage={'scope_note':'基于公开资料，未核验全文','candidate_dispositions':[]},
                 reading_status={'label':'公开资料部分解读','reason':'内部处理记录'},
                 review={'status':'ready','paragraphs':[{'text':'具体的书评。','sources':[self.source],'quotes':[]}]})
        with tempfile.TemporaryDirectory() as tmp:
            _render_outputs(Path(tmp), a, {}, [], [], [])
            md = (Path(tmp)/'DIGEST.md').read_text('utf-8')
        body, refs = md.split('## 参考资料', 1)
        self.assertIn('先弄清问题，再做选择', body)
        for unwanted in ('AI 撰写','AI 解释：','内部处理记录','来源核对：','状态：needs_review'):
            self.assertNotIn(unwanted, body)
        self.assertIn('未核验全文', refs)
        self.assertIn('e1', refs)

    def test_both_analysis_entries_receive_same_rules_and_preserve_context(self):
        from test_book_title import analysis_reply, candidate, evidence, review_reply
        from test_ebook_core import ContractRunner
        from ebook_title import distill_title
        from ebook_pipeline import distill
        class TitleRunner:
            def info(self): return {'mode':'current-agent-instructed-tools'}
            def prepare(self, stage, context, key): self.stage = stage
            def generate(runner, prompt, **kwargs):
                if runner.stage == 'title-identify': return {'status':'identified','candidates':[candidate()],'searches_used':1}
                if runner.stage == 'title-research': return evidence()
                if runner.stage == 'reading-review': return review_reply()
                self.assertIn(reading.writing_rules(), prompt)
                value = analysis_reply()
                value['book_context'] = [dict(self.context[0], sources=value['themes'][0]['sources'])]
                return value
            def commit(self, callback): callback()
        class UploadRunner(ContractRunner):
            def generate(runner, prompt, **kwargs):
                value = super().generate(prompt, **kwargs)
                if 'OUTPUT_CONTRACT:analysis\n' in prompt:
                    self.assertIn(reading.writing_rules(), prompt)
                    value['book_context'] = [dict(self.context[0], sources=value['themes'][0]['sources'])]
                return value
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = distill_title({'title':'测试书'}, root/'title', TitleRunner())
            self.assertTrue(result['book_context'])
            path = root/'book.txt'; path.write_text('先观察，再决定。', encoding='utf-8')
            result = distill(path, root/'upload', UploadRunner())
            self.assertTrue(result['book_context'])
            self.assertIn(self.context[0]['title'], (root/'upload/DIGEST.md').read_text('utf-8'))


if __name__ == '__main__': unittest.main()
