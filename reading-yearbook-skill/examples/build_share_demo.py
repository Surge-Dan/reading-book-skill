"""Rebuild the documented example only. This is not the default art direction or user workflow."""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
from run_share import file_digest, load_job, prepare_share, write_json

EXTRA_CSS = """
    .cover h1 {position:absolute;left:50px;top:117px;width:600px;height:370px}
    .cover .title-one {left:0;top:0}.cover .title-two {left:0;top:125px}.cover .title-three {left:49px;top:250px}
    .booklist [data-block]::before {content:'《'}.booklist [data-block]::after {content:'》'}
    .decision {background:var(--blue);color:var(--paper)}
    .decision .sample,.decision .footer {color:var(--paper)}
    .decision h2,.questions h2 {position:absolute;left:54px;top:136px;font-size:68px;font-weight:750;line-height:1.3;letter-spacing:-2px}
    .decision .author,.questions .author {position:absolute;left:56px;top:242px;font-size:27px}
    .decision .thought {position:absolute;left:54px;top:418px;width:792px;font-size:62px;line-height:1.6;font-family:'Noto Serif SC','SimSun',serif}
    .decision .thought .large {display:block;margin-left:174px;font-size:108px;line-height:1.55}
    .decision .about-label {position:absolute;left:54px;top:975px;font-size:27px;line-height:1.65}
    .decision .about {position:absolute;left:230px;top:970px;width:614px;font-size:34px;line-height:1.65}
    .questions h2 {font-size:60px;color:var(--blue)}
    .questions .punctuation {position:absolute;left:468px;top:290px;font-family:'Times New Roman',serif;font-size:370px;line-height:1;color:var(--blue)}
    .questions .quote {position:absolute;left:54px;top:443px;font-size:64px;line-height:1.6;font-weight:700;color:var(--blue)}
    .questions .about {position:absolute;left:54px;top:724px;width:792px;font-size:32px;line-height:1.65}
    .questions .note-label {position:absolute;left:54px;top:909px;font-size:27px;line-height:1.65;color:var(--blue)}
    .questions .personal {position:absolute;left:232px;top:900px;width:614px;font-size:34px;line-height:1.7}
"""

EXTRA_PAGES = """
  <article class="page decision" id="book-b-sample-001">
    <header class="top"><span data-label>年年阅 / 02</span><span class="sample" data-status>样例 · 虚构书目与笔记</span></header>
    <h2 data-block="b-sample-001-title">看见选择</h2>
    <p class="author" data-block="b-sample-001-author">林舟</p>
    <blockquote class="thought" data-block="b-sample-001-note">以后做重要决定时，<br>先保留一次<span class="large">反方陈述。</span></blockquote>
    <p class="about-label" data-label>书里写什么</p>
    <p class="about" data-block="b-sample-001-about">从日常选择出发，聊事实、假设和判断之间的距离。</p>
    <footer class="footer"><span data-label>书目与笔记来自仓库样例</span><span data-label>02 / 看见选择</span></footer>
  </article>
  <article class="page questions" id="book-b-sample-005">
    <header class="top"><span data-label>年年阅 / 03</span><span class="sample" data-status>样例 · 虚构书目与笔记</span></header>
    <h2 data-block="b-sample-005-title">重新学习提问</h2>
    <p class="author" data-block="b-sample-005-author">顾言</p>
    <span class="punctuation" aria-hidden="true">?</span>
    <blockquote class="quote" data-block="b-sample-005-quote">先问边界，<br>再问答案。</blockquote>
    <p class="about" data-block="b-sample-005-about">写提问，也写怎么澄清边界、寻找证据。</p>
    <p class="note-label" data-label>一条笔记</p>
    <blockquote class="personal" data-block="b-sample-005-note">我想把需求讨论里的抽象争论<br>改成三个具体问题。</blockquote>
    <footer class="footer"><span data-label>书目与笔记来自仓库样例</span><span data-label>03 / 重新学习提问</span></footer>
  </article>
"""


