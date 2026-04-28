# appy4me

**Local, open-source job application automation.** Discovers jobs on LinkedIn using your own session, tailors your resume per JD with Claude AI, and applies directly on company ATS pages (Greenhouse, Lever, Ashby) — bypassing Easy Apply.

> Your data stays local. No cloud. No subscriptions.

---

## Features

- **LinkedIn job scraping** — uses your real session cookies to find non-Easy-Apply jobs
- **AI resume tailoring** — Claude rewrites your summary and bullet points to match each JD
- **3 PDF templates** — Modern, Classic, Minimal (with optional photo)
- **ATS automation** — fills Greenhouse / Lever / Ashby forms with Playwright, pauses before submit
- **Side-by-side diff** — see exactly what Claude changed before applying
- **Cover letter generation** — optional per-job cover letters

---

## Stack

| Layer | Tech |
|-------|------|
| Frontend | Next.js 14 + TypeScript + Tailwind + shadcn/ui |
| Backend | FastAPI + Python 3.11 + SQLModel + SQLite |
| AI | Claude Sonnet 4.6 (Anthropic API) |
| PDF | Jinja2 + WeasyPrint |
| Automation | Playwright (Python) |
| Package mgr | uv |

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 20+
- [uv](https://docs.astral.sh/uv/) — `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Anthropic API key — [console.anthropic.com](https://console.anthropic.com)

### Install

```bash
git clone https://github.com/yourname/appy4me
cd appy4me
node scripts/setup.js
```

### Configure

Edit `~/.appy4me/config.json`:
```json
{
  "anthropic_api_key": "sk-ant-...",
  "search": {
    "keywords": ["QA Engineer", "SDET"],
    "location": "Remote",
    "date_posted": "past_week",
    "blacklist_companies": []
  }
}
```

### Run

```bash
npm run dev
```

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000/docs

---

## Usage Guide

### 1. Set Up LinkedIn Session (one-time)
Settings → **Set Up Session** → Log in to LinkedIn in the browser window → Close it.
Cookies are saved to `~/.appy4me/linkedin_cookies.json`.

### 2. Build Your Resume
Resume → Fill in your experience, skills, education → **Save** → **Preview PDF**

### 3. Discover Jobs
Dashboard → **Scrape Jobs** → New jobs appear in the feed
- Click **Approve** to queue a job for tailoring
- Click **Skip** to hide it

### 4. Tailor & Apply
Click an approved job → **Tailor Resume** → Review the diff → **Apply Now**
Playwright fills the ATS form and pauses before submit. You confirm in the terminal.

---

## Project Structure

```
appy4me/
├── frontend/          # Next.js 14 UI
├── backend/           # FastAPI + services
│   ├── app/
│   │   ├── api/       # Jobs, Resume, Automation endpoints
│   │   ├── services/  # Claude, PDF generation
│   │   └── models.py  # SQLModel DB models
│   └── templates/     # Jinja2 HTML resume templates
└── automation/        # Playwright scripts
    ├── auth/          # LinkedIn session
    ├── scrapers/      # LinkedIn job scraper
    └── ats/           # Greenhouse / Lever / Ashby adapters
```

---

## Docker (optional)

```bash
cp .env.example .env
# Add ANTHROPIC_API_KEY to .env
docker-compose up
```

---

## Contributing

PRs welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

MIT
