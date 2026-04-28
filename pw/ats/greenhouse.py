"""Greenhouse ATS adapter."""
from playwright.async_api import Page
from pw.ats.base import BaseATSAdapter


class GreenhouseAdapter(BaseATSAdapter):

    async def fill_form(self, job_url: str) -> bool:
        await self.page.goto(job_url, wait_until="domcontentloaded", timeout=30_000)
        await self.page.wait_for_timeout(2000)

        p = self.personal

        # Basic fields
        await self.safe_fill("input#first_name, input[name='job_application[first_name]']",
                             p.get("name", "").split()[0] if p.get("name") else "")

        last_name = " ".join(p.get("name", "").split()[1:]) if p.get("name") else ""
        await self.safe_fill("input#last_name, input[name='job_application[last_name]']", last_name)
        await self.safe_fill("input#email, input[name='job_application[email]']", p.get("email", ""))
        await self.safe_fill("input#phone, input[name='job_application[phone]']", p.get("phone", ""))

        # Location
        await self.safe_fill("input#job_application_location", p.get("location", ""))

        # Resume upload
        await self.safe_upload("input[name='job_application[resume]'], input#resume", self.pdf_path)

        # LinkedIn / GitHub / Website
        await self.safe_fill("input[name*='linkedin'], input[id*='linkedin']", p.get("linkedin", ""))
        await self.safe_fill("input[name*='github'], input[id*='github']", p.get("github", ""))

        # Handle custom questions (attempt to fill text areas)
        textareas = self.page.locator("textarea.application-answer")
        count = await textareas.count()
        for i in range(count):
            # Leave custom questions empty — user will fill manually
            pass

        print("Greenhouse form filled. Ready to submit.")
        await self.pause_before_submit()

        # Submit
        submit_btn = self.page.locator("input[type='submit'], button[type='submit']").first
        if await submit_btn.is_visible():
            await submit_btn.click()
            await self.page.wait_for_timeout(3000)
            return True

        return False
