"""Abstract ATS adapter base class."""
from abc import ABC, abstractmethod
from playwright.async_api import Page

# JS injected on every page load — dismisses cookie banners and chat overlays
# via MutationObserver so it catches widgets that appear after initial load.
_OVERLAY_DISMISSAL_JS = """
(function() {
    const ACCEPT_TEXTS = [
        'accept all', 'accept cookies', 'accept all cookies', 'i accept',
        'agree', 'agree all', 'allow all', 'allow cookies', 'got it',
        'ok', 'okay', 'close', 'dismiss', 'consent', 'continue',
    ];
    const CLOSE_SELECTORS = [
        '#onetrust-accept-btn-handler',
        '.cc-accept', '.cc-dismiss', '.cc-btn',
        '[class*="cookie"] button[class*="accept"]',
        '[class*="cookie"] button[class*="agree"]',
        '[class*="cookie"] button[class*="allow"]',
        '[id*="cookie-consent"] button',
        '[class*="cookiebanner"] button',
        '[class*="cookie-banner"] button',
        '[class*="cookie-notice"] button',
        '[data-testid*="cookie"] button',
        /* chat widgets */
        '#intercom-container [class*="close"]',
        '[class*="intercom-"] [aria-label*="close" i]',
        '[id*="drift"] [class*="close"]',
        '[class*="drift-widget"] [class*="close"]',
        '[id*="hubspot-messages"] [class*="close"]',
        '[class*="live-chat"] button[class*="close"]',
        '[class*="chat-widget"] button[class*="close"]',
        /* generic modal close */
        '[role="dialog"] button[aria-label*="close" i]',
        '[role="dialog"] button[aria-label*="dismiss" i]',
    ];

    function tryDismiss() {
        for (const sel of CLOSE_SELECTORS) {
            try {
                const el = document.querySelector(sel);
                if (el && el.offsetParent !== null) el.click();
            } catch(e) {}
        }
        for (const btn of document.querySelectorAll('button, [role="button"], a[class*="btn"]')) {
            try {
                if (btn.offsetParent === null) continue;
                const text = (btn.innerText || btn.textContent || '').trim().toLowerCase();
                if (ACCEPT_TEXTS.includes(text)) btn.click();
            } catch(e) {}
        }
    }

    tryDismiss();
    new MutationObserver(tryDismiss).observe(document.documentElement, {childList: true, subtree: true});
})();
"""


async def setup_overlay_dismissal(page: Page):
    """Install auto-dismissal of cookie banners and chat overlays on every page load."""
    await page.add_init_script(_OVERLAY_DISMISSAL_JS)


class BaseATSAdapter(ABC):
    """Base class for ATS form filling adapters."""

    def __init__(self, page: Page, resume_data: dict, pdf_path: str):
        self.page = page
        self.resume = resume_data
        self.pdf_path = pdf_path
        self.personal = resume_data.get("personal", {})

    @abstractmethod
    async def fill_form(self, job_url: str) -> bool:
        """Navigate to job URL and fill application form. Returns True if ready to submit."""
        pass

    async def safe_fill(self, selector: str, value: str):
        """Fill a field if it exists."""
        try:
            el = self.page.locator(selector).first
            if await el.is_visible(timeout=3000):
                await el.fill(value)
                return True
        except Exception:
            pass
        return False

    async def safe_upload(self, selector: str, file_path: str):
        """Upload a file if the input exists."""
        try:
            el = self.page.locator(selector).first
            if await el.count() > 0:
                await el.set_input_files(file_path)
                return True
        except Exception:
            pass
        return False

    async def pause_before_submit(self):
        """Pause execution — user must confirm in UI before submit continues."""
        print("\n=== PAUSED BEFORE SUBMIT ===")
        print("Review the form in the browser window.")
        print("The backend will receive a confirmation request...")
        # In production, this would communicate with the backend
        # which then waits for user confirmation from the frontend
        input("Press ENTER to submit (or Ctrl+C to abort): ")
