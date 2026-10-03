"""Technical fixtures for the three checkpoints and canvas sizes, not a design template."""
from __future__ import annotations

import argparse
from html import escape
from pathlib import Path
import sys

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
from run_share import prepare_share, write_json
from share_contract import make_canvas


def sample_decisions(job: dict, ratio: str = "3:4", focus: str = "reading-takeaways") -> None:
    """Populate explicit fixture decisions, never user approval or real references."""
    if job["source_mode"] != "sample":
        raise ValueError("技术夹具只能使用样例。")
    # Legacy technical fixtures exercise the original share-3 archive contract.
    # Material-led examples declare artwork separately; never migrate real jobs.
    job["art_brief"].pop("workflow", None)
    job["canvas"] = make_canvas(ratio)
    job["brief"].update(platform="本地技术样例", focus=focus)
    job["directions"] = [
        {"id": "a", "label": "文字主导（技术样例）", "concept": "标题、原始想法、辅助书目按层级排列。",
         "fonts": [{"family": "Microsoft YaHei", "role": "正文"}],
         "references": [{"source": "repository:examples/share-demo/deck.html", "lesson": "参考已有样例的文字层级；仅为夹具输入。"}]},
        {"id": "b", "label": "图像主导（技术样例）", "concept": "书封或图像占主面积，文字在侧边集中。",
         "fonts": [{"family": "SimSun", "role": "标题"}],
         "references": [{"source": "repository:examples/botanical-demo/deck.html", "lesson": "参考已有样例的图文主次；仅为夹具输入。"}]},
    ]
    job["selected_direction"] = "a"
    for page in job['pages']:
        page['storyboard'] = {"reading_task": "技术测试：检查当前页面文字与导出一致。",
                              "evidence_refs": list(dict.fromkeys(ref for b in page['blocks'] for ref in b.get('source_refs', []))) or ['period/year'],
                              "main_visual": {"structure": "text-fixture", "description": "固定测试排版，仅用于测量尺寸与确认失效。"},
                              "supporting_blocks": [b['id'] for b in page['blocks']], "omit": "不模拟真实用户偏好或艺术判断。"}


def build(output: Path, ratio: str = "3:4") -> None:
    job = prepare_share(2026, SKILL / "assets/sample-data.json", output, ["sample-002", "sample-001", "sample-005"])
    sample_decisions(job, ratio)
    job["art_brief"] = {"focus": "验证年度三张样张、比例和确认门槛；不作为默认艺术方向。"}
    write_json(output / "share-job.json", job)
    pages = []
    for page in job["pages"]:
        blocks = "".join(f'<p data-block="{block["id"]}">{escape(block["text"])}</p>' for block in page["blocks"])
        pages.append(f'<article class="page" id="{page["id"]}"><header data-status>样例·技术测试，非设计成品</header><main>{blocks}</main></article>')
    canvas = job["canvas"]
    css = f'''*{{box-sizing:border-box}}body{{margin:0;padding:20px;background:#ddd;font-family:"Microsoft YaHei",sans-serif}}
    .page{{position:relative;width:{canvas["width"]}px;height:{canvas["height"]}px;overflow:hidden;margin:0 0 20px;background:#faf8f2;color:#282923}}
    header{{position:absolute;top:30px;left:50px;font-size:24px}}main{{position:absolute;left:50px;right:50px;top:120px}}
    p{{margin:0 0 24px;font-size:40px;line-height:1.5}}'''
    (output / "deck.html").write_text(f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><style>{css}</style></head><body>{"".join(pages)}</body></html>', "utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ratio", choices=["1:1", "3:4", "4:5"], default="3:4")
    args = parser.parse_args()
    build(args.output, args.ratio)
    print("Technical sample prepared; approvals are still required.")
