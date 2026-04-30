"""AI-guided form filler — handles any unknown ATS using Claude to interpret form fields."""
import asyncio
import json
import os
from pathlib import Path

from playwright.async_api import Page
from pw.ats.base import BaseATSAdapter


def _get_api_key() -> str:
    key = os.getenv("ANTHROPIC_API_KEY")
    if key:
        return key
    config_file = Path.home() / ".apply4me" / "config.json"
    if config_file.exists():
        config = json.loads(config_file.read_text())
        return config.get("anthropic_api_key", "")
    raise ValueError("ANTHROPIC_API_KEY not set")


# JS snippet injected into the page to extract visible, fillable form fields
_EXTRACT_FIELDS_JS = """() => {
    const fields = [];
    let idx = 0;

    function getLabel(el) {
        if (el.id) {
            const lbl = document.querySelector('label[for="' + el.id + '"]');
            if (lbl) return lbl.innerText.trim();
        }
        const aria = el.getAttribute('aria-label') || el.getAttribute('aria-labelledby');
        if (aria) {
            const ref = document.getElementById(aria);
            return ref ? ref.innerText.trim() : aria;
        }
        if (el.placeholder) return el.placeholder;
        const parent = el.closest('label');
        if (parent) return parent.innerText.trim();
        const group = el.closest('[class*="field"], [class*="form-group"], [class*="question"], [class*="Question"]');
        if (group) {
            const lbl = group.querySelector('label, [class*="label"], [class*="Label"]');
            if (lbl) return lbl.innerText.trim();
        }
        return el.name || el.id || '';
    }

    function isVisible(el) {
        return el.offsetParent !== null && !el.disabled;
    }

    // text / email / tel / number / url / date inputs
    document.querySelectorAll(
        'input[type="text"], input[type="email"], input[type="tel"], ' +
        'input[type="number"], input[type="url"], input[type="date"], ' +
        'input:not([type])'
    ).forEach(el => {
        if (!isVisible(el) || el.readOnly) return;
        fields.push({
            idx: idx++, type: 'text',
            name: el.name || '', id: el.id || '',
            label: getLabel(el), value: el.value, required: el.required,
        });
    });

    // textareas
    document.querySelectorAll('textarea').forEach(el => {
        if (!isVisible(el)) return;
        fields.push({
            idx: idx++, type: 'textarea',
            name: el.name || '', id: el.id || '',
            label: getLabel(el), value: el.value, required: el.required,
        });
    });

    // selects
    document.querySelectorAll('select').forEach(el => {
        if (!isVisible(el)) return;
        const options = Array.from(el.options).map(o => o.text.trim()).filter(Boolean);
        fields.push({
            idx: idx++, type: 'select',
            name: el.name || '', id: el.id || '',
            label: getLabel(el), value: el.value,
            options: options, required: el.required,
        });
    });

    // radio groups — one entry per group
    const radioGroups = {};
    document.querySelectorAll('input[type="radio"]').forEach(el => {
        if (!isVisible(el)) return;
        const key = el.name || el.id || String(idx);
        if (!radioGroups[key]) {
            radioGroups[key] = {
                idx: idx++, type: 'radio',
                name: key, id: '',
                label: getLabel(el), options: [], selected: null,
            };
        }
        const optLabel = el.value ||
            (el.parentElement ? el.parentElement.innerText.trim() : '') ||
            el.id || '';
        radioGroups[key].options.push(optLabel);
        if (el.checked) radioGroups[key].selected = optLabel;
    });
    Object.values(radioGroups).forEach(g => fields.push(g));

    // standalone checkboxes
    document.querySelectorAll('input[type="checkbox"]').forEach(el => {
        if (!isVisible(el)) return;
        fields.push({
            idx: idx++, type: 'checkbox',
            name: el.name || '', id: el.id || '',
            label: getLabel(el), checked: el.checked,
        });
    });

    return fields;
}"""


