"""Actual saved-book UI/export acceptance; not independent whole-book quality review."""
import json
import sys
import zipfile
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
JOB='9a1b9f3021a343508025f12b52981bff'
OUT=ROOT/'output/reading-redesign-20261016'
PRIVATE=ROOT/'output/current-agent-test-20261012/.ebook-workbench/jobs'/JOB


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    analysis=json.loads((PRIVATE/'deep/analysis.json').read_text('utf-8'))
    research=json.loads((PRIVATE/'research-reply.json').read_text('utf-8'))
    elements={s['id']+'-'+str(i):t for s in research['sources'] for i,t in enumerate(s['excerpts'],1)}
    records=[s for k in ('themes','methods','insights') for item in analysis[k] for s in item['sources']]
    records += [s for p in analysis['review']['paragraphs'] for s in p['sources']+p['quotes']]
    assert records and all(s['quote'] in elements[s['element_id']] for s in records)
    errors=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless=True)
        try:
            page=browser.new_page(viewport={'width':1280,'height':900},accept_downloads=True)
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto('http://127.0.0.1:55997/results/'+JOB+'.html',wait_until='networkidle')
            assert '部分解读' in page.locator('#ebookQuality').inner_text()
            assert page.locator('[data-reading-section="review"] p').count()>=2
            assert page.get_by_role('heading',name='RIA 方法',exact=True).count()==0
            assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
            page.screenshot(path=str(OUT/'desktop.png'),full_page=True)
            page.set_viewport_size({'width':375,'height':812})
            assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
            page.screenshot(path=str(OUT/'mobile.png'),full_page=True)
            page.locator('[data-reading-section="review"]').screenshot(path=str(OUT/'review.png'))
            page.evaluate("Object.defineProperty(navigator,'clipboard',{value:{writeText:async text=>window.copied=text}})")
            page.locator('[data-reading-section="review"]').get_by_role('button',name='复制这条').first.click()
            assert '未核验全文' in page.evaluate('window.copied')
            page.locator('#ebookShareToggle').click()
            for choice in page.locator('[data-ebook-share]').all():
                choice.set_checked(choice.get_attribute('data-ebook-share').startswith('review-'))
            page.wait_for_function("() => !document.getElementById('ebookExportZip').disabled")
            with page.expect_download() as download: page.locator('#ebookExportPng').click()
            download.value.save_as(str(OUT/'review-share.png'))
            with page.expect_download() as download: page.locator('#ebookExportZip').click()
            download.value.save_as(str(OUT/'review-share.zip'))
            with zipfile.ZipFile(OUT/'review-share.zip') as archive:
                pages=len(archive.namelist())
                assert pages>=2 and all(archive.read(name).startswith(b'\x89PNG') for name in archive.namelist())
            with page.expect_download() as download: page.locator('#ebookDownloadHtml').click()
            download.value.save_as(str(OUT/'book-result.html'))
            page.goto((OUT/'book-result.html').as_uri(),wait_until='load')
            assert page.locator('[data-reading-section="review"]').is_visible()
            assert not errors,errors
        finally: browser.close()
    report={'kind':'current_chat_public_source_book_acceptance_not_full_text_or_independent_quality',
            'job':JOB,'stages':4,'reading_status':analysis['reading_status'],'methods':len(analysis['methods']),
            'review_paragraphs':len(analysis['review']['paragraphs']),'exact_source_records_checked':len(records),
            'share_zip_pages':pages,'browser_errors':errors,'source_access_dates':[s['accessed_at'] for s in research['sources']]}
    (OUT/'acceptance.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':main()
