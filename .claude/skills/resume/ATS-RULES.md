# ATS Scanner Rules — Do Not Modify

> These rules ensure the generated resume passes ATS (Applicant Tracking System) keyword scanners
> used by most companies for initial filtering. Changing them may cause your resume to be rejected
> before a human ever reads it.
>
> apply4me automatically applies these rules on every resume generation. You do not need to
> think about them — just keep this file as-is.

---

## Keyword Matching

- Use the **exact phrasing** from the job description for tools, technologies, and methodologies
  - JD says "Selenium WebDriver" → use "Selenium WebDriver", not "Selenium" or "Webdriver"
  - JD says "CI/CD" → use "CI/CD", not "continuous integration"
  - JD says "REST APIs" → use "REST APIs", not "RESTful" or "web services"
- Expand acronyms at least once per document when the JD uses both forms
  - e.g. "Test-Driven Development (TDD)"
- Do not use synonyms when the JD has a specific term — ATS matches exact strings

## Structure Rules

- If the candidate held multiple roles at the same company, output a SEPARATE experience entry for each role — same company string, different title and dates. Never merge roles into one title. The PDF renderer will group them visually under one company header automatically.
- The "title" field: job title only — no dates embedded
- The "dates" field: date range only (e.g. "May 2019 – November 2021")
- The "company" field must contain the FULL company string exactly as written in SKILL.md, including location and employment type (e.g. "PASV | United States (Part-time)")

## Format Rules

- Use standard section names: Summary, Experience, Skills, Education, Certifications
  - Do NOT rename to "What I've Done", "About Me", "Tech Stack", etc.
- Use plain bullet points (hyphen or dot) — no icons, tables, or columns in the text layer
- No images, logos, charts, or infographics — ATS parsers skip them entirely
- Put contact info (name, email, phone, location, LinkedIn) in the document body, NOT in headers or footers — ATS often ignores header/footer regions
- Spell out dates in "Month Year – Month Year" format — avoid abbreviations
- Job titles must match or closely mirror common industry titles
  - Do NOT use internal/creative titles like "Quality Champion" — use "QA Engineer"

## Skills Section

- List skills as a flat, comma-separated or line-separated list — ATS parsers handle this best
- Include both the spelled-out name and acronym when both are common:
  - "Continuous Integration / Continuous Deployment (CI/CD)"
  - "Application Programming Interface (API) testing"
- Do not group skills under decorative headers that ATS can't parse (e.g. "🛠 Tools")

## Content Rules

- Never put critical keywords only in headers or graphics — ATS often ignores them
- Repeat the most important keywords from the JD naturally across Summary, Experience, and Skills
- Do not use the word "Resume" or "CV" as a section header — ATS may misparse it

---

*This file is read by Claude on every resume generation alongside SKILL.md.*
*Source: standard ATS optimization practices (Greenhouse, Lever, Workday, Ashby).*
