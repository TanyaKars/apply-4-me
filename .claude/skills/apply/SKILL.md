---
name: apply
description: Navigation instructions for the AI-driven job application filler. Edit to control how Claude navigates unknown application pages, account walls, login prompts, and multi-step forms.
argument-hint: "[what to update]"
---

# Application Navigation Instructions

> apply4me reads this file at every step of the browser automation.
> Edit it in plain English — Claude follows these instructions to navigate unknown pages.

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

---

## Already Applied

- If the page says "You have already applied" or similar → stop with reason "already applied"

---

## List of Open Positions

- If the page shows a list of jobs (not the form for the specific job) → find the job title that best matches the one being applied to and click it

---

## Diversity / EEO / Voluntary Surveys

- These are usually optional — answer "Prefer not to say" / "Decline to self-identify" for each question
- Do not leave required diversity fields blank — pick the most neutral option

---

## CAPTCHA

- If a CAPTCHA appears → stop with reason "captcha detected"

---

## Confirmation / Thank You Page

- If you see "Thank you for applying", "Application submitted", "We received your application" or similar → you are done
