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

- Write in first person, active voice, past tense for past roles
- Maximum 4 bullet points per role — quality over quantity
- Lead each bullet with a strong action verb (Built, Led, Reduced, Improved...)
- Quantify impact wherever possible (e.g. "reduced CI time by 40%")
- Mirror keywords from the job description naturally — don't stuff
- Keep summary to 2–3 sentences, tailored to the specific role
- Do not invent experience or skills I don't have
- Prioritize the most relevant experience for the target role

---

## Summary

Experienced software engineer with 6+ years building scalable backend systems and developer tooling. Passionate about clean APIs, CI/CD automation, and cross-functional collaboration. Looking for senior IC or tech lead roles at product-focused companies.

---

## Experience

### Senior Software Engineer — Acme Corp (2021 – Present)
- Led migration of monolith to microservices, reducing p99 latency by 35%
- Built internal CI/CD platform used by 80+ engineers across 12 teams
- Mentored 3 junior engineers; introduced weekly architecture review sessions
- Owned on-call rotation for core payments service (99.95% uptime over 18 months)

### Software Engineer — Beta Inc (2018 – 2021)
- Designed and shipped REST API serving 2M+ daily active users
- Reduced test suite runtime from 45 min to 8 min via parallelization and caching
- Collaborated with product and design to ship 4 major features per quarter
- Introduced structured logging and alerting, cutting mean time to recovery from hours to minutes

### Junior Developer — Gamma Studio (2017 – 2018)
- Built internal dashboard for campaign analytics using React and Node.js
- Automated weekly reporting pipeline, saving ~6 hours of manual work per week

---

## Skills

**Languages:** Python, TypeScript, Go, SQL
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

- I prefer concise, direct language — no corporate fluff
- I've grown into leadership at Acme but I'm also happy as a senior IC
- I'm strongest in backend and infrastructure; frontend is secondary
- I'm not interested in roles that are purely management with no hands-on work
- Target companies: mid-size startups and scale-ups, not FAANG
