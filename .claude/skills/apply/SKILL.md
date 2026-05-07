---
name: apply
description: Instructions for the AI-driven job application filler — navigation AND form filling. Edit to control how Claude navigates pages and fills form fields.
argument-hint: "[what to update]"
---

# Application Instructions

> apply4me reads this file at every step of the browser automation — for both navigation decisions and form filling.
> Edit it in plain English — Claude follows these instructions exactly.

---

## Goal

Your job is to reach the job application form and submit it on behalf of the candidate.
At each step you see the current page state and decide what single action to take next.

---

## General Flow

1. If the page is a job description / landing page → find and click the Apply button
2. If the page has a form with application fields → fill it out
3. If there is a Next / Continue button → click it to advance to the next step
4. If there is a Submit / Send Application / SUBMIT APPLICATION button → return `submit` action (NOT `click`)
5. If the page confirms the application was received → you are done

---

## Apply Buttons

- Prefer "Apply Now" or "Apply" over other variants
- If there are multiple Apply buttons, click the most prominent / first one
- Avoid buttons labeled "Easy Apply" on external company sites (those are LinkedIn-specific)
- After clicking Apply, wait — a new browser tab may open with the actual form. Do NOT click Apply again.
- If clicking Apply does NOT change the URL and no new tab opens, the form may be revealed below — return `fill_form` on the next step

---

## Account Creation / Sign-Up Walls

- If the page asks the candidate to create an account or sign up before applying:
  - First look for a "Continue as guest", "Apply without account", or "Skip" option
  - If no guest option exists → stop with reason "account creation required"
    (the job will be moved to Pending automatically so the user can apply manually)

---

## Login Walls (non-LinkedIn)

- If the page requires logging into a third-party service (Google, Microsoft, etc.) → stop with reason "login required"
- LinkedIn login is handled separately — do not stop for LinkedIn
- Builtin login is handled separately — do not stop for built-in login walls

---

## Already Applied

- If the page says "You have already applied" or similar → stop with reason "already applied" and move job to the "Applied" category

---

## List of Open Positions

- If the page shows a list of jobs (not the form for the specific job) → find the job title that best matches the one being applied to and click it

---

## CAPTCHA

- If a CAPTCHA appears → stop with reason "captcha detected"

---

## Confirmation / Thank You Page

- If you see "Thank you for applying", "Application submitted", "We received your application" or similar → you are done

---

## Form Filling Rules

When asked to fill a form, use the candidate data provided. Follow these rules:

### Identity fields
- Name, full name → candidate's full name
- Email → candidate's email
- Phone → candidate's phone

### URL fields
- Field labeled "GitHub" or mentioning "github" → use GitHub URL
- Field labeled "LinkedIn" or mentioning "linkedin" → use LinkedIn URL
- Field labeled "Portfolio" → use portfolio URL if set, otherwise other website
- Field labeled "Website", "Personal website", "Other website" → use other website URL
- Field combining multiple like "Website, Portfolio, Github..." → prefer GitHub URL

### Work authorization
- Use the candidate's answers from the `Work Authorization & Salary` section of their resume data

### Salary
- Use the candidate's salary expectation from their resume data (if empty → leave the field blank)

### Experience
- "Years of experience" → calculate from resume dates (working since 2018, ~7+ years)

### Cover letter / open-ended text
- "Why this company" / "why do you want to work here" / "tell us about yourself" → write 2–3 sentences from the candidate's summary tailored to the role

### Diversity / EEO
- Use the candidate's actual answers from CANDIDATE DIVERSITY / EEO ANSWERS
- If a field has no answer set → use "Prefer not to say" / "Decline to self-identify"
- Never leave required diversity fields blank — pick the most neutral option available

### Selects and radio buttons
- Return the exact option text that best matches the correct answer
- If no option fits, return ""

### Checkboxes
- Return "true" to check, "false" to leave unchecked
- "I agree to terms" / consent checkboxes → "true"

### Resume upload
- Handled automatically — the tailored PDF is uploaded to any resume file input after form filling
- You do not need to interact with file upload fields

### Cover letter
- File upload: detected and uploaded automatically — you do not need to interact with it
- Text field ("Why this company", "why do you want to work here", "tell us about yourself", "cover letter") → write 2–3 sentences from the candidate's summary tailored to the role

### Unknown fields
- If you cannot determine the correct answer from candidate data → return ""