def build(output: Path) -> None:
    prepare_share(2026, SKILL / "assets/sample-data.json", output, ["sample-002", "sample-001", "sample-005"])
    job = load_job(output)
    job["art_brief"] = {"audience": "小红书陌生读者", "focus": "精选书单与原始笔记，城市观察是这次的图像入口", "visual": "照片全景与局部；蓝色文字与黑白照片相处；讨论选择时换成文字主导", "sequence": "封面、街道观察、反方陈述、提问", "omit": "不加年度总量、年轮、装饰纹理；不是其他书单的固定风格"}
    blocks = {block["id"]: block for page in job["pages"] for block in page["blocks"]}
    blocks["cover-title"]["text"] = "今年的书，挑几本聊聊。"
    blocks["b-sample-002-about"]["text"] = "写的是步行和街区，以及人在城市里怎么生活。"
    blocks["b-sample-001-about"]["text"] = "从日常选择出发，聊事实、假设和判断之间的距离。"
    blocks["b-sample-001-note"].update(text=job["sources"]["sample-001/thought/s1-r2"]["text"], source_refs=["sample-001/thought/s1-r2"])
    blocks["b-sample-005-about"]["text"] = "写提问，也写怎么澄清边界、寻找证据。"
    job["pages"][-1]["blocks"].append({"id": "b-sample-005-quote", "kind": "quote", "text": job["sources"]["sample-005/highlight/s5-h2"]["text"], "source_refs": ["sample-005/highlight/s5-h2"]})
    assets = output / "assets"
    assets.mkdir(parents=True)
    shutil.copy2(SKILL / "examples/visual-proof-v2/assets/atget-organ-player.jpg", assets / "atget-organ-player.jpg")
    job["assets"] = [{"path": "assets/atget-organ-player.jpg", "source": "https://www.artic.edu/artworks/55394", "rights": "public-domain; museum API is_public_domain=true", "sha256": file_digest(assets / "atget-organ-player.jpg"), "role": "visual illustration, not a book cover or illustration"}]
    write_json(output / "share-job.json", job)
    html = (SKILL / "examples/visual-proof-v2/deck.html").read_text("utf-8")
    html = html.replace('id="01-cover"', 'id="cover"').replace('id="02-city"', 'id="book-b-sample-002"')
    html = html.replace('data-ink', 'data-label').replace('class="sample" data-label', 'class="sample" data-status')
    html = html.replace('<h1 aria-label=', '<h1 data-block="cover-title" aria-label=')
    html = html.replace('class="year" aria-label="2026" data-label', 'class="year" aria-label="2026" data-block="cover-year"')
    html = html.replace('<p class="booklist" data-label>《缓慢的城市》　《看见选择》<span class="more">《重新学习提问》</span></p>', '<p class="booklist"><span data-block="cover-book-b-sample-002">缓慢的城市</span>　<span data-block="cover-book-b-sample-001">看见选择</span><span class="more"><span data-block="cover-book-b-sample-005">重新学习提问</span></span></p>')
    html = html.replace('<h2 data-label>', '<h2 data-block="b-sample-002-title">')
    html = html.replace('<p class="author" data-label>周野 · 随笔</p>', '<p class="author" data-label><span data-block="b-sample-002-author">周野</span> · 随笔</p>')
    html = html.replace('cite="../../assets/sample-data.json" data-label', 'data-block="b-sample-002-note"')
    html = html.replace('<p class="about" data-label>', '<p class="about" data-block="b-sample-002-about">')
    html = html.replace('</style>', EXTRA_CSS + '\n  </style>').replace('</body>', EXTRA_PAGES + '\n</body>')
    html = "\n".join(line.rstrip() for line in html.splitlines()) + "\n"
    (output / "deck.html").write_text(html, "utf-8", newline="\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=SKILL / "output/share-demo")
    args = parser.parse_args()
    build(args.output)
    print("Example prepared; record sample-test confirmations and render with run_share.py.")
