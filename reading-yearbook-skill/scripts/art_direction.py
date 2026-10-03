"""Material-led planning packets and artwork contracts, never a book-title classifier."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

WORKFLOW = 'material-led'


def design_packet(job: dict) -> dict:
    """Bound the material a designer needs. Proposals are not chosen styles or approval."""
    pages = []
    for page in job['pages']:
        evidence = [b for b in page['blocks'] if b['kind'] in ('quote', 'thought', 'user_input', 'editorial')]
        excerpts = [{'id': b['id'], 'kind': b['kind'], 'text': b['text'][:280],
                     'excerpt_only': len(b['text']) > 280,
                     'source_refs': b.get('source_refs', [])} for b in evidence[:4]]
        data = any(g['kind'] in ('monthly-trace', 'calendar') for g in page.get('graphics', []))
        relations = any(g['kind'] == 'relations' for g in page.get('graphics', []))
        personal = any(b['kind'] in ('thought', 'user_input') for b in evidence)
        moves = ['先用本页材料写一个主意象与阅读路径；书名、分类不决定风格。',
                 '字样／原创物件可在没有合适照片时成立；找到有使用依据的照片才考虑摄影拼贴。']
        if data:
            moves.append('数据绘图维持比例和单位，材质只作用于承载纸面，不能扭曲坐标。')
        if relations:
            moves.append('关系结构可以成为版面骨架；物件前后与连接须表达已有证据，不加权重。')
        if personal:
            moves.append('可让原话与印刷文字形成不同声音；手写字体不是用户真实笔迹。')
        pages.append({'id': page['id'], 'reading_task': page.get('storyboard', {}).get('reading_task'),
                      'book_ids': page['book_ids'], 'selected_material': excerpts,
                      'design_moves': moves,
                      'needs_editorial_decision': ['主意象及其材料依据', '为什么这种图文关系适合这一页',
                                                  '实际主素材与字体', '阅读顺序与文字保护区']})
    return {'version': 'design-packet-1', 'status': 'proposal_only', 'canvas': job.get('canvas'),
            'brief': job.get('brief'), 'books': job['books'], 'pages': pages,
            'assets': [{k: a[k] for k in ('path', 'source', 'rights', 'role') if k in a} for a in job.get('assets', [])],
            'rules': ['不读取整本书，不按书名或类型套版。', '先提两个具体方向，确认后做一套实际样张。',
                      '截短的材料只用于设计选材，不能替代完整引文。', '无素材不假装已有素材，无观点不假装个人所得。']}


def nonempty(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_artwork(job: dict) -> None:
    """Opt-in contract keeps existing share-3 archives usable without inventing history."""
    required = job.get('art_brief', {}).get('workflow') == WORKFLOW
    assets = {a['path'] for a in job.get('assets', [])}
    for page in job['pages']:
        plan = page.get('artwork')
        if plan is None and not required:
            continue
        if not isinstance(plan, dict) or any(not nonempty(plan.get(k)) for k in ('concept', 'rationale', 'voice')):
            raise ValueError(f"{page['id']}需要材料驱动的主意象、适配理由和视觉语言。")
        refs = plan.get('basis_refs')
        available = {r for b in page['blocks'] for r in b.get('source_refs', [])}
        available.update(page.get('storyboard', {}).get('evidence_refs', []))
        if not isinstance(refs, list) or not refs or any(not nonempty(r) or r not in available or r not in job['sources'] for r in refs):
            raise ValueError(f"{page['id']}主意象必须绑定本页材料证据。")
        ids = {b['id'] for b in page['blocks']}
        order = plan.get('reading_path')
        if not isinstance(order, list) or not order or any(not nonempty(b) for b in order) or len(set(order)) != len(order) or any(b not in ids for b in order):
            raise ValueError(f"{page['id']}阅读路径须指向本页唯一内容块。")
        primary = plan.get('primary', {})
        if not isinstance(primary, dict) or any(not nonempty(primary.get(k)) for k in ('medium', 'description')):
            raise ValueError(f"{page['id']}需要具体主素材或原创物件，不只是风格名称。")
        if primary.get('origin') not in ('original', 'registered-assets', 'typography', 'evidence-graphic'):
            raise ValueError(f"{page['id']}主素材来源未明确。")
        paths = primary.get('asset_paths', [])
        if not isinstance(paths, list) or any(not nonempty(p) or p not in assets for p in paths) or (primary['origin'] == 'registered-assets' and not paths):
            raise ValueError(f"{page['id']}主素材尚未登记，不能用参考图充当成品素材。")
        layers = plan.get('layers')
        if not isinstance(layers, list) or not layers:
            raise ValueError(f"{page['id']}需要有语义的图层计划。")
        seen, covered = set(), set()
        for layer in layers:
            if not isinstance(layer, dict):
                raise ValueError('图层须为对象。')
            lid = layer.get('id')
            if not nonempty(lid) or lid in seen or layer.get('role') not in ('text', 'material', 'decoration', 'data') or not nonempty(layer.get('purpose')):
                raise ValueError(f"{page['id']}图层须唯一并说明实际作用。")
            seen.add(lid)
            bound = layer.get('block_ids', [])
            if not isinstance(bound, list) or any(not nonempty(b) or b not in ids for b in bound):
                raise ValueError(f"{page['id']}图层文字须绑定本页内容。")
            covered.update(bound)
            paths = layer.get('asset_paths', [])
            if not isinstance(paths, list) or any(not nonempty(p) or p not in assets for p in paths):
                raise ValueError(f"{page['id']}图层素材未登记。")
            if layer.get('allow_bleed'):
                if layer['role'] not in ('material', 'decoration') or bound or not nonempty(layer.get('bleed_reason')):
                    raise ValueError('出血仅用于有理由的无文字素材，不允许数据或核心文字借此越界。')
        if not set(order).issubset(covered):
            raise ValueError(f"{page['id']}主要阅读内容缺少图层绑定。")
        fonts = plan.get('fonts')
        if not isinstance(fonts, list) or not fonts:
            raise ValueError(f"{page['id']}需要实际字体职责及使用依据。")
        assigned = set()
        for font in fonts:
            if not isinstance(font, dict):
                raise ValueError('字体计划须为对象。')
            if any(not nonempty(font.get(k)) for k in ('family', 'role', 'use_basis')):
                raise ValueError('字体需要实际名称、职责和使用依据。')
            bound = font.get('block_ids')
            if not isinstance(bound, list) or not bound or any(not nonempty(b) or b not in ids or b in assigned for b in bound):
                raise ValueError('字体校验需要明确且不重复的内容块。')
            assigned.update(bound)
            if not isinstance(font.get('fallbacks', []), list) or any(not nonempty(f) for f in font.get('fallbacks', [])):
                raise ValueError('备用字体须列出实际名称，不能静默回退。')
        if not set(order).issubset(assigned):
            raise ValueError('主标题与阅读路径的文字须有实际字体校验。')


def main() -> None:
    parser = argparse.ArgumentParser(description='整理已有精选证据用于艺术指导，不自动选择或确认风格。')
    parser.add_argument('--job', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() == args.job.resolve():
        parser.error('材料包输出不能覆盖share-job.json。')
    job = json.loads(args.job.read_text('utf-8'))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(design_packet(job), ensure_ascii=False, indent=2) + '\n', 'utf-8')
    print(json.dumps({'status': 'proposal_only', 'pages': len(job['pages']), 'output': str(args.output)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
