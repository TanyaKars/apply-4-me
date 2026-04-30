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

        return await self._fill_modal()

    async def _fill_modal(self) -> bool:
        """Run the Easy Apply step loop. Modal must already be open."""
        # Scope all button checks to the modal — avoids false positives from the main LinkedIn page
        modal = self.page.locator("div[role='dialog']").first

        max_steps = 15
        for step in range(max_steps):
            print(f"  Easy Apply step {step + 1}")

            # If a "dismiss" / close for "You've already applied" notice appears, bail
            already = modal.locator("text=You've already applied")
            if await already.count() > 0:
                print("  Already applied to this job.")
                return False

            await self._fill_current_step()

            # Check for the final Submit button first (scoped to modal)
            submit_btn = modal.locator(
                "button:has-text('Submit application'), "
                "button[aria-label*='Submit application']"
            ).first
            if await submit_btn.is_visible(timeout=1500):
                print("  Reached submit step — pausing for your review.")
                try:
                    await self.pause_before_submit()
                except EOFError:
                    # Running as subprocess with no TTY — wait briefly so user can see the form
                    print("  No terminal available — waiting 15 s before submitting.")
                    await self.page.wait_for_timeout(15_000)
                await submit_btn.click()
                await self.page.wait_for_timeout(3000)
                return True

            # Click Next / Review your application to advance (scoped to modal)
            next_btn = modal.locator(
                "button:has-text('Next'), "
                "button[aria-label='Continue to next step'], "
                "button[aria-label='Review your application']"
            ).first
            if await next_btn.is_visible(timeout=4000):
                label = (await next_btn.inner_text()).strip()
                print(f"  Clicking: '{label}'")
                await next_btn.click()
                await self.page.wait_for_timeout(2000)
            else:
                print("  No Next/Review/Submit button found — stopping.")
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
        # Detect resume upload step by checking if an "Upload resume" section is visible.
        # Do NOT click the button — that opens the native Finder dialog.
        # Playwright's set_input_files() injects the file directly on the hidden input.
        upload_section = self.page.locator(
            "label:has-text('Upload resume'), button:has-text('Upload resume')"
        ).first
        if await upload_section.is_visible(timeout=500):
            file_input = self.page.locator("input[type='file']").first
            if await file_input.count() > 0:
                await file_input.set_input_files(self.pdf_path)
                print(f"  Uploaded resume: {self.pdf_path}")
                await self.page.wait_for_timeout(1000)

        # ── Text inputs / textareas ─────────────────────────────────────────
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
        # Scope to modal via JS to avoid touching radio groups on the main LinkedIn page
        radio_groups = await self.page.evaluate("""() => {
            const modal = document.querySelector('div[role="dialog"]');
            const root = modal || document.body;
            const groups = {};
            root.querySelectorAll('input[type="radio"]').forEach(r => {
                const name = r.name || r.id;
                if (!groups[name]) groups[name] = [];
                groups[name].push(r.checked);
            });
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
        # Scope to modal to avoid touching selects on the main LinkedIn page
        modal_sel = "div[role='dialog'] select"
        selects = self.page.locator(modal_sel)
        count = await selects.count()
        for i in range(count):
            sel = selects.nth(i)
            if not await sel.is_visible(timeout=300):
                continue
            current_val = await sel.input_value()
            if not current_val or current_val == "Select an option":
                options = await sel.locator("option").all()
                for opt in options[1:]:
                    val = await opt.get_attribute("value")
                    if val:
                        await sel.select_option(value=val)
                        break
