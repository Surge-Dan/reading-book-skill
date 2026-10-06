"""Use OFL bundled fonts; subset actual document characters when tools exist."""
import base64
import io
import json
import sys
import zlib
from functools import lru_cache
from pathlib import Path
from threading import Lock
from unittest.mock import patch

FONT_LOCK=Lock()

ROOT=Path(__file__).resolve().parents[1]
vendor=ROOT/'.vendor'
if vendor.exists():sys.path.insert(0,str(vendor))


@lru_cache(maxsize=32)
def font_bytes(name,characters):
    source=ROOT/'assets/fonts'/name
    raw=zlib.decompress(source.read_bytes())
    try:
        from fontTools import subset
        from fontTools.ttLib import TTFont
    except ImportError:
        return raw
    font=TTFont(io.BytesIO(raw),lazy=True)
    options=subset.Options();options.flavor='woff2';options.recalc_timestamp=False
    sub=subset.Subsetter(options=options);sub.populate(text=characters);sub.subset(font)
    # WOFF2 defaults to Brotli quality 11. Quality 5 retains identical glyphs
    # while avoiding expensive recompression for every user's document.
    from fontTools.ttLib import woff2
    output=io.BytesIO();font.flavor='woff2'
    with FONT_LOCK:
        compressor=woff2.brotli.compress
        def fast_compress(content,**kwargs):
            kwargs['quality']=5
            return compressor(content,**kwargs)
        with patch.object(woff2.brotli,'compress',fast_compress):font.save(output)
    font.close();return output.getvalue()


def font_css(data):
    sources=[json.dumps(data,ensure_ascii=False)]
    for name in ('reading-template.html','reading-app.js','reading-share-art.js'):
        sources.append((ROOT/'assets'/name).read_text('utf-8'))
    characters=''.join(sorted(set(''.join(sources))))
    # Numeric readouts, CJK punctuation and any dynamic prose used by controls.
    characters+='0123456789年月日小时分钟本条已选在读未开始状态记录暂停继续取消导出成功失败进行中，。！？：；、（）《》「」“”…—↑→✓'
    css=[]
    for family,name in [('ReadingSerif','NotoSerifSC.ttf.zlib'),('ReadingSans','NotoSansSC.ttf.zlib')]:
        binary=font_bytes(name,characters);flavor='woff2' if binary[:4]==b'wOF2' else 'truetype'
        mime='font/woff2' if flavor=='woff2' else 'font/ttf'
        encoded=base64.b64encode(binary).decode('ascii')
        css.append(f'@font-face{{font-family:{family};src:url(data:{mime};base64,{encoded}) format("{flavor}");font-weight:100 900;font-display:block}}')
    return '\n'.join(css)
