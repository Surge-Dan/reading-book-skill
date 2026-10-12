"""Controlled browser acceptance. Upload only; never calls any model."""
import sys
import tempfile
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'reading-yearbook-skill/scripts'))
from serve_ebook import JobStore, create_server
from ebook_agent_bridge import AgentRunner
from playwright.sync_api import sync_playwright


def main():
    with tempfile.TemporaryDirectory() as tmp:
        store = JobStore(tmp, AgentRunner())
        server = create_server(store)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, executable_path='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
                context = browser.new_context(permissions=['clipboard-read', 'clipboard-write'])
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}')
                page.wait_for_load_state('networkidle')
                layouts = page.evaluate('''async () => {
                  const analysis={book:{title:'受控分享测试'},quality_status:'needs_review',
                    evaluation_limit:'同一对话，非隔离对照，不证明任务增益',
                    limitations:['覆盖缺口 TEST_GAP'],coverage:{complete:false,warnings:['覆盖缺口 TEST_GAP']}};
                  const art=ReadingShareArtwork.createDigest({analysis});const result=[];
                  for(const ratio of ['1:1','3:4','4:5']){
                    const pages=await art.pages([{id:'overview',title:'整书概览',kind:'overview',text:'测试内容 '.repeat(150)}],ratio);
                    const rendered=[];
                    for(const page of pages){const canvas=await art.render(page,ratio);rendered.push({text:canvas.readingLayout.text.map(x=>x.text).join(''),png:canvas.toDataURL('image/png').length});}
                    result.push(rendered);
                  }return result;
                }''')
                for pages in layouts:
                    assert 'TEST_GAP' in ''.join(p['text'] for p in pages)
                    for rendered in pages:
                        assert '待核查' in rendered['text'] and '非隔离' in rendered['text']
                        assert rendered['png'] > 2000
                assert '当前助手' in page.locator('#ebookConnection').inner_text()
                page.locator('#ebookFile').set_input_files({'name': 'book.txt', 'mimeType': 'text/plain', 'buffer': b'PRIVATE_SOURCE_MARKER'})
                page.locator('#ebookStartInstruction').wait_for(state='visible')
                assert '等待' in page.locator('#ebookStatus').inner_text() or '回到' in page.locator('#ebookStatus').inner_text()
                page.locator('#ebookStartInstruction').click()
                text = page.evaluate('navigator.clipboard.readText()')
                assert '开始蒸馏' in text
                assert store.token not in text and store.agent_token not in text and 'PRIVATE_SOURCE_MARKER' not in text
                assert page.locator('#ebookUpload').is_disabled()
                page.locator('#ebookCancel').click()
                page.locator('#ebookRetry').wait_for(state='visible')
                page.locator('#ebookRetry').click()
                page.locator('#ebookStartInstruction').wait_for(state='visible')
                assert not errors, errors
                browser.close()
            print('PASS current-agent upload / waiting / copy privacy / cancel / retry; no model calls')
        finally:
            server.shutdown()
            server.server_close()
            store.close()


if __name__ == '__main__':
    main()
