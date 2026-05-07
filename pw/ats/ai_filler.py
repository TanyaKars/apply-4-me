"""AI-guided form filler — LLM-driven navigation + form filling.

Navigation decisions (what button to click, how to handle account walls, etc.)
are made by Claude using NAVIGATION.md as its instruction set.
Form field filling uses the candidate's resume data from SKILL.md.
"""
import json
import os
import tempfile
from pathlib import Path

import httpx
from playwright.async_api import Page
from pw.ats.base import BaseATSAdapter

BACKEND_URL = "http://localhost:8000"


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


def _read_personal_urls() -> dict:
    """Extract Portfolio URL and Other website from resume SKILL.md."""
    resume_path = Path(__file__).parents[2] / ".claude" / "skills" / "resume" / "SKILL.md"
    result = {"portfolio_url": "", "other_website": ""}
    if not resume_path.exists():
        return result
    for line in resume_path.read_text().splitlines():
        if line.startswith("- **Portfolio URL:**"):
            result["portfolio_url"] = line.split(":", 1)[-1].strip().lstrip("*").strip()
        elif line.startswith("- **Other website:**"):
            result["other_website"] = line.split(":", 1)[-1].strip().lstrip("*").strip()
    return result


# JS: extract visible, fillable form fields
_EXTRACT_FIELDS_JS = """() => {
    const fields = [];
    let idx = 0;

    function getLabel(el) {
        // 1. label[for]
        if (el.id) {
            const lbl = document.querySelector('label[for="' + el.id + '"]');
            if (lbl) return lbl.innerText.trim();
        }
        // 2. aria-label / aria-labelledby
        const ariaLabel = el.getAttribute('aria-label');
        if (ariaLabel) return ariaLabel;
        const labelledBy = el.getAttribute('aria-labelledby');
        if (labelledBy) {
            const ref = document.getElementById(labelledBy);
            if (ref) return ref.innerText.trim();
        }
        // 3. placeholder
        if (el.placeholder) return el.placeholder;
        // 4. ancestor label element
        const parentLabel = el.closest('label');
        if (parentLabel) return parentLabel.innerText.trim();
        // 5. Walk up DOM up to 7 levels — check preceding siblings and label-like children
        let node = el;
        for (let depth = 0; depth < 7; depth++) {
            let prev = node.previousElementSibling;
            while (prev) {
                if (!prev.querySelector('input, textarea, select, button')) {
                    const text = (prev.innerText || '').trim();
                    if (text && text.length > 3 && text.length < 500) return text;
                }
                prev = prev.previousElementSibling;
            }
            const parent = node.parentElement;
            if (!parent || parent === document.body) break;
            const lblChild = parent.querySelector(
                'label, [class*="label"], [class*="Label"], [class*="question-text"], legend, dt'
            );
            if (lblChild && !lblChild.contains(el)) {
                const text = (lblChild.innerText || '').trim();
                if (text && text.length > 3 && text.length < 500) return text;
            }
            node = parent;
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

    def __init__(self, page: Page, resume_data: dict, pdf_path: str, jd_text: str = "", job_id: int | None = None):
        super().__init__(page, resume_data, pdf_path)
        self.jd_text = jd_text
        self.job_id = job_id
        self._nav_skill = _read_nav_skill()
        self._personal_urls = _read_personal_urls()
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
        wait = "domcontentloaded"
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

        last_action = ""
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
            decision = await self._decide_action(page_state, has_form, last_action)
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
                await self._handle_cover_letter()
                last_action = "fill_form"
                continue

            if action == "submit":
                await self._upload_resume_if_needed()
                try:
                    submit = self.page.locator(
                        "button[type='submit'], input[type='submit'], "
                        "button:has-text('Submit'), button:has-text('SUBMIT'), "
                        "button:has-text('Send application'), button:has-text('Send Application')"
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
                # Route submit-like clicks through the submit handler
                if any(kw in text.lower() for kw in ("submit", "send application")):
                    action = "submit"
                    continue
                print(f"  Clicking: {text!r}")
                clicked = await self._click_by_text(text)
                if not clicked:
                    print(f"  Element not found: {text!r}")
                    inp = input("  [c] continue / [q] quit: ").strip().lower()
                    if inp == "q":
                        return False
                await self.page.wait_for_timeout(2000)
                last_action = f"click:{text}"
                continue

            # Unexpected response — let user decide
            print(f"  Unexpected action {action!r}.")
            inp = input("  [c] continue / [q] quit: ").strip().lower()
            if inp == "q":
                return False
            await self.page.wait_for_timeout(2000)

        return False

    async def _decide_action(self, page_state: dict, has_form: bool, last_action: str = "") -> dict:
        """Ask Claude what single action to take on the current page."""
        try:
            import anthropic
            api_key = _get_api_key()
        except Exception as e:
            print(f"  Claude unavailable: {e}")
            return {"action": "stop", "reason": "claude unavailable"}

        client = anthropic.Anthropic(api_key=api_key)
        title = await self.page.title()

        last_action_note = ""
        if last_action == "fill_form":
            last_action_note = "\nLAST ACTION: The form fields were just filled. Do NOT return fill_form again — look for a Next, Continue, or Submit button to advance.\n"
        elif last_action.startswith("click:"):
            last_action_note = f"\nLAST ACTION: Clicked '{last_action[6:]}'. The page may have updated.\n"

        prompt = f"""You are controlling a browser to submit a job application.

