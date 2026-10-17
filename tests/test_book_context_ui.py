import sys
import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'reading-yearbook-skill/scripts'))
from serve_ebook import offline_page
from test_book_title import analysis_reply


class BookContextBrowserTests(unittest.TestCase):
    def test_reading_navigation_stays_in_document_flow_and_links_still_work(self):
        a = analysis_reply()
        a['overview'] = '\n\n'.join(['概览中的完整内容。'] * 70)
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless=True)
            try:
                for width in (375,1280):
                    page = browser.new_page(viewport={'width':width,'height':812}, reduced_motion='reduce')
                    page.set_content(offline_page(a,''), wait_until='load')
                    nav = page.locator('.ebook-reading-nav')
                    self.assertEqual(nav.evaluate('(e)=>getComputedStyle(e).position'), 'static')
                    nav.evaluate('(e)=>e.open=true')
                    nav.get_by_role('link',name='核心观点',exact=True).click()
                    self.assertTrue(page.url.endswith('#ebook-reading-themes'))
                    self.assertLess(nav.evaluate('(e)=>e.getBoundingClientRect().bottom'), 0)
                    self.assertFalse(page.evaluate('document.documentElement.scrollWidth>innerWidth'))
                    page.close()
            finally:
                browser.close()

    def test_both_modes_keep_context_and_clean_body_with_sources_at_bottom(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless=True)
            try:
                page = browser.new_page(viewport={'width':375,'height':812})
                for mode in ('title','upload'):
                    a = analysis_reply()
                    source = a['themes'][0]['sources'][0]
                    a.update(input_mode=mode, book_context=[{'kind':'logic','title':'问题怎样展开','explanation':'先理解处境，再比较选择。','sources':[source]}],
                             reading_status={'label':'部分解读','reason':'内部原因'},
                             review={'status':'ready','paragraphs':[{'text':'我喜欢这个具体的选择。','sources':[source],'quotes':[]}]})
                    extra_source = dict(source, quote='补充参考的独立引文', location='附录定位')
                    a['glossary'] = [{'term':'补充词','definition':'一个词的解释','sources':[extra_source]}]
                    page.set_content(offline_page(a,''), wait_until='load')
                    self.assertEqual(page.locator('[data-reading-section="book-context"] h4').count(), 1, '缺少书籍理解展示')
                    self.assertEqual(page.locator('[data-reading-section="book-context"] h4').inner_text(), '问题怎样展开')
                    self.assertEqual(page.locator('#ebookQuality').inner_text(), '')
                    main = page.locator('[data-reading-section="themes"]')
                    for text in ('查看依据','核验状态','AI 解释：'):
                        self.assertNotIn(text, main.inner_text())
                    self.assertNotIn('AI 撰写', page.locator('[data-reading-section="review"]').inner_text())
                    refs = page.locator('[data-reading-section="references"]')
                    self.assertIn(source['quote'], refs.text_content())
                    self.assertIn('内部原因', refs.text_content())
                    self.assertIn('补充参考的独立引文', refs.text_content())
                    page.evaluate("Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async text=>{window.copied=text;}}})")
                    page.locator('[data-reading-section="review"]').get_by_role('button',name='复制这条').click()
                    self.assertIn('我喜欢这个具体的选择。', page.evaluate('window.copied'))
                    self.assertNotIn('AI 书评', page.evaluate('window.copied'))
                    self.assertFalse(page.evaluate('document.documentElement.scrollWidth>innerWidth'))
                    result = page.evaluate("""async()=>{const art=ReadingShareArtwork.createDigest({analysis:EBOOK_RESULT.analysis});
                        const pages=await art.pages([{id:'m',kind:'methods',title:'方法',text:'怎么做'}],'3:4');
                        return pages.flatMap(p=>p.rows.map(r=>r.text)).join('');}""")
                    self.assertNotIn('覆盖与局限', result)
                    self.assertNotIn('核验状态', result)
            finally:
                browser.close()


if __name__ == '__main__': unittest.main()
