---
name: resume
description: Manage your resume data and tailoring preferences. Use when updating personal info, experience, skills, education, or how Claude should tailor your resume for jobs.
argument-hint: "[what to update]"
---

<!-- Copy this instructions into SKILL.md, replacing all placeholder values with your real information. SKILL.md file is the source of truth for your resume — Claude reads it every time it tailors your resume for a job. -->

# Resume Data & Tailoring Preferences

> This is your resume source of truth. Edit it directly in VS Code.
> apply4me reads this file every time it tailors your resume for a job.

---

## Personal

- **Name:** Jane Doe
- **Email:** jane@example.com
- **Phone:** +1 (555) 000-0000
- **Location:** San Francisco, CA (open to remote)
- **LinkedIn:** linkedin.com/in/janedoe
- **GitHub:** github.com/janedoe

---

## Tailoring Preferences

<!-- ✅ SAFE TO EDIT — these are your personal writing style preferences -->

- Write in first person, active voice, past tense for past roles
- Maximum 4 bullet points per past roles — quality over quantity
- Lead each bullet with a strong action verb (Built, Led, Reduced, Improved...)
- Quantify impact wherever possible (e.g. "reduced CI time by 40%")
- Mirror keywords from the job description naturally — don't stuff
- Keep summary to 2–3 sentences, tailored to the specific role
- Do not invent experience or skills I don't have
- Prioritize the most relevant experience for the target role
- Do not use red-flag words like 'knowledge', 'ability', 'familiarity', 'assist', 'support', 'helped', 'contributed to', 'experienced' — I want my resume to sound confident and impactful, not wishy-washy or junior

<!-- 🚫 DO NOT TOUCH — ATS scanner rules live in ATS-RULES.md in this same folder.
     They ensure your resume passes automated keyword filters used by Greenhouse, Lever,
     Workday, and Ashby before a human ever sees it. Claude loads that file automatically.
     You never need to reference or copy anything from it here. -->
---

## Summary

<!-- You can leave this section empty. Claude will generate the summary from the experience data and the JD context -->

---

## Experience

<!-- Write raw facts, not polished bullets.                                                                     
  Claude's job is to pick, reframe, and tailor. Your job is to give it enough material to work with. More raw detail = better output. -->
### Senior Software Engineer — Acme Corp (2021 – Present)
<!-- Bad: 
- Wrote automated tests
- Worked with the team-->

### Software Engineer — Beta Inc (2018 – 2021)
<!-- Good:
Built Cypress e2e framework from scratch, ~400 tests covering checkout, auth, search.
  Reduced flaky test rate from 30% to under 5% by isolating network calls with cy.intercept.
  Integrated into GitHub Actions — runs on every PR, catches regressions before merge.
  Team was 5 QAs, I owned the automation layer, others did manual and exploratory.
  Also did API testing with Postman and Supertest — ~80% coverage on critical endpoints.
  Stack: React frontend, Node/Express backend, PostgreSQL.
  Had a big win migrating from Selenium (slow, brittle) to Cypress — cut suite time by 60%.

  ---
  Specific things to include per role:

  - What you actually built or owned (not just "worked on")
  - Numbers wherever you remember them — time saved, coverage %, team size, scale
  - Tools and stack — Claude will mirror the JD's terminology if it knows what you used
  - What changed because of your work (before/after)
  - Any context that explains scope — team size, company stage, product type

  ---
  Don't pre-filter. If you're not sure something is relevant, include it anyway. Claude decides what to surface based on the JD. A detail that
   seems minor for one role might be the headline for another.
 -->

---

## Skills
<!-- Don't curate for a specific role. Claude will reorder and pick what's relevant based on the JD.  

Specific suggestions:

  - Group by category — easier for Claude to reason about what cluster matters for a given JD
  - Be honest about depth — "some Go", "basic SQL", "awareness" tells Claude not to lead with those. It won't oversell you.
  - Include tools you've used even briefly — if it's on a JD and you've touched it, Claude can mention it. If it's not in SKILL.md, Claude
  won't invent it.
  - Don't include soft skills — "attention to detail", "team player" etc. Claude will weave those into bullets naturally if needed. A
  standalone skills list of soft skills wastes space.
  - Put down notes in () after skills and a number of years of experience. The last 2 notes for Claude will scan this data for the resume and auto apply. 
-->
**Languages:** Python (can read), TypeScript - 5, some Go, SQL (no complex queries) - 5
**Frameworks:** FastAPI, Next.js, React, Express
**Infrastructure:** AWS (ECS, RDS, S3, Lambda), Docker, Kubernetes, Terraform
**Tools:** PostgreSQL, Redis, Kafka, GitHub Actions, Datadog, PagerDuty
**Practices:** TDD, CI/CD, agile, code review, system design

---

## Education

**B.S. Computer Science** — State University, 2017

---

## Certifications

- AWS Certified Solutions Architect – Associate (2022)
- Google Cloud Professional Data Engineer (2023)

---

## Notes for Claude

<!-- Put here anything you'd tell a human recruiter off the record that you don't want on the actual document. Claude reads it, uses it to make decisions, and never outputs it. -->

- I prefer concise, direct language — no corporate fluff
- I've grown into leadership at Acme but I'm also happy as a senior IC
- I'm strongest in backend and infrastructure; frontend is secondary
- I'm not interested in roles that are purely management with no hands-on work
- Target companies: mid-size startups and scale-ups, not FAANG
- <enter US work authorization here>
- Target salary: <enter salary range here>. Answer "Yes" to any range that includes or exceeds $140K.
- In Skills section, if the skill does have no note in (), assume I'm proficient and you can use it in tailoring without hesitation. If there's a note, follow it carefully.
- The number following the skill is the num of years I have experience (real, not learning) with it, but feel free to use any skill in tailoring as long as you follow the notes in parentheses. if it says "familiar", you can use it but don't highlight it as a strength. if it says "basic", you can only use it if the job description explicitly mentions that level of experience. If there is no number after the skill, you can assume I don't have working experience with the tool, I have only explored it, or learned a bit.
