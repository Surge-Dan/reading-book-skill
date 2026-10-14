"""Source-backed smoke: replies authored in this chat, NOT independent quality eval.

The source was actually read on 2026-10-14. Only the public book-description
question is used; no methods are invented from a marketing page.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'reading-yearbook-skill/scripts'))
from serve_ebook import JobStore
from ebook_agent_bridge import AgentRunner


def main():
    root = Path('output/title-source-smoke-20261014')
    store = JobStore(root, AgentRunner())
    owner = {'session':'01a0e80d-00df-7661-b8f7-6291b079d293-source-smoke','host':'codex-desktop','model':'unknown'}
    book = {'id':'mom-test','title':'The Mom Test','author':'Rob Fitzpatrick',
            'edition':'版本未确认','identity_url':'https://www.momtestbook.com/'}
    quote = 'How to avoid biased feedback?'
    replies = {
        'title-identify':{'status':'identified','candidates':[book],'searches_used':0},
        'title-research':{'book_key':'mom-test','searches_used':0,
                         'gaps':['只读取作者官网的书籍介绍，没有整书目录、正文或完整步骤。'],
                         'sources':[{'id':'official','book_key':'mom-test','url':book['identity_url'],
                                     'title':'The Mom Test · Practical, not academic','type':'author',
                                     'accessed_at':'2026-10-14','excerpts':[quote]}]},
        'title-analysis':{'schema_version':1,'book':{'title':book['title'],'author':book['author']},
                          'overview':'作者官网将避免带偏的反馈列为本书处理的实际问题。这只是有来源的主题概览，不等于完整方法或整书蒸馏。',
                          'themes':[{'title':'识别带偏的反馈','explanation':'公开介绍把这一点作为本书讨论的问题，但已读摘录不包含操作步骤，因此不补写方法。',
                                     'sources':[{'element_id':'official-1','quote':quote,'location':'Practical, not academic'}]}],
                          'methods':[],'cases':[],'counterexamples':[],'glossary':[],
                          'limitations':['当前材料仅支持主题识别，不能证明作者的完整方法、边界或案例。']}}
    try:
        job = store.create_title(book['title'], book['author'])
        store.agent_action(job['id'], 'claim', owner)
        accepted = set()
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            current = store.get(job['id'])
            if current['state'] == 'completed': break
            if current['state'] in ('failed','interrupted','cancelled'): raise AssertionError(current.get('error') or current['message'])
            next_item = store.agent_action(job['id'], 'next', {'session':owner['session']})
            if next_item['request']:
                request = json.loads(Path(next_item['request']['request_path']).read_text('utf-8'))
                if request['request_id'] not in accepted:
                    store.agent_action(job['id'], 'submit', {'session':owner['session'],'request_id':request['request_id'],
                                                           'answer':replies[request['stage']]})
                    accepted.add(request['request_id'])
            time.sleep(.01)
        current = store.get(job['id'])
        assert current['state'] == 'completed', current['state']
        assert len(accepted) == 3
        assert current['analysis']['input_mode'] == 'title'
        assert current['analysis']['coverage']['full_text'] is False
        assert current['analysis']['methods'] == []
        assert '未核验全文' in current['digest']
        deep = store.jobs_dir/job['id']/'deep'
        report = {'kind':'source_backed_controlled_smoke_not_independent_quality_eval','stages':3,
                  'source':book['identity_url'],'result':str(deep/'index.html'),'quality':'needs_review'}
        print(json.dumps(report, ensure_ascii=False))
    finally: store.close()


if __name__ == '__main__': main()
