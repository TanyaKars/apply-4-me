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

    async def pause_before_submit(self):
        """Pause execution — user must confirm in UI before submit continues."""
        print("\n=== PAUSED BEFORE SUBMIT ===")
        print("Review the form in the browser window.")
        input("Press ENTER to submit (or Ctrl+C to abort): ")