class AIFillerAdapter(BaseATSAdapter):
    """General-purpose adapter that uses Claude to fill any application form."""

    def __init__(self, page: Page, resume_data: dict, pdf_path: str, jd_text: str = ""):
        super().__init__(page, resume_data, pdf_path)
        self.jd_text = jd_text

    def _is_linkedin_auth(self) -> bool:
        return "linkedin.com" in self.page.url and any(
            p in self.page.url for p in ("oauth", "login", "authwall", "uas/login")
        )

    def _is_login_wall(self) -> bool:
        url = self.page.url.lower()
        title = ""  # checked separately to avoid async here
        return any(p in url for p in (
            "accounts.google.com", "login.microsoftonline.com", "login.live.com",
        ))

    async def _check_login_wall(self) -> str | None:
        """Return 'linkedin', 'other', or None."""
        if self._is_linkedin_auth():
            return "linkedin"
        url = self.page.url.lower()
        title = (await self.page.title()).lower()
        if any(p in url for p in ("accounts.google.com", "login.microsoftonline", "login.live.com")):
            return "other"
        if any(p in title for p in ("sign in", "log in", "login")):
            return "other"
        return None

    async def _click_linkedin_apply(self) -> bool:
        """If on a LinkedIn job page, click the Apply button and switch to the new tab."""
        if "linkedin.com/jobs/view/" not in self.page.url:
            return False
        try:
            apply_btn = self.page.locator("button:has-text('Apply'), a:has-text('Apply')").first
            if not await apply_btn.is_visible(timeout=3000):
                return False
            print("  LinkedIn job page — clicking Apply to open external form...")
            async with self.page.context.expect_page(timeout=5000) as new_page_info:
                await apply_btn.click()
            new_page = await new_page_info.value
            await new_page.wait_for_load_state("networkidle", timeout=30_000)
            self.page = new_page
            print(f"  Switched to external form: {self.page.url}")
            return True
        except Exception as e:
            print(f"  Could not click Apply button: {e}")
            return False

    async def fill_form(self, job_url: str) -> bool:
        # LinkedIn never reaches networkidle due to background polling — use domcontentloaded
        wait = "domcontentloaded" if "linkedin.com" in job_url else "networkidle"
        await self.page.goto(job_url, wait_until=wait, timeout=30_000)
        await self.page.wait_for_timeout(2000)

        # If this is a LinkedIn job page, click Apply to get to the actual ATS form
        if "linkedin.com/jobs/view/" in self.page.url:
            switched = False
            try:
                switched = await self._click_linkedin_apply()
            except Exception as e:
                print(f"  LinkedIn apply click failed: {e} — continuing on current page")

            if not switched:
                # No new tab opened — check if an Easy Apply modal appeared instead
                await self.page.wait_for_timeout(1000)
                dialog = self.page.locator("div[role='dialog']")
                if await dialog.count() > 0:
                    print("  Easy Apply modal detected — handing off to Easy Apply adapter.")
                    from pw.ats.easy_apply import LinkedInEasyApplyAdapter
                    ea = LinkedInEasyApplyAdapter(self.page, self.resume, self.pdf_path)
                    return await ea._fill_modal()

        for step in range(20):
            print(f"\n--- AI Filler: step {step + 1} | url: {self.page.url} ---")

            wall = await self._check_login_wall()

            if wall == "linkedin":
                print("  LinkedIn auth wall detected — warming up session...")
                return_url = self.page.url
                try:
                    await self.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=15_000)
                    if "feed" in self.page.url:
                        print("  LinkedIn session active — navigating back to apply URL...")
                        await self.page.goto(job_url, wait_until="domcontentloaded", timeout=30_000)
                        await self.page.wait_for_timeout(1000)
                        continue
                    else:
                        print("  LinkedIn session expired.")
                except Exception:
                    pass
                # Session didn't work — fall through to manual login
                print("\n  ⚠️  LinkedIn session is expired.")
                print("  → Go to Settings in the apply4me UI and click 'Re-authenticate'.")
                print("  → Then retry applying to this job.\n")
                await self.page.goto(return_url, wait_until="networkidle", timeout=30_000)
                wall = "other"

            if wall == "other":
                print(f"  Login wall detected ({self.page.url})")
                print("  Please log in manually in the browser window.")
                input("  Press ENTER once you are logged in and the form is visible: ")
                await self.page.wait_for_load_state("networkidle", timeout=15_000)
                await self.page.wait_for_timeout(1000)
                continue

            fields = await self.page.evaluate(_EXTRACT_FIELDS_JS)
            fillable = [f for f in fields if f.get("type") != "file"]

            if fillable:
                print(f"  {len(fillable)} fillable fields — asking Claude...")
                instructions = await self._ask_claude(fillable)
                await self._apply_instructions(instructions, fillable)
            else:
                print("  No fillable fields on this step.")

            await self._upload_resume_if_needed()

            # Check for submit button — must be type=submit OR explicit submit/send text
            # Do NOT match generic "Apply" buttons (those are navigation, not submission)
            try:
                submit = self.page.locator(
                    "button[type='submit'], input[type='submit'], "
                    "button:has-text('Submit'), button:has-text('Send application'), "
                    "button:has-text('Send Application')"
                ).first
                if await submit.is_visible(timeout=2000):
                    label = (await submit.inner_text()).strip().lower()
                    if any(w in label for w in ("submit", "send application")):
                        print("  Submit button found — pausing for review.")
                        await self.pause_before_submit()
                        await submit.click()
                        await self.page.wait_for_timeout(3000)
                        return True
            except Exception:
                pass

            # Check for next/continue button
            try:
                next_btn = self.page.locator(
                    "button:has-text('Next'), button:has-text('Continue'), "
                    "button:has-text('next'), button:has-text('continue'), "
                    "button:has-text('Save and continue'), "
                    "button:has-text('Review'), button[aria-label*='Review'], "
                    "button[data-live-test-easy-apply-review-button]"
                ).first
                if await next_btn.is_visible(timeout=2000):
                    await next_btn.click()
                    await self.page.wait_for_timeout(2000)
                    continue
            except Exception:
                pass

            # If no fields were found, this may be a job description page with an Apply button
            # Click it (same-page — may scroll to form, reveal it, or navigate)
            if not fillable:
                try:
                    # :text-is() does exact match — avoids "Apply with Indeed" etc.
                    apply_btn = self.page.locator("button:text-is('Apply'), a:text-is('Apply')").first
                    if await apply_btn.is_visible(timeout=2000):
                        url_before = self.page.url
                        print("  No form fields — clicking Apply button on this page...")
                        await apply_btn.click()
                        await self.page.wait_for_timeout(2000)
                        # If we navigated to a new page, wait for it to load
                        if self.page.url != url_before:
                            await self.page.wait_for_load_state("networkidle", timeout=15_000)
                        continue
                except Exception as e:
                    print(f"  Could not click Apply button: {e}")

            # Nothing to click — pause and let user decide
            print("  No next/submit button found.")
            action = input("  [c] continue scanning / [q] quit: ").strip().lower()
            if action == "q":
                break
            await self.page.wait_for_timeout(2000)

        return False

    async def _ask_claude(self, fields: list[dict]) -> list[dict]:
        """Send form fields to Claude, get back fill instructions."""
        try:
            import anthropic
            api_key = _get_api_key()
        except Exception as e:
            print(f"  Claude unavailable: {e}")
            return []

        client = anthropic.Anthropic(api_key=api_key)

        # Slim down field list for the prompt
        slim = []
        for f in fields:
            item = {"idx": f["idx"], "type": f["type"], "label": f.get("label", "")}
            if f["type"] in ("select", "radio"):
                item["options"] = f.get("options", [])
            if f.get("required"):
                item["required"] = True
            slim.append(item)

        jd_section = f"\n\nJOB DESCRIPTION:\n{self.jd_text}" if self.jd_text else ""

        prompt = f"""You are filling out a job application form on behalf of the candidate.

CANDIDATE DATA:
{json.dumps(self.resume, indent=2)}
{jd_section}

FORM FIELDS (current step):
{json.dumps(slim, indent=2)}

Rules:
- Fill each field from the candidate data above
- Work authorization in the US → "Yes"
- Requires visa sponsorship → "No"
- Salary / compensation → leave empty (return "")
- Years of experience → calculate from resume dates
- Cover letter / "why this company" text → 2-3 sentences from the summary tailored to the role
- For select/radio: return the exact option text that best matches; if none fit, return ""
- For checkbox: return "true" to check, "false" to leave unchecked
- Return "" for anything you cannot answer from the data

Return ONLY a JSON array, no explanation:
[{{"idx": 0, "value": "..."}}]"""

        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}]
        )
        text = message.content[0].text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1])
        return json.loads(text)

    async def _apply_instructions(self, instructions: list[dict], fields: list[dict]):
        """Fill the form using Claude's instructions."""
        field_map = {f["idx"]: f for f in fields}

        for instr in instructions:
            idx = instr.get("idx")
            value = str(instr.get("value", ""))
            if not value:
                continue

            field = field_map.get(idx)
            if not field:
                continue

            ftype = field.get("type")
            fid = field.get("id", "")
            name = field.get("name", "")
            label = field.get("label", "")

            # Use attribute selector — CSS `#id` breaks on IDs containing `:` or `.`
            sel = f'[id="{fid}"]' if fid else (f"[name='{name}']" if name else None)
            if not sel:
                print(f"  Skipping field idx={idx} ({label!r}) — no selector")
                continue

            try:
                el = self.page.locator(sel).first

                if ftype in ("text", "textarea"):
                    if await el.is_visible(timeout=2000):
                        await el.fill(value)
                        print(f"  Filled {label!r}: {value[:60]}")

                elif ftype == "select":
                    if await el.is_visible(timeout=2000):
                        try:
                            await el.select_option(label=value)
                        except Exception:
                            await el.select_option(value=value)
                        print(f"  Selected {label!r}: {value}")

                elif ftype == "radio":
                    # Try by value attribute first, then by adjacent label text
                    radio = self.page.locator(
                        f"input[type='radio'][name='{name}'][value='{value}']"
                    ).first
                    if not await radio.is_visible(timeout=1000):
                        # Search all radios in the group, match by label
                        radios = self.page.locator(f"input[type='radio'][name='{name}']")
                        count = await radios.count()
                        for i in range(count):
                            r = radios.nth(i)
                            parent_text = await r.evaluate(
                                "el => el.parentElement?.innerText?.trim() || ''"
                            )
                            if value.lower() in parent_text.lower():
                                radio = r
                                break
                    if await radio.is_visible(timeout=1000):
                        await radio.click()
                        print(f"  Radio {label!r}: {value}")

                elif ftype == "checkbox":
                    want_checked = value.lower() == "true"
                    if await el.is_visible(timeout=2000):
                        currently = await el.is_checked()
                        if want_checked != currently:
                            await el.click()
                        print(f"  Checkbox {label!r}: {value}")

            except Exception as e:
                print(f"  Could not fill {label!r} (idx={idx}): {e}")

    async def _upload_resume_if_needed(self):
        """Upload resume PDF if a file input is present and visible."""
        if not self.pdf_path:
            return
        try:
            file_inputs = self.page.locator("input[type='file']")
            count = await file_inputs.count()
            for i in range(count):
                fi = file_inputs.nth(i)
                if await fi.count() > 0:
                    await fi.set_input_files(self.pdf_path)
                    print(f"  Uploaded resume PDF: {self.pdf_path}")
                    break
        except Exception as e:
            print(f"  Could not upload resume: {e}")
