"""Shared evidence-bound reading layer; never generates facts in rendering code."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'reading-2-context'


def writing_rules():
    return (ROOT / 'references/book-reading-writing.md').read_text('utf-8')


class ReadingValidationError(ValueError):
    pass


class ReviewStageFailure(ValueError):
    """Sanitized provider failure, distinct from cancellation or orchestration errors."""


def generate_stage(runner, stage, prompt, **kwargs):
    try:
        return runner.generate(prompt, **kwargs)
    except InterruptedError:
        raise
    except (ValueError, TimeoutError, RuntimeError, OSError):
        if stage != 'reading-review': raise
        # Lease/ownership errors are not optional writing failures.
        if runner.info().get('mode') == 'current-agent-instructed-tools': raise
        raise ReviewStageFailure('书评服务暂未返回有效内容；已保留其他解读，请检查连接后重试书评。') from None


def _fail(message):
    raise ReadingValidationError(message)


def _sources(sources, elements, allowed=None):
    if not isinstance(sources, list) or not sources:
        _fail('阅读内容缺少实际来源')
    index = {e['element_id']: e for e in elements}
    for source in sources:
        if not isinstance(source, dict) or not all(isinstance(source.get(k), str) and source[k] for k in ('element_id', 'quote', 'location')):
            _fail('阅读来源字段无效')
        eid, quote = source['element_id'], source['quote']
        if eid not in index or (allowed is not None and eid not in allowed) or quote not in index[eid]['text']:
            _fail('阅读引文未匹配有效材料')
        if len(quote) > 150 if re.search(r'[\u3400-\u9fff]', quote) else len(quote.split()) > 100:
            _fail('阅读引文过长')
        source['location'] = index[eid]['location']
        for key in ('url', 'source_type'):
            if key in index[eid]: source[key] = index[eid][key]


def validate_map(rows, elements):
    if not isinstance(rows, list) or not rows:
        _fail('缺少实际内容地图，无法检查关键内容')
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('id'), str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', row['id']) or row['id'] in seen:
            _fail('内容地图身份无效或重复')
        seen.add(row['id'])
        if not isinstance(row.get('title'), str) or not row['title'].strip() or row.get('importance') not in ('core', 'supporting') or row.get('status') not in ('read', 'missing') or not isinstance(row.get('gap'), str):
            _fail('内容地图字段无效')
        if row['status'] == 'read': _sources(row.get('sources'), elements)
        elif not row['gap'].strip() or row.get('sources') != []: _fail('未取得项目必须写明缺口，不伪造证据')
    return rows


def validate_context(analysis, elements):
    rows = analysis.get('book_context', [])
    if not isinstance(rows, list): _fail('书籍理解层格式无效')
    for row in rows:
        if not isinstance(row, dict) or row.get('kind') not in ('characters', 'logic', 'intent'):
            _fail('书籍理解层类型无效')
        if not all(isinstance(row.get(k), str) and row[k].strip() for k in ('title', 'explanation')):
            _fail('书籍理解层正文为空')
        _sources(row.get('sources'), elements)
        row['source_verified'] = True
    return rows


def validate_coverage(analysis, topics):
    rows = analysis.get('topic_coverage')
    if not isinstance(rows, list) or len(rows) != len(topics): _fail('关键内容去向不完整')
    index = {t['id']: t for t in topics}; seen = set()
    for row in rows:
        if not isinstance(row, dict) or row.get('topic_id') not in index or row['topic_id'] in seen or row.get('status') not in ('explained', 'missing') or not isinstance(row.get('reason'), str) or not row['reason'].strip() or not isinstance(row.get('item_refs'), list):
            _fail('关键内容去向字段无效')
        seen.add(row['topic_id']); topic = index[row['topic_id']]
        if row['status'] == 'missing':
            if row['item_refs']: _fail('未解释内容不能标记已交付位置')
            continue
        if topic['status'] != 'read' or not row['item_refs']: _fail('未读到内容不能声称已解释')
        bound = {s['element_id'] for s in topic['sources']}
        for ref in row['item_refs']:
            match = re.fullmatch(r'(book_context|themes|methods|cases|counterexamples|glossary):(\d+)', ref) if isinstance(ref, str) else None
            if not match: _fail('无效内容去向')
            items = analysis.get(match[1], []); n = int(match[2])
            if n >= len(items) or not bound.intersection(s['element_id'] for s in items[n]['sources']): _fail('内容去向与实际证据不匹配')
    return rows


def reading_status(analysis, topics, mode, bibliography):
    missing = any(t['importance'] == 'core' and t['status'] == 'missing' for t in topics) or any(r['status'] == 'missing' for r in analysis.get('topic_coverage', []))
    if mode == 'upload':
        level, label = ('partial', '正文部分解读') if missing else ('provided_text', '基于所提供正文的解读')
    elif missing: level, label = 'partial', '公开资料部分解读'
    elif not any(s.get('content_kind') in ('discussion','excerpt') for s in bibliography): level, label = 'introduction', '公开资料简介'
    else: level, label = 'public_reading', '公开资料解读'
    gaps=[t['title'] for t in topics if t['status']=='missing']
    gaps += [next(t['title'] for t in topics if t['id']==r['topic_id']) for r in analysis.get('topic_coverage',[]) if r['status']=='missing']
    reason = ('尚缺关键内容：'+'、'.join(dict.fromkeys(gaps))) if gaps else '已整理本次实际取得的材料，不代表整书覆盖或方法效用验证。'
    if level=='introduction': reason='目前材料主要为简介或目录，尚不足以展开主要论证。'
    return {'level': level, 'label': label, 'reason': reason}


def validate_review(value, elements, allowed):
    if not isinstance(value, dict) or value.get('status') not in ('ready', 'unavailable') or not isinstance(value.get('reason'), str) or not isinstance(value.get('paragraphs'), list): _fail('书评格式无效')
    if value['status'] == 'unavailable':
        if value['paragraphs'] or not value['reason'].strip(): _fail('书评缺失必须说明原因')
        return value
    if not value['paragraphs']: _fail('书评正文为空')
    for paragraph in value['paragraphs']:
        if not isinstance(paragraph, dict) or not isinstance(paragraph.get('text'), str) or not paragraph['text'].strip() or not isinstance(paragraph.get('quotes'), list): _fail('书评段落格式无效')
        _sources(paragraph.get('sources'), elements, allowed)
        quotes = paragraph['quotes']
        if quotes: _sources(quotes, elements, allowed)
        for q in quotes:
            if q['quote'] not in paragraph['text'] or q['element_id'] not in {s['element_id'] for s in paragraph['sources']}: _fail('书评引文未实际出现或缺少段落依据')
        marked = re.findall(r'“([^”]+)”|「([^」]+)」|"([^"\n]+)"', paragraph['text'])
        for group in marked:
            fragment = next(x for x in group if x)
            if not any(fragment in q['quote'] for q in quotes): _fail('书评引号中的文字没有原文核对记录')
    return value


def add_review(analysis, document, call, mode, focus):
    """One bounded stage; writing failures are visible, cancellation still stops work."""
    items = [item for key in ('book_context','themes','methods','cases','counterexamples','glossary','insights') for item in analysis.get(key, []) if item.get('source_verified', True)]
    allowed = {s['element_id'] for item in items for s in item.get('sources', [])}
    evidence = [e for e in document['elements'] if e['element_id'] in allowed]
    rules = writing_rules() + '\n\n' + (ROOT / 'references/book-review-writing.md').read_text('utf-8')
    payload = {'book':analysis['book'], 'input_mode':mode, 'focus':focus,
               'overview':analysis['overview'], 'book_context':analysis.get('book_context', []), 'content':items, 'elements':evidence}
    try:
        review = call('reading-review', rules, payload, validate=lambda value: validate_review(value,evidence,allowed))
        analysis['review'] = review
    except (ReadingValidationError, ReviewStageFailure) as error:
        analysis['review'] = {'status':'unavailable','reason':str(error),'paragraphs':[]}
    if analysis['review']['status']=='unavailable':
        analysis['quality_status']='needs_review'
    return analysis
