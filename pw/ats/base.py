"""Abstract ATS adapter base class."""
from abc import ABC, abstractmethod
from playwright.async_api import Page


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
