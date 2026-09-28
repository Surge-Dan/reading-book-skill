from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def find_browser_executable() -> str | None:
    candidates = [
        shutil.which("msedge"),
        shutil.which("chrome"),
        shutil.which("chromium"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    return None


def export_cards(html_dir: Path, output_dir: Path) -> dict:
    html_dir, output_dir = Path(html_dir), Path(output_dir)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"status": "unavailable", "reason": "缺少 playwright；HTML 已保留，可稍后导出。", "exported": 0}
    output_dir.mkdir(parents=True, exist_ok=True)
    exported = 0
    try:
        with sync_playwright() as playwright:
            executable = find_browser_executable()
            launch_options = {"headless": True}
            if executable:
                launch_options["executable_path"] = executable
            browser = playwright.chromium.launch(**launch_options)
            page = browser.new_page(viewport={"width": 900, "height": 1200}, device_scale_factor=1)
            for source in sorted(html_dir.glob("*.html")):
                page.goto(source.resolve().as_uri(), wait_until="networkidle")
                page.locator(".card").screenshot(path=str(output_dir / f"{source.stem}.png"))
                exported += 1
            browser.close()
    except Exception as exc:
        return {"status": "failed", "reason": str(exc), "exported": exported}
    return {"status": "pass", "exported": exported, "browser": executable or "playwright-bundled"}


def main() -> int:
    parser = argparse.ArgumentParser(description="将可编辑卡片 HTML 导出为 900×1200 PNG。")
    parser.add_argument("html_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    result = export_cards(args.html_dir, args.output_dir)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
