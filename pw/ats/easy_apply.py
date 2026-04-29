"""LinkedIn Easy Apply adapter."""
from pw.ats.base import BaseATSAdapter


class LinkedInEasyApplyAdapter(BaseATSAdapter):
    """Fills LinkedIn Easy Apply modal step-by-step."""

    async def fill_form(self, job_url: str) -> bool:
        await self.page.goto(job_url, wait_until="domcontentloaded", timeout=30_000)
        await self.page.wait_for_timeout(3000)

        # Click the Easy Apply button to open the modal
        easy_btn = self.page.locator("button:has-text('Easy Apply')").first
        if not await easy_btn.is_visible(timeout=5000):
            print("Easy Apply button not found on page.")
            return False

        await easy_btn.click()
        await self.page.wait_for_timeout(2000)

        max_steps = 15
        for step in range(max_steps):
            print(f"  Easy Apply step {step + 1}")

            # If a "dismiss" / close for "You've already applied" notice appears, bail
            already = self.page.locator("text=You've already applied")
            if await already.count() > 0:
                print("  Already applied to this job.")
                return False

            await self._fill_current_step()

            # Check for the final Submit button first
            submit_btn = self.page.locator(
                "button:has-text('Submit application'), "
                "button[aria-label*='Submit application']"
            ).first
            if await submit_btn.is_visible(timeout=1000):
                print("  Reached submit step — pausing for your review.")
                await self.pause_before_submit()
                await submit_btn.click()
                await self.page.wait_for_timeout(3000)
                return True

            # Click Next or Review to advance
            next_btn = self.page.locator(
                "button:has-text('Next'), button:has-text('Review'), "
                "button[aria-label='Continue to next step']"
            ).first
            if await next_btn.is_visible(timeout=3000):
                await next_btn.click()
                await self.page.wait_for_timeout(1500)
            else:
                print("  No Next/Submit button found — stopping.")
                break

        return False

    async def _fill_current_step(self):
        """Best-effort fill of all inputs visible on the current step."""
        p = self.personal

        # ── Phone ──────────────────────────────────────────────────────────
        phone_field = self.page.locator(
            "input[id*='phoneNumber'], input[name*='phoneNumber'], "
            "input[id*='phone'], input[name*='phone']"
        ).first
        if await phone_field.is_visible(timeout=500):
            val = await phone_field.input_value()
            if not val and p.get("phone"):
                await phone_field.fill(p["phone"])

        # ── Resume upload ───────────────────────────────────────────────────
        # LinkedIn shows either a "Change resume" button or a file input.
        # Prefer the "Upload resume" tab if available.
        upload_tab = self.page.locator(
            "label:has-text('Upload resume'), button:has-text('Upload resume')"
        ).first
        if await upload_tab.is_visible(timeout=500):
            await upload_tab.click()
            await self.page.wait_for_timeout(500)

        file_input = self.page.locator("input[type='file']").first
        if await file_input.count() > 0:
            await file_input.set_input_files(self.pdf_path)
            await self.page.wait_for_timeout(1000)

        # ── Text inputs / textareas ─────────────────────────────────────────
        # Fill empty text fields with sensible defaults from resume personal data
        field_map = {
            "city": p.get("location", ""),
            "location": p.get("location", ""),
            "linkedin": p.get("linkedin", ""),
            "website": p.get("github", ""),
            "github": p.get("github", ""),
            "salary": "",  # leave blank
        }
        for keyword, value in field_map.items():
            if not value:
                continue
            field = self.page.locator(
                f"input[id*='{keyword}'], input[name*='{keyword}'], "
                f"input[placeholder*='{keyword}' i]"
            ).first
            if await field.is_visible(timeout=300):
                current = await field.input_value()
                if not current:
                    await field.fill(value)

        # ── Radio buttons (Yes/No work-auth questions) ──────────────────────
        # Default: select the first option for each unanswered radio group
        radio_groups = await self.page.evaluate("""() => {
            const groups = {};
            document.querySelectorAll('input[type="radio"]').forEach(r => {
                const name = r.name || r.id;
                if (!groups[name]) groups[name] = [];
                groups[name].push(r.checked);
            });
            // Return names of groups where nothing is checked
            return Object.entries(groups)
                .filter(([, checks]) => !checks.some(Boolean))
                .map(([name]) => name);
        }""")
        for group_name in radio_groups:
            first_radio = self.page.locator(
                f"input[type='radio'][name='{group_name}'], "
                f"input[type='radio'][id='{group_name}']"
            ).first
            if await first_radio.is_visible(timeout=300):
                await first_radio.check()

        # ── Dropdowns (select elements) ─────────────────────────────────────
        # Leave dropdowns that already have a value; pick first non-empty option for blank ones
        selects = self.page.locator("select")
        count = await selects.count()
        for i in range(count):
            sel = selects.nth(i)
            if not await sel.is_visible(timeout=300):
                continue
            current_val = await sel.input_value()
            if not current_val or current_val == "Select an option":
                # Pick the first real option (skip placeholder at index 0)
                options = await sel.locator("option").all()
                for opt in options[1:]:
                    val = await opt.get_attribute("value")
                    if val:
                        await sel.select_option(value=val)
                        break
