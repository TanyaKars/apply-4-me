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
    """Open browser, let user log in manually. Saves storage state and closes once authenticated."""
    print("Opening Builtin in browser. Please log in.")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=50)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://builtin.com/login")

        # Wait until the user menu header appears — always visible when authenticated
        try:
            await page.wait_for_selector(".header-dropdown-items", timeout=120_000)
        except Exception:
            pass  # user may have closed the browser

        # storage_state captures cookies + localStorage (where user_session_id lives)
        COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
        await context.storage_state(path=str(STORAGE_STATE_FILE))
        cookies = await context.cookies()
        COOKIE_FILE.write_text(json.dumps(cookies, indent=2))
        print(f"Saved {len(cookies)} cookies + localStorage to {STORAGE_STATE_FILE}")
        await browser.close()


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
