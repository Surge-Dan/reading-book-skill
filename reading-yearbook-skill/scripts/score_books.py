from __future__ import annotations

import argparse
import json
from pathlib import Path

from yearbook_core import score_books


def main() -> int:
    parser = argparse.ArgumentParser(description="计算前 20% 精选与年度之书候选。")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.input.read_text("utf-8"))
    data["books"] = score_books(data.get("books", []))
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2), "utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
