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
STORAGE_STATE_FILE = Path.home() / ".apply4me" / "builtin_storage_state.json"


async def setup_session():
    """Open browser, let user log in manually, save cookies + localStorage when they close it."""
    print("Opening Builtin. Log in, then close the browser window.")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=50)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://builtin.com/login")

        # Save full storage state (cookies + localStorage) every 3s while browser is open.
        # Loop exits when the user closes the browser window.
        while browser.is_connected():
            try:
                COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
                # storage_state captures cookies AND localStorage — both needed for Builtin auth
                await context.storage_state(path=str(STORAGE_STATE_FILE))
                # Also save raw cookies for the httpx scraper
                cookies = await context.cookies()
                if cookies:
                    COOKIE_FILE.write_text(json.dumps(cookies, indent=2))
            except Exception:
                break
            await asyncio.sleep(3)

        print(f"Session saved.")


def load_cookies() -> list[dict]:
    """Load saved Builtin cookies, or return empty list if none saved."""
    if not COOKIE_FILE.exists():
        return []
    return json.loads(COOKIE_FILE.read_text())


def storage_state_path() -> str | None:
    """Return storage state path if it exists, else None."""
    return str(STORAGE_STATE_FILE) if STORAGE_STATE_FILE.exists() else None


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--setup" in args:
        asyncio.run(setup_session())
    else:
        print("Usage: python -m pw.auth.builtin_session [--setup]")
