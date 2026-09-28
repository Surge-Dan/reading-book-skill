from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
ATLAS = ROOT / "demo-output" / "2026" / "atlas.html"
SCREENSHOT = ROOT / "demo-output" / "2026" / "atlas-preview.png"
EDGE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


def main() -> None:
    console_errors = []
    with sync_playwright() as playwright:
        launch = {"headless": True}
        if EDGE.exists():
            launch["executable_path"] = str(EDGE)
        browser = playwright.chromium.launch(**launch)
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page.on("console", lambda message: console_errors.append(message.text) if message.type == "error" else None)
        page.goto(ATLAS.resolve().as_uri(), wait_until="networkidle")
        assert page.locator(".book").count() == 6
        page.locator('[data-month="2"]').first.click()
        assert page.locator(".book").count() == 1
        page.get_by_role("button", name="全部", exact=True).click()
        page.get_by_role("button", name="已读完", exact=True).click()
        assert page.locator(".book").count() == 1
        page.get_by_role("button", name="全部", exact=True).click()
        page.get_by_role("button", name="E2", exact=True).click()
        assert 1 <= page.locator(".book").count() < 6
        page.locator(".book").first.click()
        assert page.locator("dialog[open]").count() == 1
        assert page.locator("#detailContent").get_by_text("证据索引").count() == 1
        page.locator(".close").click()
        page.screenshot(path=str(SCREENSHOT), full_page=True)
        browser.close()
    assert not console_errors, console_errors
    print("ATLAS_UI=PASS")


if __name__ == "__main__":
    main()
