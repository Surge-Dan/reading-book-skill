import sys
import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'reading-yearbook-skill/scripts'))
from serve_ebook import offline_page, workbench_page
from test_book_title import analysis_reply


class ReadingRedesignBrowserTests(unittest.TestCase):
    def test_review_and_title_stage_names_are_readable(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless=True)
            try:
                page = browser.new_page()
                for stage, label in [('reading-review','撰写书评'),('title-research','查阅公开资料'),('title-analysis','整理书籍解读')]:
                    job = {'id':'test','state':'awaiting_response','stage':stage}
                    def route_request(route):
                        if '/api/' in route.request.url:
                            route.fulfill(json={'runner':{'available':True,'mode':'current-agent-instructed-tools'},'jobs':[job],'job':job})
                        else:
                            route.fulfill(body=workbench_page({'token':'test'}),content_type='text/html')
                    page.route('**/*',route_request)
                    page.goto('http://reading.test',wait_until='networkidle')
                    self.assertIn(label,page.locator('#ebookProgress').inner_text())
                    page.unroute('**/*',route_request)
            finally: browser.close()

    def test_reading_structure_review_copy_and_real_share_renderer(self):
        a = analysis_reply()
        source = dict(a['themes'][0]['sources'][0], source_type='author')
        a.update(input_mode='title', methods=[], cases=[], counterexamples=[], glossary=[], references=[],
                 reading_status={'level':'partial','label':'部分解读','reason':'尚缺关键章节'},
                 insights=[{'title':'先检查条件','explanation':'条件决定方法的用处。','sources':[source]}],
                 review={'status':'ready','paragraphs':[{'text':'我更在意方法停下来的条件。','sources':[source],'quotes':[]},
                                                      {'text':'保留疑问，比过早下结论更有价值。','sources':[source],'quotes':[]}]})
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless=True)
            try:
                page = browser.new_page(viewport={'width':375,'height':812}, reduced_motion='reduce')
                page.set_content(offline_page(a, '测试正文'), wait_until='load')
                self.assertEqual(page.locator('#ebookResult > section > h3').all_text_contents(),
                                 ['书籍概览','核心观点','对我的启发','我的书评','参考资料'])
                self.assertIn('部分解读', page.locator('#ebookQuality').inner_text())
                self.assertIn('尚缺关键章节', page.locator('#ebookQuality').inner_text())
                self.assertFalse(page.evaluate('document.documentElement.scrollWidth>innerWidth'))
                self.assertEqual(page.evaluate('getComputedStyle(document.documentElement).scrollBehavior'), 'auto')
                review = page.locator('[data-reading-section="review"]')
                self.assertEqual(review.locator('blockquote').count(), 0)
                self.assertIn('AI 撰写', review.inner_text())
                page.evaluate("Object.defineProperty(navigator,'clipboard',{value:{writeText:async text=>{window.copied=text;}}})")
                review.get_by_role('button', name='复制这条').first.click()
                copied = page.evaluate('window.copied')
                for text in ('AI 书评', '未核验全文', source['element_id'], source['quote']): self.assertIn(text, copied)
                self.assertEqual(page.locator('[data-ebook-share="review-0"]').count(), 1)
                page.locator('#ebookShareToggle').click()
                page.wait_for_function("() => !document.getElementById('ebookExportPng').disabled")
                self.assertIn('我的书评 · 1', page.locator('#ebookPage').inner_text())
                self.assertGreater(page.locator('#ebookCanvas').evaluate('(c)=>c.width'), 0)
                review_page = page.locator('#ebookPage option').filter(has_text='我的书评 · 1').first.get_attribute('value')
                page.locator('#ebookPage').select_option(review_page)
                with page.expect_download() as download:
                    page.locator('#ebookExportPng').click()
                self.assertTrue(download.value.suggested_filename.endswith('.png'))
                self.assertGreater(Path(download.value.path()).stat().st_size, 1000)
                self.assertEqual(page.locator('.ebook-reading-nav a').all_text_contents(), ['书籍概览','核心观点','对我的启发','我的书评','参考资料'])
                page.set_viewport_size({'width':1280,'height':900})
                self.assertFalse(page.evaluate('document.documentElement.scrollWidth>innerWidth'))
                self.assertEqual(review.evaluate('(e)=>getComputedStyle(e).opacity'), '1')
                page.locator('.ebook-reading-nav summary').click()
                page.locator('.ebook-reading-nav a').filter(has_text='核心观点').click()
                page.wait_for_function("() => document.querySelector('.ebook-reading-nav a[aria-current]').textContent==='核心观点'", timeout=3000)
                self.assertGreaterEqual(page.locator('.ebook-reading-nav').evaluate('(e)=>e.getBoundingClientRect().top'),
                                        page.locator('.masthead').evaluate('(e)=>e.getBoundingClientRect().bottom'))
            finally: browser.close()

    def test_old_result_and_failed_review_remain_readable(self):
        a = analysis_reply()
        a.update(methods=[], cases=[], counterexamples=[], glossary=[], references=[],
                 review={'status':'unavailable','reason':'引用待核查','paragraphs':[]})
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless=True)
            try:
                page = browser.new_page()
                page.set_content(offline_page(a, ''), wait_until='load')
                self.assertIn('书评暂未生成', page.locator('#ebookResult').inner_text())
                self.assertEqual(page.locator('[data-ebook-share^="review-"]').count(), 0)
                self.assertEqual(page.get_by_role('heading',name='值得带走的方法',exact=True).count(), 0)
                self.assertEqual(page.get_by_role('heading',name='核心观点',exact=True).count(), 1)
                del a['review']
                a['cases'] = [{'title':'练习','explanation':'练习不能证明原方法有效。','case_origin':'ai_exercise','sources':a['themes'][0]['sources']}]
                page.set_content(offline_page(a, ''), wait_until='load')
                self.assertEqual(page.get_by_role('heading',name='我的书评',exact=True).count(), 0)
                self.assertEqual(page.get_by_role('heading',name='关键案例',exact=True).count(), 1)
                page.evaluate("Object.defineProperty(navigator,'clipboard',{value:{writeText:async text=>{window.copied=text;}}})")
                page.locator('[data-reading-section="cases"]').get_by_role('button',name='复制这条').click()
                self.assertIn('不是原书案例',page.evaluate('window.copied'))
                self.assertIn('所提供正文',page.evaluate('window.copied'))
            finally: browser.close()


if __name__ == '__main__': unittest.main()
