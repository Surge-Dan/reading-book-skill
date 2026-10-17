"""Build a separate editorial sample, never a formal job result or pipeline cache."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'reading-yearbook-skill/scripts'))
from serve_ebook import offline_page


def build():
    directory = ROOT / 'output/reading-content-sample-20261017'
    directory.mkdir(parents=True, exist_ok=True)
    text = (ROOT / 'tests/fixtures/book-context-sample.md').read_text('utf-8')
    overview = text.split('## 这本书讲了什么\n\n', 1)[1].split('\n## ', 1)[0]
    contexts = text.split('## 读懂这本书\n\n', 1)[1].split('\n## ', 1)[0].split('### ')[1:]
    method = text.split('### 给产品定价前，先把这六件事想清楚\n\n', 1)[1].split('\n## ', 1)[0]
    review = text.split('## 我的书评\n\n', 1)[1].split('\n---', 1)[0]
    roles = {'element_id':'roles','quote':'卡两头，保中间','location':'岗位职责相关读书笔记', 'source_type':'secondary',
             'url':'https://blog.nowcoder.net/n/d1e665fb1288473285a0a3625e865a29'}
    pricing = {'element_id':'pricing','quote':'确定企业目标','location':'定价相关读书笔记', 'source_type':'secondary',
               'url':'https://blog.nowcoder.net/n/bee3ba5ac54a4a71bda6caa88ac8ea7b'}
    a = {'book':{'title':'YES！产品经理','author':'汤圆、老马 · 阅读样稿'}, 'overview':overview,
         'input_mode':'title','quality_status':'needs_review',
         'book_context':[{'kind':kind,'title':part.split('\n',1)[0], 'explanation':part.split('\n',1)[1].strip(),'sources':[roles,pricing]}
                         for kind,part in zip(('logic','intent'), contexts)],
         'themes':[], 'methods':[{'id':'pricing','title':'给产品定价前，先把这六件事想清楚',
             'interpretation':method.replace('**',''), 'sources':[pricing]}],
         'cases':[], 'counterexamples':[], 'insights':[], 'glossary':[], 'references':[],
         'review':{'status':'ready','reason':'','paragraphs':[{'text':p,'sources':[roles],'quotes':[]} for p in review.split('\n\n') if p.strip()]},
         'limitations':['内容与界面样稿，不是新完成的整书蒸馏。依据公开书目及二手读书笔记整理；未核验原书全文。'],
         'coverage':{'complete':False},
         'bibliography':[{'type':'secondary','title':s['location'],'url':s['url'],'accessed_at':'2026-10-17'} for s in (roles,pricing)]}
    target = directory / 'preview.html'
    page = offline_page(a, text)
    # This sample is a reading preview, not a second live upload workbench.
    page = page.replace('</head>', '<style>.ebook-upload-area,.ebook-heading,.ebook-connection-row{display:none!important}</style></head>')
    target.write_text(page, encoding='utf-8')
    return target


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--screenshots', action='store_true')
    args = parser.parse_args()
    target = build()
    print(target)
    if args.screenshots:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless=True)
            try:
                for label, width, height in [('desktop',1280,900),('mobile',375,812)]:
                    page = browser.new_page(viewport={'width':width,'height':height}, reduced_motion='reduce')
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(target.as_uri(), wait_until='load')
                    page.locator('#ebookResultShell').evaluate('(e)=>e.scrollIntoView({block:"start"})')
                    assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
                    assert not errors, errors
                    page.screenshot(path=str(target.parent / (label+'.png')))
                    page.close()
            finally:
                browser.close()
