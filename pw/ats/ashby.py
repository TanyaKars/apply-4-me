"""Ashby HQ ATS adapter."""
from pw.ats.base import BaseATSAdapter


class AshbyAdapter(BaseATSAdapter):

    async def fill_form(self, job_url: str) -> bool:
        await self.page.goto(job_url, wait_until="domcontentloaded", timeout=30_000)
        await self.page.wait_for_timeout(2000)

        p = self.personal

        # Ashby uses React form — fields may be labeled
        name_parts = p.get("name", "").split()
        first = name_parts[0] if name_parts else ""
        last = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

        await self.safe_fill("input[name='_systemfield_name'], input[placeholder*='Full name' i]", p.get("name", ""))
        await self.safe_fill("input[name='_systemfield_first_name'], input[placeholder*='First' i]", first)
        await self.safe_fill("input[name='_systemfield_last_name'], input[placeholder*='Last' i]", last)
        await self.safe_fill("input[name='_systemfield_email'], input[type='email']", p.get("email", ""))
        await self.safe_fill("input[name='_systemfield_phone'], input[type='tel']", p.get("phone", ""))

        # Resume upload
        await self.safe_upload("input[type='file']", self.pdf_path)

        # Social links
        await self.safe_fill("input[name*='linkedin' i]", p.get("linkedin", ""))
        await self.safe_fill("input[name*='github' i]", p.get("github", ""))

        print("Ashby form filled. Ready to submit.")
        await self.pause_before_submit()

        submit_btn = self.page.locator("button[type='submit']").first
        if await submit_btn.is_visible():
            await submit_btn.click()
            await self.page.wait_for_timeout(3000)
            return True

        return False
