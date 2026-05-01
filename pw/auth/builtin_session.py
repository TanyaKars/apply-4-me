"""
Builtin session auth — saves/loads cookies for reuse.

Usage:
  python -m pw.auth.builtin_session --setup   # opens browser for manual login
"""
import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright

COOKIE_FILE = Path.home() / ".apply4me" / "builtin_cookies.json"


async def setup_session():
    """Open browser, let user log in manually, save cookies."""
    print("Opening Builtin in browser. Please log in, then close the browser window.")
    print("Cookies will be saved automatically once you close it.")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=50)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://builtin.com/login")

        # Wait until the user navigates away from the login page
        try:
            await page.wait_for_function(
                "!window.location.pathname.includes('/login') && "
                "!window.location.pathname.includes('/sign-in')",
                timeout=120_000,
            )
        except Exception:
            pass  # user may have closed the browser

        cookies = await context.cookies()
        COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
        COOKIE_FILE.write_text(json.dumps(cookies, indent=2))
        print(f"Saved {len(cookies)} cookies to {COOKIE_FILE}")
        await browser.close()


def load_cookies() -> list[dict]:
    """Load saved Builtin cookies, or return empty list if none saved."""
    if not COOKIE_FILE.exists():
        return []
    return json.loads(COOKIE_FILE.read_text())


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--setup" in args:
        asyncio.run(setup_session())
    else:
        print("Usage: python -m pw.auth.builtin_session [--setup]")
