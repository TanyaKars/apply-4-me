"""LinkedIn Easy Apply adapter."""
import asyncio
from pathlib import Path
from pw.ats.base import BaseATSAdapter


def _read_work_auth() -> dict:
    """Pull work-auth / salary fields from resume SKILL.md."""
    resume_path = Path(__file__).parents[2] / ".claude" / "skills" / "resume" / "SKILL.md"
    result = {
        "authorized_to_work_us": "",
        "requires_sponsorship": "",
        "us_citizen": "",
        "salary_expectation": "",
    }
    if not resume_path.exists():
        return result
    field_map = {
        "- **Authorized to work in the US:**": "authorized_to_work_us",
        "- **Requires visa sponsorship:**": "requires_sponsorship",
        "- **US Citizen:**": "us_citizen",
        "- **Salary expectation:**": "salary_expectation",
    }
    for line in resume_path.read_text().splitlines():
        for prefix, key in field_map.items():
            if line.startswith(prefix):
                result[key] = line.split(":", 1)[-1].strip().lstrip("*").strip()
    return result


def _pick_radio_answer(question: str, options: list[str], auth: dict) -> str | None:
    """Return the option label that best answers the question, or None to skip."""
    q = question.lower()
    opts_lower = [o.lower() for o in options]

    def pick(want: str) -> str | None:
        for o, ol in zip(options, opts_lower):
            if ol.startswith(want):
                return o
        return None

    # Visa / sponsorship — always No
    if any(k in q for k in ("sponsor", "visa", "sponsorship")):
        return pick("no") or pick("false")

    # Hourly / contractor / part-time pay — No
    if any(k in q for k in ("hourly", "contractor rate", "per hour", "part-time pay")):
        return pick("no") or pick("false")

    # Work authorization / eligible to work
    if any(k in q for k in ("authorized", "eligible to work", "legally permitted", "work in the us", "work in us")):
        authorized = (auth.get("authorized_to_work_us") or "yes").lower()
        if authorized in ("yes", "true", "1"):
            return pick("yes") or pick("true")
        return pick("no") or pick("false")

    # US citizen
    if "citizen" in q:
        citizen = (auth.get("us_citizen") or "").lower()
        if citizen in ("yes", "true", "1"):
            return pick("yes") or pick("true")
        if citizen in ("no", "false", "0"):
            return pick("no") or pick("false")

    # No match — skip (leave unanswered, let user fill)
    return None


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
                print("  Reached submit step — waiting for you to review and submit (or close the window).")
                await self._wait_for_close()
                return True

            # Check for Review button — stop and hand off to user
            review_btn = modal.locator(
                "button[aria-label='Review your application'], "
                "button:has-text('Review your application')"
            ).first
            if await review_btn.is_visible(timeout=1000):
                print("  Reached review step — waiting for you to review and submit (or close the window).")
                await self._wait_for_close()
                return True

            # Click Next to advance
            next_btn = modal.locator(
                "button:has-text('Next'), "
                "button[aria-label='Continue to next step']"
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

    async def _wait_for_close(self):
        """Block until the browser page is closed by the user."""
        while True:
            try:
                await self.page.evaluate("() => true")
                await asyncio.sleep(2)
            except Exception:
                return

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
        # Extract groups with labels so we can pick the right answer
        auth = _read_work_auth()
        radio_groups = await self.page.evaluate("""() => {
            const modal = document.querySelector('div[role="dialog"]');
            const root = modal || document.body;
            const groups = {};
            root.querySelectorAll('input[type="radio"]').forEach(r => {
                const name = r.name || r.id;
                if (!name) return;
                if (!groups[name]) {
                    // derive question label from fieldset legend or nearest label-like element
                    let label = '';
                    const fs = r.closest('fieldset');
                    if (fs) {
                        const leg = fs.querySelector('legend, [class*="legend"], [class*="label"], span');
                        if (leg) label = leg.innerText.trim();
                    }
                    if (!label) {
                        // walk up looking for a preceding text node / sibling
                        let node = r.parentElement;
                        for (let i = 0; i < 6 && node; i++) {
                            const prev = node.previousElementSibling;
                            if (prev && !prev.querySelector('input')) {
                                label = prev.innerText.trim();
                                if (label) break;
                            }
                            node = node.parentElement;
                        }
                    }
                    groups[name] = { label, options: [], checked: false };
                }
                const sibLbl = r.id ? document.querySelector('label[for="' + r.id + '"]') : null;
                const optLabel = (sibLbl ? sibLbl.innerText.trim() : '') || r.value || '';
                groups[name].options.push(optLabel);
                if (r.checked) groups[name].checked = true;
            });
            return Object.entries(groups)
                .filter(([, g]) => !g.checked)
                .map(([name, g]) => ({ name, label: g.label, options: g.options }));
        }""")
        for group in radio_groups:
            group_name = group["name"]
            question = group.get("label", "")
            options = group.get("options", [])
            answer = _pick_radio_answer(question, options, auth)
            if answer is None:
                print(f"  Radio {question[:60]!r}: no rule matched, skipping")
                continue
            # Find the radio whose sibling label matches the chosen answer
            radios = self.page.locator(f"input[type='radio'][name='{group_name}']")
            count = await radios.count()
            for i in range(count):
                r = radios.nth(i)
                rid = await r.get_attribute("id") or ""
                lbl_el = self.page.locator(f"label[for='{rid}']").first if rid else None
                lbl_text = (await lbl_el.inner_text()).strip() if lbl_el and await lbl_el.count() > 0 else ""
                val = await r.get_attribute("value") or ""
                if answer.lower() in (lbl_text.lower(), val.lower()):
                    if await r.is_visible(timeout=300):
                        await r.check()
                        print(f"  Radio {question!r:.60}: {answer!r}")
                    break

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
