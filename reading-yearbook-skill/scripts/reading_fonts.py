"""Embed a redistributable font; optionally subset it without network access."""
import base64
import io
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def content_characters(data):
    # Capture static labels and dynamic text, not image payloads or credentials.
    parts = []
    def visit(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key != 'cover':
                    visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
        elif isinstance(value, str) and not value.startswith('data:'):
            parts.append(value)
    visit(data)
    for name in ('reading-template.html', 'reading-app.js', 'reading-share-art.js'):
        parts.append((ROOT / 'assets' / name).read_text('utf-8'))
    return ''.join(sorted(set(''.join(parts)) | {chr(i) for i in range(32, 127)}))


@lru_cache(maxsize=8)
def embedded_font(characters):
    source = ROOT / 'assets' / 'fonts' / 'NotoSansSC-VF.ttf'
    try:
        from fontTools import subset
        from fontTools.ttLib import TTFont
    except ImportError:
        # The complete bundled font is a safe, larger offline fallback.
        return source.read_bytes(), 'full'
    font = TTFont(source, recalcTimestamp=False)
    options = subset.Options()
    options.layout_features = ['*']
    worker = subset.Subsetter(options=options)
    worker.populate(text=characters)
    worker.subset(font)
    buffer = io.BytesIO()
    font.save(buffer)
    font.close()
    return buffer.getvalue(), 'subset'


def font_css(data):
    content, mode = embedded_font(content_characters(data))
    encoded = base64.b64encode(content).decode('ascii')
    css = '@font-face{font-family:ReadingSans;src:url(data:font/ttf;base64,' + encoded + ') format("truetype");font-style:normal;font-weight:100 900;font-display:block;}'
    return css, {'mode': mode, 'bytes': len(content), 'family': 'ReadingSans'}
