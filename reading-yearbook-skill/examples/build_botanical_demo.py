"""A second, content-specific art example. Not a template used by the sharing CLI."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
from run_share import file_digest, load_job, prepare_share, write_json
from workflow_fixture import sample_decisions

LEAF = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 620 850">
<g fill="#702936">
<path d="M304 799C250 689 320 614 304 471C274 299 372 174 424 43C501 222 539 344 434 456C374 520 347 624 304 799Z"/>
<path d="M297 615C153 585 77 473 51 278C228 298 304 414 297 615Z"/>
<path d="M322 724C376 590 487 543 594 547C575 676 480 749 322 724Z"/>
</g>
<g fill="none" stroke="#edc5ab" stroke-width="2.5">
<path d="M302 821C325 641 333 359 424 58M308 603C234 503 169 399 69 301M317 719C410 672 482 616 574 562"/>
<path d="M352 439L439 362M369 346L462 278M390 257L463 199M242 505L139 455M197 436L119 382M407 670L495 686M464 632L538 645"/>
</g></svg>'''

HTML = '''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>植物知道时间 · 分享样例</title>
<style>
*{box-sizing:border-box}body{margin:0;padding:24px;background:#d6cbc5;color:#702936}
.page{width:900px;height:1200px;position:relative;overflow:hidden;margin:0 auto 24px;background:#edc5ab}
h1,h2,p,blockquote{margin:0}header,footer{position:absolute;left:52px;right:52px;display:flex;justify-content:space-between;font:23px/1.5 'Microsoft YaHei',sans-serif}
header{top:42px}footer{bottom:38px;font-size:21px} .serif{font-family:'SimSun',serif;font-weight:400}
.cover .plant{position:absolute;width:490px;height:672px;left:430px;top:400px;transform:rotate(8deg)}
.cover h1{position:absolute;left:52px;top:164px;font-size:124px;line-height:1.3;letter-spacing:4px}
.cover h1 span{display:block;margin-top:90px;margin-left:44px}
.cover .lead{position:absolute;left:54px;top:938px;width:540px;font:34px/1.6 'Microsoft YaHei',sans-serif}
.inside{background:#702936;color:#edc5ab}
.inside h2{position:absolute;left:52px;top:135px;font-size:53px;line-height:1.4}
.inside .author{position:absolute;left:57px;top:224px;font:25px/1.5 'Microsoft YaHei',sans-serif}
.inside .plant{position:absolute;left:418px;top:245px;width:355px;height:488px;transform:rotate(-19deg);filter:brightness(0) saturate(100%) invert(88%) sepia(22%) saturate(526%) hue-rotate(321deg) brightness(93%)}
.inside .about{position:absolute;left:55px;top:389px;width:343px;font:34px/1.8 'Microsoft YaHei',sans-serif}
.inside .quote{position:absolute;left:54px;top:765px;width:790px;font-size:53px;line-height:1.55;letter-spacing:1px}
.inside .note{position:absolute;left:55px;top:1055px;font:23px/1.5 'Microsoft YaHei',sans-serif}
</style></head><body>
<article class="page cover" id="cover">
<header><span data-label>年年阅 · 单书</span><span data-status>样例 · 虚构书目与划线</span></header>
<img class="plant" src="assets/plant-shape.svg" alt="原创植物形态示意">
<h1 class="serif" data-block="cover-book-b-sample-004">植物<span>知道时间</span></h1>
<p class="lead" data-block="cover-title">这次聊一本<br>关于植物的书。</p>
<footer><span data-label>配图：原创植物形态示意</span><span data-block="cover-year">2026</span></footer>
</article>
<article class="page inside" id="book-b-sample-004">
<header><span data-label>年年阅 / 01</span><span data-status>样例 · 虚构书目与划线</span></header>
<h2 class="serif" data-block="b-sample-004-title">植物知道时间</h2>
<p class="author" data-block="b-sample-004-author">苏禾</p>
<img class="plant" src="assets/plant-shape.svg" alt="原创植物形态示意">
<p class="about" data-block="b-sample-004-about">通过植物节律解释生命如何感知光照、季节与环境变化。</p>
<blockquote class="quote serif" data-block="b-sample-004-note">节律不是钟表，<br>而是生命对<br>环境变化的响应。</blockquote>
<p class="note" data-label>一条划线</p>
<footer><span data-label>书目与划线来自仓库样例</span><span data-label>01 / 植物知道时间</span></footer>
</article></body></html>'''


def build(output: Path) -> None:
    prepare_share(2026, SKILL / "assets/sample-data.json", output, ["sample-004"], "single-book")
    job = load_job(output)
    sample_decisions(job, focus="excerpts")
    job["art_brief"] = {
        "focus": "植物如何感知光照与季节；只用简介和划线，没有个人感受就不补写",
        "visual": "原创植物形态作为大面积剪影；浅杏与暗红互换，宋体顺着枝叶的方向排列",
        "sequence": "一本书的封面与一条划线；不沿用城市书单的照片、蓝色或数字构图",
        "audience": "小红书读者",
    }
    job["pages"][0]["blocks"][0]["text"] = "这次聊一本关于植物的书。"
    job["caption"] = "这次聊《植物知道时间》。关于光照、季节，还有植物怎么感知环境变化。\n\n样例：虚构书目与划线，仅作设计演示。"
    assets = output / "assets"
    assets.mkdir()
    asset = assets / "plant-shape.svg"
    asset.write_text(LEAF, "utf-8")
    job["assets"] = [{"path": "assets/plant-shape.svg", "sha256": file_digest(asset),
                      "source": "original: examples/build_botanical_demo.py", "rights": "original geometric SVG; repository license",
                      "role": "decorative plant shape; not a botanical specimen or book illustration"}]
    write_json(output / "share-job.json", job)
    with (output / "deck.html").open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(HTML)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=SKILL / "output/botanical-demo")
    build(parser.parse_args().output)
    print("Example prepared; use sample-test confirmations with run_share.py.")
