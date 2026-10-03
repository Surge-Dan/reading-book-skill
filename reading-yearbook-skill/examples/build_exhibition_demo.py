"""A six-page, fictional reading exhibition. A worked example, never a theme preset."""
from __future__ import annotations

import argparse
from html import escape
from pathlib import Path
import shutil
import sys

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / 'scripts'))
from run_share import prepare_share, write_json, file_digest
from static_graphics import render_graphic
from workflow_fixture import sample_decisions


def build(output: Path) -> None:
    job = prepare_share(2026, SKILL/'assets/sample-data.json', output,
                        ['sample-002','sample-001','sample-005','sample-004'])
    sample_decisions(job, focus='excerpts')  # One book has no personal note.
    job['period'].update(as_of='2026-12-31', complete=True)  # Fictional full-year fixture only.
    job['art_brief'] = {'concept':'阅读展览：物件、片段、内容图解各有职责。仅用于这组虚构材料。',
                        'palette':'炭底／纸色／柠檬黄绿；植物页用暗绿，与本次物件呼应。',
                        'fonts':'Noto Serif SC标题与引文，Noto Sans SC正文、数字和图形。',
                        'sequence':'书册陈列、记录轨迹、摄影观察、假设关系、提问路径、植物标本。'}
    job['directions'][0].update(label='阅读展览（样例）',concept=job['art_brief']['concept'],
        fonts=[{'family':'Noto Serif SC','role':'标题、引文'},{'family':'Noto Sans SC','role':'正文、数字、图解'}],
        references=[{'source':'design.md#2','lesson':'书籍物件与记录共同构图；主视觉变化来自具体内容。'}])
    job['directions'][1].update(label='编辑档案（备选，仅说明）',concept='浅底、多栏笔记与旁注；以内容图解而非物件陈列为主要视觉。',
        references=[{'source':'https://github.com/larashero3-dotcom/lieflat-charts/blob/eace082a317b696c5570c25826a53a7fa113e984/templates/reports/report-10.zh.html',
                     'lesson':'记录、名单、图形交替展开；没有复制代码或素材。'}])
    pages = job['pages']
    blocks = {b['id']:b for p in pages for b in p['blocks']}
    blocks['cover-title']['text'] = '读过的书，\n留下的几件事'
    def add(page, bid, text, refs, kind='editorial'):
        block={'id':bid,'kind':kind,'text':text,'source_refs':refs}
        page['blocks'].append(block)
        blocks[bid]=block
        return bid
    def plan(page, task, structure, description, omit):
        page['storyboard']={'reading_task':task,'evidence_refs':list(dict.fromkeys(r for b in page['blocks'] for r in b.get('source_refs',[]))),
                           'main_visual':{'structure':structure,'description':description},
                           'supporting_blocks':[b['id'] for b in page['blocks']], 'omit':omit}
    def node(nid,bid,x,y,w,h):
        return {'id':nid,'block_id':bid,'x':x,'y':y,'width':w,'height':h}
    def tag(bid, cls='', name='p'):
        return f'<{name} class="{cls}" data-block="{bid}">{escape(blocks[bid]["text"]).replace(chr(10),"<br>")}</{name}>'
    def frame(page, cls, body, label):
        index=pages.index(page)+1
        return f'<article class="page {cls}" id="{page["id"]}"><header><span data-label>年年阅 / 阅读展览</span><span data-status>样例 · 虚构书目与笔记</span></header>{body}<footer><span data-label>{label}</span><span data-label>{index:02d} / 06</span></footer></article>'
    assets=output/'assets'
    assets.mkdir(parents=True,exist_ok=True)
    shutil.copy2(SKILL/'examples/visual-proof-v2/assets/atget-organ-player.jpg',assets/'street.jpg')
    job['assets']=[{'path':'assets/street.jpg','source':'https://www.artic.edu/artworks/55394',
                    'rights':'public-domain; museum API is_public_domain=true', 'sha256':file_digest(assets/'street.jpg'),
                    'role':'visual illustration; not a book cover or reader photograph'}]

    cover,overview,city,decision,questions,plant=pages
    blocks['b-sample-004-note']['text']='节律不是钟表，\n而是生命对环境变化的响应。'
    # This page edits the selection rather than squeezing every candidate block.
    decision['blocks']=[b for b in decision['blocks'] if b['id']!='b-sample-001-about']
    blocks['b-sample-001-note'].update(text=job['sources']['sample-001/thought/s1-r2']['text'],source_refs=['sample-001/thought/s1-r2'])
    plan(cover,'看到精选书目以及本组内容的入口。','book-objects','四本示意书册与年度标题共同构图。','不把模拟书册厚度当作阅读量。')
    objects=''.join(f'<div class="book-object object-{i}">{tag("cover-book-b-"+b["book_id"],"spine-title")}<span class="object-line"></span><span data-label class="object-index">{i+1:02d}</span></div>' for i,b in enumerate(job['books']))
    cover_html=frame(cover,'cover',f'{tag("cover-year","year")}{tag("cover-title","cover-heading","h1")}<p data-label class="cover-deck">几段原话，几条笔记，几个值得展开的问题。</p><div class="objects">{objects}</div><div class="cover-bottom"><span data-label>书册为原创示意，非原版封面</span><p data-label>从一条具体记录开始，<br>看看这本书留下了什么。</p></div>','虚构材料的编排示例，非真实年度报告')

    overview['graphics']=[{'id':'monthly-track','kind':'monthly-trace','source_ref':'summary/monthly-records'}]
    add(overview,'monthly-basis','按月汇总已提供的时长记录',['summary/monthly-records'],'fact')
    rows=[]
    for i,book in enumerate(job['books']):
        bid=add(overview,f'overview-book-{i}',book['title'],[book['book_id']+'/title'],'fact')
        rows.append(f'<div class="shelf-row"><span data-label>{i+1:02d}</span>{tag(bid)}<span data-label>精选书目</span></div>')
    plan(overview,'看年度时长记录及本组精选书目，理解它们是不同统计范围。','record-trace','精确月度轨迹与精选索引交替展开。','没有日明细，不生成日历；精选不是全年书数。')
    overview_html=frame(overview,'overview',tag('overview-title','page-heading','h2')+f'<div class="stats"><div><span data-label>年度累计时长</span>{tag("overview-total-read-seconds","duration")}</div><div><span data-label>累计阅读天数</span>{tag("overview-read-days","days")}</div></div><div class="track">'+render_graphic(job,overview['id'],'monthly-track',792,340)+f'</div>{tag("monthly-basis","chart-basis")}<div class="shelf"><div class="shelf-heading" data-label>这组展开的四本书 / 精选索引</div>{"".join(rows)}</div>','统计采用虚构年度数据；精选书目单独列示')

    ref='sample-002/highlight/s2-h2'
    add(city,'city-excerpt',job['sources'][ref]['text'],[ref],'quote')
    plan(city,'一段关于街道的划线，与个人的日常观察放在一起读。','photo-observation','全景和细节并置，划线与笔记各有位置。','照片只作视觉联想，不冒充书中插图或用户拍摄。')
    city_html=frame(city,'city',tag('b-sample-002-title','page-heading','h2')+tag('b-sample-002-author','author')+f'<figure class="city-photo"><img src="assets/street.jpg" alt="公共领域街头摄影"><div class="crop"><img src="assets/street.jpg" alt="同一摄影的局部"></div></figure><p data-label class="photo-credit">Eugène Atget · 公共领域摄影 / 视觉联想</p><div class="city-notes"><div><span data-label class="section-label">留下一段原话</span>{tag("city-excerpt","excerpt","blockquote")}</div><div><span data-label class="section-label">样例中的一条笔记</span>{tag("b-sample-002-note","personal","blockquote")}</div></div>{tag("b-sample-002-about","bottom-about")}','照片全景与局部，让观察有具体对象')

    for bid,text,ref in [('write-hypothesis','写下你相信什么','sample-001/highlight/s1-h2'),
                         ('counter-evidence','寻找推翻它的证据','sample-001/highlight/s1-h2'),
                         ('counter-statement','保留一次反方陈述','sample-001/thought/s1-r2')]:
        add(decision,bid,text,[ref])
    ref='sample-001/highlight/s1-h2'
    add(decision,'decision-excerpt',job['sources'][ref]['text'],[ref],'quote')
    decision['graphics']=[{'id':'decision-path','kind':'relations','font_size':38,
        'nodes':[node('hypothesis','write-hypothesis',10,10,328,170),node('evidence','counter-evidence',430,130,344,180),node('statement','counter-statement',160,360,420,170)],
        'edges':[{'from':'hypothesis','to':'evidence','source_refs':[ref]},{'from':'evidence','to':'statement','source_refs':[ref,'sample-001/thought/s1-r2']}]}]
    plan(decision,'把一条划线和反方陈述笔记整理成可以读的检查路径。','decision-relations','错落的节点和连接形成主图，下方保留原文与笔记。','关系按精选片段整理；不用假分数或全书结论。')
    decision_html=frame(decision,'decision',tag('b-sample-001-title','page-heading','h2')+tag('b-sample-001-author','author')+f'<p data-label class="diagram-caption">按所选片段整理 / 箭头表示阅读顺序</p><div class="decision-graph">'+render_graphic(job,decision['id'],'decision-path',792,550)+f'</div><div class="decision-notes"><div><span data-label class="section-label">划线原文</span>{tag("decision-excerpt","excerpt","blockquote")}</div><div><span data-label class="section-label">样例个人笔记</span>{tag("b-sample-001-note","personal","blockquote")}</div></div>','关系图依据片段编辑，不代表量化因果')

    ref='sample-005/highlight/s5-h2'
    add(questions,'question-boundary','先问边界',[ref])
    add(questions,'question-answer','再问答案',[ref])
    add(questions,'question-excerpt',job['sources'][ref]['text'],[ref],'quote')
    ref2='sample-005/highlight/s5-h1'
    add(questions,'question-evidence',job['sources'][ref2]['text'],[ref2],'quote')
    questions['graphics']=[{'id':'question-pair','kind':'relations','font_size':42,
        'nodes':[node('boundary','question-boundary',10,14,332,172),node('answer','question-answer',450,136,332,172)],
        'edges':[{'from':'boundary','to':'answer','source_refs':[ref]}]}]
    plan(questions,'辨认先问边界、再问答案的次序，以及它与证据的关系。','question-pair','错开的两块问题牌，证据片段与个人提醒分区阅读。','不补写样例笔记中未给出的三个问题。')
    questions_html=frame(questions,'questions',tag('b-sample-005-title','page-heading','h2')+tag('b-sample-005-author','author')+f'<div class="question-graph">'+render_graphic(job,questions['id'],'question-pair',792,338)+f'</div><div class="question-excerpt"><span data-label class="section-label">原文的次序</span>{tag("question-excerpt","excerpt","blockquote")}</div><div class="question-lower"><div class="evidence-slip"><span data-label class="section-label">另一段划线</span>{tag("question-evidence","excerpt","blockquote")}</div><div><span data-label class="section-label">样例个人提醒</span>{tag("b-sample-005-note","personal","blockquote")}</div></div>{tag("b-sample-005-about","bottom-about")}','问题路径来自划线；个人提醒保留原话')

    add(plant,'plant-environment','光照\n季节\n环境变化',['sample-004/intro'])
    plan(plant,'用一条划线和书籍简介展示节律与环境的关系。','specimen-excerpt','原创植物意象与环境词旁注，长引文作为理解入口。','没有个人笔记，不补写读后感；植物意象非科学物种图。')
    # Original vector illustration. No quantities, observations or specimen claim.
    botanical='''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 560" width="480" height="560" aria-label="原创植物意象"><g fill="none" stroke="#d8dfb7" stroke-width="3"><path d="M244 548 C220 400 265 240 241 28"/><path d="M242 408 C143 410 76 369 54 297 C152 292 217 329 242 408 Z" fill="#63705c"/><path d="M241 319 C335 303 388 244 402 171 C305 188 257 234 241 319 Z" fill="#909b79"/><path d="M246 221 C168 213 121 165 113 107 C182 118 229 156 246 221 Z" fill="#aeb79c"/><path d="M243 132 C305 109 339 65 332 16 C281 39 254 83 243 132 Z" fill="#758369"/><path d="M58 300 L243 408 M402 171 L241 319 M115 110 L246 221 M332 17 L243 132" stroke-width="1"/></g></svg>'''
    plant_html=frame(plant,'plant',tag('b-sample-004-title','page-heading','h2')+tag('b-sample-004-author','author')+f'<div class="botanical">{botanical}</div><div class="plant-side"><p data-label>环境的线索</p><div class="specimen-line"></div>{tag("plant-environment")}</div><div class="plant-quote"><span data-label class="section-label">留下一段原话</span>{tag("b-sample-004-note","excerpt","blockquote")}</div>{tag("b-sample-004-about","plant-about")}','原创植物意象；没有虚构实测节律或阅读感受')
    write_json(output/'share-job.json',job)
    css=(Path(__file__).with_name('exhibition-demo.css')).read_text('utf-8')
    (output/'deck.html').write_text(f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>阅读展览 · 虚构样例</title><style>{css}</style></head><body>{cover_html}{overview_html}{city_html}{decision_html}{questions_html}{plant_html}</body></html>','utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    build(parser.parse_args().output)
    print('Fictional exhibition prepared; sample-test checkpoints still required.')