NAVIGATION INSTRUCTIONS:
{self._nav_skill}
{last_action_note}
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
        # Try role-based match (case-insensitive via exact=False fallback)
        for role in ("button", "link"):
            for exact in (True, False):
                el = self.page.get_by_role(role, name=text, exact=exact).first
                try:
                    if not await el.is_visible(timeout=500):
                        continue
                    pages_before = list(self.page.context.pages)
                    url_before = self.page.url
                    await el.click()
                    # Poll up to 8 seconds for a new tab or URL change
                    for _ in range(16):
                        await self.page.wait_for_timeout(500)
                        pages_after = list(self.page.context.pages)
                        new_pages = [p for p in pages_after if p not in pages_before]
                        if new_pages:
                            new_page = new_pages[-1]
                            await new_page.wait_for_load_state("domcontentloaded", timeout=20_000)
                            self.page = new_page
                            print(f"  Opened new tab: {self.page.url}")
                            return True
                        if self.page.url != url_before:
                            await self.page.wait_for_load_state("domcontentloaded", timeout=10_000)
                            return True
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

        portfolio = self._personal_urls.get("portfolio_url", "")
        other_site = self._personal_urls.get("other_website", "")
        website_rule = ""
        if portfolio or other_site:
            urls = " / ".join(u for u in [portfolio, other_site] if u)
            website_rule = f"- Portfolio / personal website / other projects / side projects URL → use: {urls}\n"

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
{website_rule}- For select/radio: return the exact option text that best matches; if none fit, return ""
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
                    try:
                        currently = await el.is_checked()
                    except Exception:
                        currently = False
                    if want_checked != currently:
                        try:
                            # Try label click first (works for custom-styled checkboxes)
                            if fid:
                                lbl = self.page.locator(f'label[for="{fid}"]').first
                                if await lbl.count() > 0:
                                    await lbl.click()
                                else:
                                    await el.click(force=True)
                            else:
                                await el.click(force=True)
                        except Exception:
                            pass
                    print(f"  Checkbox {label!r}: {value}")

            except Exception as e:
                print(f"  Could not fill {label!r} (idx={idx}): {e}")

    async def _upload_resume_if_needed(self):
        """Upload resume PDF to the resume file input (not cover letter)."""
        if not self.pdf_path:
            return
        try:
            # Try resume-specific input first (Greenhouse, Lever, etc.)
            for sel in [
                "input[type='file'][name*='resume']",
                "input[type='file'][id*='resume']",
                "input[type='file'][accept*='pdf']:not([name*='cover'])",
            ]:
                inp = self.page.locator(sel).first
                if await inp.count() > 0:
                    await inp.set_input_files(self.pdf_path)
                    print(f"  Uploaded resume: {self.pdf_path}")
                    return
            # Fallback: first file input that isn't for cover letter
            inputs = self.page.locator("input[type='file']")
            count = await inputs.count()
            for i in range(count):
                inp = inputs.nth(i)
                name = await inp.get_attribute("name") or ""
                if "cover" not in name.lower():
                    await inp.set_input_files(self.pdf_path)
                    print(f"  Uploaded resume (fallback): {self.pdf_path}")
                    return
        except Exception as e:
            print(f"  Could not upload resume: {e}")

    async def _handle_cover_letter(self):
        """Detect cover letter upload field, generate CL via API, save to job, upload."""
        # Find cover letter file input
        cl_input = None
        for sel in [
            "input[type='file'][name*='cover_letter']",
            "input[type='file'][name*='cover']",
            "input[type='file'][id*='cover']",
        ]:
            inp = self.page.locator(sel).first
            if await inp.count() > 0:
                cl_input = inp
                break

        if cl_input is None:
            # Check if page text mentions cover letter near a file input
            has_cl_section = await self.page.evaluate("""() => {
                const text = document.body.innerText.toLowerCase();
                return text.includes('cover letter');
            }""")
            if not has_cl_section:
                return
            # Try the second file input (Greenhouse: resume=first, cover letter=second)
            inputs = self.page.locator("input[type='file']")
            if await inputs.count() >= 2:
                cl_input = inputs.nth(1)

        if cl_input is None or not self.job_id:
            return

        print("  Cover letter field detected — generating...")
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(f"{BACKEND_URL}/api/jobs/{self.job_id}/tailor-cover-letter")
                if not resp.is_success:
                    print(f"  Cover letter generation failed: {resp.status_code}")
                    return
                cover_letter_text = resp.json().get("cover_letter", "")

            if not cover_letter_text:
                return

            # Write to temp file and upload
            with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False, encoding="utf-8") as f:
                f.write(cover_letter_text)
                tmp_path = f.name

            await cl_input.set_input_files(tmp_path)
            os.unlink(tmp_path)
            print("  Cover letter generated and uploaded.")
        except Exception as e:
            print(f"  Cover letter handling failed: {e}")
