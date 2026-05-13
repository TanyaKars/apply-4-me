# 🤖 apply4me

[![License: PolyForm Noncommercial 1.0.0](https://img.shields.io/badge/License-PolyForm_NC_1.0.0-blue)](https://polyformproject.org/licenses/noncommercial/1.0.0)

Automate your job search — without giving your data to anyone.

apply4me finds jobs on LinkedIn and Builtin, scores them against your background, tailors your resume for each role using Claude AI, and fills out application forms automatically. Everything runs on your own computer.

Requires an [Anthropic API key](https://console.anthropic.com) — you pay per use (~$1–3 per 100 applications).

---

## What it actually does

1. Scrapes LinkedIn and Builtin for jobs matching your keywords and filters
2. Scores each job against your background with Claude AI (0–100 match score)
3. Rewrites your resume bullets and summary to match the specific role
4. Generates a tailored resume PDF — and optionally a cover letter
5. Opens the application form and fills it in automatically, then pauses for your review

Supported ATS: LinkedIn Easy Apply, Greenhouse, Lever, Ashby, Workday. For everything else, the AI form filler reads the page and figures it out.

---

## Quick start with Docker

The easiest way. You only need [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```
git clone https://github.com/TanyaKars/apply4me
cd apply4me
./start.sh
```

On first run, `start.sh` creates a `.env` file. Add your Anthropic API key and run `./start.sh` again.

- App → **http://localhost:3000**
- Browser view (LinkedIn login, form review) → **http://localhost:6080/vnc.html**

---

## Manual install

You'll need Node.js 18+, Python 3.10+, and `uv`.

**Install uv:**

```bash
# Mac/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

**Then:**

```bash
git clone https://github.com/TanyaKars/apply4me
cd apply4me
cp .env.example .env   # add your Anthropic API key
node scripts/setup.js  # installs everything, takes a few minutes
npm run dev            # starts the app at http://localhost:3000
```

---

## First-time setup

**1. Fill in your resume**

Open `apply4me/.claude/skills/resume/SKILL.md` and replace the example with your real info — name, contact details, work history, skills, and what kind of role you're targeting. More detail = better tailoring.

If you already have a resume as PDF or DOCX, go to the **Resume** page in the app and import it — Claude will convert it automatically.

**2. Connect your accounts**

Go to **Settings** and click **Set Up LinkedIn Session**. A browser opens — log in to LinkedIn normally, then close it. apply4me saves the session so it can search on your behalf.

Builtin.com is optional — same flow under **Set Up Builtin Session**.

**3. Set your search preferences**

Still in Settings: keywords, country, work type (remote/hybrid/on-site), date range, Easy Apply toggle, company blacklist. Save and you're ready.

---

## Using the app

**Scraping** — click **Scrape Jobs** on the dashboard. Jobs appear within a minute or two, each pre-scored. You can also add jobs manually by pasting a URL or dropping in a job description for sites that block scraping.

**Reviewing** — filter by match score or status. Approve what looks good, skip the rest. Click the `%` button to re-score any job on demand.

**Tailoring** — open an approved job, click **Tailor Resume**. Claude rewrites your resume for that role. Click **Generate Cover Letter** if you need one too.

**Applying** — click **Apply Now**. apply4me opens the form, fills it in, and pauses for your review before submitting.

---

## Your data stays local

| What | Where |
|------|-------|
| Resume data | `apply4me/.claude/skills/resume/SKILL.md` |
| Generated PDFs | `~/.apply4me/resumes/` |
| LinkedIn session | `~/.apply4me/linkedin_cookies.json` |
| Builtin session | `~/.apply4me/builtin_storage_state.json` |
| App database | `~/.apply4me/apply4me.db` |
| API key | `apply4me/.env` |

No cloud sync, no telemetry, no account required beyond the Anthropic API key.

---

## Troubleshooting

**App won't start** — run `node scripts/setup.js` first. If it still fails, close and reopen Terminal.

**"API key not found"** — check your `.env` has the real key, not the placeholder, and is saved.

**No jobs after scraping** — LinkedIn session expired. Go to Settings → re-authenticate.

**PDF won't generate** — make sure your SKILL.md has at least a name, one job, and some skills.

---

## Contributing

PRs welcome — especially new ATS adapters and resume templates.

---

## License

[PolyForm Noncommercial 1.0.0](LICENSE) — free to use, study, and modify for noncommercial purposes. Commercial use is not permitted.
