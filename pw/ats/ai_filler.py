"""AI-guided form filler — LLM-driven navigation + form filling.

Navigation decisions (what button to click, how to handle account walls, etc.)
are made by Claude using NAVIGATION.md as its instruction set.
Form field filling uses the candidate's resume data from SKILL.md.
"""
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


def _read_nav_skill() -> str:
    """Load navigation instructions from .claude/skills/apply/SKILL.md."""
    nav_path = Path(__file__).parents[2] / ".claude" / "skills" / "apply" / "SKILL.md"
    if nav_path.exists():
        return nav_path.read_text()
    return ""


# JS: extract visible, fillable form fields
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

    document.querySelectorAll('textarea').forEach(el => {
        if (!isVisible(el)) return;
        fields.push({
            idx: idx++, type: 'textarea',
            name: el.name || '', id: el.id || '',
            label: getLabel(el), value: el.value, required: el.required,
        });
    });

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


# JS: get page state for navigation decisions
_GET_PAGE_STATE_JS = """() => {
    const visibleText = document.body.innerText.substring(0, 3000).trim();

    const clickables = [];
    const seen = new Set();
    document.querySelectorAll(
        'button, a[href], [role="button"], input[type="submit"], input[type="button"]'
    ).forEach(el => {
        if (el.offsetParent === null || el.disabled) return;
        const text = (el.innerText || el.value || el.getAttribute('aria-label') || '')
            .trim().replace(/\\s+/g, ' ');
        if (!text || seen.has(text)) return;
        seen.add(text);
        clickables.push({
            tag: el.tagName.toLowerCase(),
            text: text.substring(0, 80),
            type: el.type || null,
        });
    });

    return { visibleText, clickables: clickables.slice(0, 40) };
}"""


