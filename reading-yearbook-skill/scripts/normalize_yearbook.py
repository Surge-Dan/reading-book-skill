from __future__ import annotations

import argparse
import json
from pathlib import Path

from yearbook_core import normalize_yearbook


def main() -> int:
    parser = argparse.ArgumentParser(description="将微信读书原始数据转为年报数据契约。")
    parser.add_argument("input", type=Path)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = normalize_yearbook(json.loads(args.input.read_text("utf-8")), args.year)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), "utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
