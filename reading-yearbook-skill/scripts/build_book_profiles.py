from __future__ import annotations

import argparse
import json
from pathlib import Path

from yearbook_core import build_profiles


def main() -> int:
    parser = argparse.ArgumentParser(description="从证据受限的数据生成全部单书档案。")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.input.read_text("utf-8"))
    args.output.write_text(json.dumps(build_profiles(data.get("books", [])), ensure_ascii=False, indent=2), "utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
