"""Rebuild the public yearbook using fictional records and original mock covers."""
import io
import json
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from build_reading_html import adapt_data, build_html, merge_materials
from PIL import Image, ImageDraw, ImageFont


def main():
    out = ROOT / 'examples/reading-html-demo'
    covers_dir = out / 'covers'
    covers_dir.mkdir(parents=True, exist_ok=True)
    font_data = zlib.decompress((ROOT / 'assets/fonts/NotoSerifSC.ttf.zlib').read_bytes())
    def font(size):
        return ImageFont.truetype(io.BytesIO(font_data), size)
    titles = ['看见选择', '缓慢的城市', '工作中的尺度', '植物知道时间', '重新学习提问', '冬日短篇集']
    authors = ['林舟', '周野', '陈屿', '苏禾', '顾言', '许川']
    categories = ['社会科学', '文学', '商业', '自然科学', '教育', '文学']
    colors = ['#a9483e', '#365e71', '#64725a', '#95704c', '#58688a', '#84707f']
    seconds = [12960, 10080, 24600, 14400, 17280, 19440]
    excerpts = [
        '先把知道的事实写下来，再看看还有多少判断只是自己的猜测。',
        '',
        '尺度不是越大越好。先说明问题，再决定一次行动应该改变多大的范围。',
        '',
        '一个好问题，往往能让我们看清原来没有注意到的前提。',
        '有些话当时没说出口，后来就在一页书里认了出来。',
    ]
    thoughts = ['', '走路的时候先别急着拍照。试着记住一条街的声音，下次再来看看。',
                '开会前先写清楚这次要做的决定，比多准备几页材料管用。', '', '',
                '这段让我想起一个很久没联系的朋友。']
    books, covers = [], {}
    for i, title in enumerate(titles):
        book_id = f'demo-{i + 1:03d}'
        image = Image.new('RGB', (600, 900), '#eee7d8')
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, 0, 22, 900), fill=colors[i])
        draw.rectangle((55, 55, 545, 845), outline=colors[i], width=2)
        draw.text((85, 102), '阅读小册', font=font(23), fill=colors[i])
        draw.text((85, 185), '\n'.join(title[j:j+3] for j in range(0, len(title), 3)),
                  font=font(78), fill=colors[i], spacing=20)
        draw.text((88, 500), authors[i], font=font(30), fill=colors[i])
        if i % 2:
            draw.arc((125, 580, 475, 780), 10, 320, fill=colors[i], width=4)
            draw.line((120, 700, 470, 600), fill=colors[i], width=2)
        else:
            for j in range(5):
                draw.line((100, 620+j*22, 490-j*38, 600+j*22), fill=colors[i], width=3)
        draw.text((85, 793), '虚构书目 · 示意封面', font=font(23), fill=colors[i])
        target = covers_dir / (book_id + '.png')
        image.save(target)
        covers[book_id] = target
        date = f'2026-{i + 2:02d}-15'
        books.append({'book_id': book_id, 'title': title, 'author': authors[i],
                      'category': categories[i], 'progress': [100, 100, 68, 100, 42, 100][i],
                      'is_started': True, 'annual_reading_seconds': seconds[i],
                      'selected': i < 4, 'finish_time': date if i in (0, 1, 3, 5) else None,
                      'intro': f'这是一份关于{categories[i]}的虚构示例简介，用于检查书籍资料的展示。',
                      'highlights': [{'text': excerpts[i], 'created_at': date, 'source_id': f'h{i}'}] if excerpts[i] else [],
                      'thoughts': [{'text': thoughts[i], 'created_at': date, 'source_id': f'n{i}'}] if thoughts[i] else []})
    raw = {'year': 2026, 'as_of': '2026-10-01', 'source_mode': 'sample',
           'verification_status': 'sample_verified', 'books': books,
           'summary': {'book_count': len(books), 'finished_count': 4, 'read_days': 108,
                       'note_count': sum(len(b['highlights']) + len(b['thoughts']) for b in books),
                       'total_read_seconds': sum(seconds),
                       'monthly_read_seconds': [9000, 12600, 14400, 10800, 16200, 10800, 8640, 11340, 4980]}}
    (out / 'demo-data.json').write_text(json.dumps(raw, ensure_ascii=False, indent=2)+'\n', 'utf-8')
    data = adapt_data(raw)
    merge_materials(data, {'year': 2026, 'books': [{**b, 'notes_scope': 'all_time',
                     'collection': {'highlights': 'complete', 'thoughts': 'complete'}} for b in books]})
    result = build_html(data, out / 'index.html', covers, require_all_covers=True)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
