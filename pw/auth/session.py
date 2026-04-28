"""
LinkedIn session auth — saves/loads cookies for reuse.

Usage:
  python -m pw.auth.session --setup   # opens browser for manual login
  python -m pw.auth.session --check   # verify session is valid
"""
import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright

COOKIE_FILE = Path.home() / ".apply4me" / "linkedin_cookies.json"


async def setup_session():
    """Open browser, let user log in manually, save cookies."""
    print("Opening LinkedIn in browser. Please log in, then close the browser window.")
    print("Cookies will be saved automatically once you close it.")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=50)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://www.linkedin.com/login")

        # Wait until user navigates to feed (logged in)
        try:
            await page.wait_for_url("**/feed/**", timeout=120_000)
        except Exception:
            pass  # user may have closed the browser

        cookies = await context.cookies()
        COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
        COOKIE_FILE.write_text(json.dumps(cookies, indent=2))
        print(f"Saved {len(cookies)} cookies to {COOKIE_FILE}")
        await browser.close()


def load_cookies() -> list[dict]:
    """Load saved LinkedIn cookies."""
    if not COOKIE_FILE.exists():
        raise FileNotFoundError(f"No session found at {COOKIE_FILE}. Run --setup first.")
    return json.loads(COOKIE_FILE.read_text())


async def check_session() -> bool:
    """Verify saved session is still valid."""
    if not COOKIE_FILE.exists():
        print("No session file found.")
        return False

    cookies = load_cookies()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        await context.add_cookies(cookies)
        page = await context.new_page()
        await page.goto("https://www.linkedin.com/feed/")
        url = page.url
        await browser.close()

    valid = "feed" in url
    print(f"Session {'valid' if valid else 'expired'} (url: {url})")
    return valid


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--setup" in args:
        asyncio.run(setup_session())
    elif "--check" in args:
        asyncio.run(check_session())
    else:
        print("Usage: python -m pw.auth.session [--setup|--check]")
