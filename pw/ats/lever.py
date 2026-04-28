"""Lever ATS adapter."""
from pw.ats.base import BaseATSAdapter


class LeverAdapter(BaseATSAdapter):

    async def fill_form(self, job_url: str) -> bool:
        await self.page.goto(job_url, wait_until="domcontentloaded", timeout=30_000)
        await self.page.wait_for_timeout(2000)

        p = self.personal
        full_name = p.get("name", "")

        await self.safe_fill("input[name='name'], input#name", full_name)
        await self.safe_fill("input[name='email'], input#email", p.get("email", ""))
        await self.safe_fill("input[name='phone'], input#phone", p.get("phone", ""))

        # Location / org fields
        await self.safe_fill("input[name='location']", p.get("location", ""))
        await self.safe_fill("input[name*='org']", "")

        # Resume upload — Lever uses a file input
        await self.safe_upload("input[type='file'][name='resume'], input#resume-upload-input", self.pdf_path)

        # Links
        await self.safe_fill("input[name*='linkedin']", p.get("linkedin", ""))
        await self.safe_fill("input[name*='github']", p.get("github", ""))
        await self.safe_fill("input[name*='website']", p.get("github", ""))

        print("Lever form filled. Ready to submit.")
        await self.pause_before_submit()

        submit_btn = self.page.locator("button[type='submit'], input[type='submit']").first
        if await submit_btn.is_visible():
            await submit_btn.click()
            await self.page.wait_for_timeout(3000)
            return True

        return False