class AIFillerAdapter(BaseATSAdapter):
    """General-purpose adapter that uses Claude to navigate and fill any application form."""

    def __init__(self, page: Page, resume_data: dict, pdf_path: str, jd_text: str = ""):
        super().__init__(page, resume_data, pdf_path)
        self.jd_text = jd_text
        self._nav_skill = _read_nav_skill()
        self.stop_reason: str = ""

    async def _click_linkedin_apply(self) -> bool:
        """If on a LinkedIn job page, click Apply and switch to the new tab."""
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
        wait = "domcontentloaded" if "linkedin.com" in job_url else "networkidle"
        await self.page.goto(job_url, wait_until=wait, timeout=30_000)
        await self.page.wait_for_timeout(2000)

        # LinkedIn: click Apply to reach the external ATS form
        if "linkedin.com/jobs/view/" in self.page.url:
            switched = False
            try:
                switched = await self._click_linkedin_apply()
            except Exception as e:
                print(f"  LinkedIn apply click failed: {e}")

            if not switched:
                await self.page.wait_for_timeout(1000)
                dialog = self.page.locator("div[role='dialog']")
                if await dialog.count() > 0:
                    print("  Easy Apply modal detected — handing off to Easy Apply adapter.")
                    from pw.ats.easy_apply import LinkedInEasyApplyAdapter
                    ea = LinkedInEasyApplyAdapter(self.page, self.resume, self.pdf_path)
                    return await ea._fill_modal()

        for step in range(20):
            print(f"\n--- AI Filler: step {step + 1} | url: {self.page.url} ---")

            # LinkedIn auth wall — handle internally, not via Claude
            if "linkedin.com" in self.page.url and any(
                p in self.page.url for p in ("oauth", "login", "authwall", "uas/login")
            ):
                print("  LinkedIn auth wall — warming up session...")
                try:
                    await self.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=15_000)
                    if "feed" in self.page.url:
                        await self.page.goto(job_url, wait_until="domcontentloaded", timeout=30_000)
                        await self.page.wait_for_timeout(1000)
                        continue
                except Exception:
                    pass
                print("\n  ⚠️  LinkedIn session expired. Go to Settings and re-authenticate.\n")
                return False

            # Get page state and form fields
            page_state = await self.page.evaluate(_GET_PAGE_STATE_JS)
            fields = await self.page.evaluate(_EXTRACT_FIELDS_JS)
            fillable = [f for f in fields if f.get("type") != "file"]
            has_form = bool(fillable) and not self._looks_like_utility_form(fillable)

            # Ask Claude what to do next
            decision = await self._decide_action(page_state, has_form)
            action = decision.get("action", "")
            reason = decision.get("reason", "")
            print(f"  Claude → {action}" + (f": {reason}" if reason else ""))

            if action == "done":
                return True

            if action == "stop":
                self.stop_reason = reason
                print(f"  Cannot proceed: {reason}")
                return False

            if action == "fill_form":
                print(f"  Filling {len(fillable)} fields...")
                instructions = await self._ask_claude_fill(fillable)
                await self._apply_instructions(instructions, fillable)
                await self._upload_resume_if_needed()
                continue

            if action == "submit":
                await self._upload_resume_if_needed()
                try:
                    submit = self.page.locator(
                        "button[type='submit'], input[type='submit'], "
                        "button:has-text('Submit'), button:has-text('Send application'), "
                        "button:has-text('Send Application')"
                    ).first
                    if await submit.is_visible(timeout=2000):
                        print("  Submitting — pausing for review.")
                        await self.pause_before_submit()
                        await submit.click()
                        await self.page.wait_for_timeout(3000)
                        return True
                except Exception:
                    pass
                print("  Submit button not found.")
                inp = input("  Press ENTER to retry or 'q' to quit: ").strip().lower()
                if inp == "q":
                    return False
                continue

            if action == "click":
                text = decision.get("text", "")
                print(f"  Clicking: {text!r}")
                clicked = await self._click_by_text(text)
                if not clicked:
                    print(f"  Element not found: {text!r}")
                    inp = input("  [c] continue / [q] quit: ").strip().lower()
                    if inp == "q":
                        return False
                await self.page.wait_for_timeout(2000)
                continue

            # Unexpected response — let user decide
            print(f"  Unexpected action {action!r}.")
            inp = input("  [c] continue / [q] quit: ").strip().lower()
            if inp == "q":
                return False
            await self.page.wait_for_timeout(2000)

        return False

    async def _decide_action(self, page_state: dict, has_form: bool) -> dict:
        """Ask Claude what single action to take on the current page."""
        try:
            import anthropic
            api_key = _get_api_key()
        except Exception as e:
            print(f"  Claude unavailable: {e}")
            return {"action": "stop", "reason": "claude unavailable"}

        client = anthropic.Anthropic(api_key=api_key)
        title = await self.page.title()

        prompt = f"""You are controlling a browser to submit a job application.

NAVIGATION INSTRUCTIONS:
{self._nav_skill}

CURRENT PAGE:
URL: {self.page.url}
Title: {title}
Has fillable application form fields: {has_form}

Visible page text (first 3000 chars):
{page_state['visibleText']}

Visible buttons / links:
{json.dumps(page_state['clickables'], indent=2)}

What is the single best next action? Return JSON only:
- {{"action": "fill_form"}} — the application form is visible and ready to fill
- {{"action": "click", "text": "exact text of the button or link to click"}}
- {{"action": "submit"}} — all fields are filled, ready to submit
- {{"action": "done"}} — application confirmed as submitted
- {{"action": "stop", "reason": "brief reason"}} — cannot proceed"""

        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}]
        )
        text = message.content[0].text.strip()
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:-1])
        try:
            return json.loads(text)
        except Exception:
            return {"action": "stop", "reason": f"could not parse Claude response: {text}"}

    async def _click_by_text(self, text: str) -> bool:
        """Find and click an element by its visible text, following new tabs."""
        for role in ("button", "link"):
            el = self.page.get_by_role(role, name=text).first
            try:
                if await el.is_visible(timeout=500):
                    url_before = self.page.url
                    try:
                        async with self.page.context.expect_page(timeout=2000) as new_page_info:
                            await el.click()
                        new_page = await new_page_info.value
                        await new_page.wait_for_load_state("domcontentloaded", timeout=20_000)
                        self.page = new_page
                        print(f"  Opened new tab: {self.page.url}")
                    except Exception:
                        await self.page.wait_for_timeout(1500)
                        if self.page.url != url_before:
                            await self.page.wait_for_load_state("networkidle", timeout=15_000)
                    return True
            except Exception:
                pass
        # Fallback: any visible element containing the text
        el = self.page.get_by_text(text, exact=False).first
        try:
            if await el.is_visible(timeout=500):
                await el.click()
                await self.page.wait_for_timeout(1500)
                return True
        except Exception:
            pass
        return False

    def _looks_like_utility_form(self, fields: list[dict]) -> bool:
        """Return True when visible fields are a widget (email-job/save/share), not the real form."""
        labels = " ".join(f.get("label", "").lower() for f in fields)
        strong = {"recipient", "save job", "save this job", "email this job", "email this position"}
        if any(kw in labels for kw in strong):
            return True
        if len(fields) > 5:
            return False
        weak = {"email this", "share this", "notify me", "job alert"}
        return any(kw in labels for kw in weak)

    async def _ask_claude_fill(self, fields: list[dict]) -> list[dict]:
        """Send form fields to Claude, get back fill instructions."""
        try:
            import anthropic
            api_key = _get_api_key()
        except Exception as e:
            print(f"  Claude unavailable: {e}")
            return []

        client = anthropic.Anthropic(api_key=api_key)

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
            text = "\n".join(text.split("\n")[1:-1])
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
                    radio = self.page.locator(
                        f"input[type='radio'][name='{name}'][value='{value}']"
                    ).first
                    if not await radio.is_visible(timeout=1000):
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
