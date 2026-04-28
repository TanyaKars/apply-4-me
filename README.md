# apply4me

**Automate your job search — without giving your data to anyone.**

apply4me finds jobs on LinkedIn, rewrites your resume to match each job description using AI, and fills out application forms for you. Everything runs on your own computer. No cloud. No subscriptions. No one sees your resume but you.

> Built for QA engineers and anyone tired of copy-pasting the same resume into 50 job applications.

---

## Quick start with Docker (recommended)

If you have [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed, you don't need Node.js or Python.

```
git clone https://github.com/TanyaKars/apply4me
cd apply4me
./start.sh
```

`start.sh` creates a `.env` file on first run — open it, add your Anthropic API key, then run `./start.sh` again.

Once running:
- App → **http://localhost:3000**
- Browser view (for LinkedIn login & application review) → **http://localhost:6080/vnc.html**

To stop: `Ctrl + C`, then `docker compose down`.

---

## What it does

1. **Finds jobs** — searches LinkedIn using your own account and pulls job listings matching your keywords
2. **Tailors your resume** — sends the job description + your background to Claude AI, which rewrites your bullet points and summary to match the role
3. **Generates a PDF** — produces a clean, formatted resume PDF ready to submit
4. **Fills application forms** — opens the company's application page and types in your info automatically, then pauses so you can review before hitting Submit

---

## Before you start (manual install)

You'll need to install a few free tools. This takes about 15–20 minutes and you only do it once.

---

### Step 1 — Install Node.js

Node.js is a tool that runs JavaScript programs (apply4me uses it for the visual interface).

1. Go to **https://nodejs.org**
2. Download the **LTS** version (the one labeled "Recommended for most users")
3. Run the installer and click through — all defaults are fine

**Check it worked:** Open Terminal (on Mac: press `Cmd + Space`, type "Terminal", press Enter) and type:
```
node --version
```
You should see something like `v20.11.0`. Any number starting with 18 or higher is fine.

---

### Step 2 — Install Python

Python is a programming language that the AI and automation parts of apply4me are written in.

1. Go to **https://www.python.org/downloads**
2. Download the latest version (the big yellow button)
3. Run the installer
   - **Important on Windows:** check the box that says **"Add Python to PATH"** before clicking Install

**Check it worked:** In Terminal, type:
```
python3 --version
```
You should see something like `Python 3.12.0`.

---

### Step 3 — Install uv

`uv` is a tool that manages Python packages (think of it like an App Store for Python tools).

**On Mac or Linux** — paste this into Terminal and press Enter:
```
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**On Windows** — paste this into PowerShell and press Enter:
```
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Then close Terminal and open it again (this makes the new tool available).

**Check it worked:**
```
uv --version
```

---

### Step 4 — Get an Anthropic API key

This is what lets apply4me use Claude AI to rewrite your resume. You need a paid Anthropic account (separate from Claude.ai — that's the chat product, this is the API).

1. Go to **https://console.anthropic.com**
2. Sign up or log in
3. Go to **API Keys** in the left sidebar
4. Click **Create Key**, give it a name like "apply4me", copy the key

> **Cost:** Resume tailoring uses roughly $0.01–0.03 per job. 100 applications ≈ $1–3 total.

---

## Installation

Open Terminal, then run these commands one by one:

```
git clone https://github.com/TanyaKars/apply4me
```
```
cd apply4me
```
```
cp .env.example .env
```

Now open the `.env` file in any text editor (TextEdit on Mac, Notepad on Windows) and replace `sk-ant-your-key-here` with your real API key from Step 4.

Then run the setup script:
```
node scripts/setup.js
```

This installs all dependencies automatically. It takes a few minutes.

---

## Running the app

Every time you want to use apply4me, open Terminal, go to the apply4me folder, and run:

```
npm run dev
```

Then open your browser and go to **http://localhost:3000**

To stop it, go back to Terminal and press `Ctrl + C`.

---

## First-time setup (in the app)

### 1. Fill in your resume

Open the file `.claude/skills/resume/SKILL.md` in any text editor — it's in the apply4me folder you downloaded. Replace the example content with your real information: name, contact details, work history, skills.

The more detail you put here, the better Claude can tailor your resume for each job. You can write naturally — no special format required.

### 2. Connect your LinkedIn account

In the app, go to **Settings** → click **Set Up Session**.

A browser window will open. Log in to LinkedIn normally. Once you're on the LinkedIn home page, close the browser window. apply4me saves your login so it can search jobs on your behalf.

> Your LinkedIn cookies are saved only to your computer at `~/.apply4me/linkedin_cookies.json`.

### 3. Set your job search preferences

In **Settings**, fill in:
- **Job Keywords** — what roles you're looking for (e.g. `QA Engineer, SDET, Test Automation`)
- **Location** — `Remote`, `New York`, etc.
- **Company Blacklist** — companies you don't want to appear (comma-separated)

Click **Save Settings**.

---

## Using the app

### Finding jobs

On the Dashboard, click **Scrape Jobs**. apply4me opens LinkedIn in the background and collects matching job listings. New jobs appear in the feed within a minute or two.

For each job you can:
- **Approve** — adds it to your queue for resume tailoring
- **Skip** — hides it from the feed

### Tailoring your resume

Click on any approved job to open it. Then click **Tailor Resume**.

Claude reads the job description and your SKILL.md, then rewrites your resume bullet points and summary to best match this specific role. A tailored PDF is saved automatically.

You can also click **Generate Cover Letter** for a job-specific cover letter.

### Applying

Once a job has a tailored resume, the **Apply Now** button appears. Click it — apply4me opens the company's application form and fills it in using your details and the tailored PDF.

It pauses before submitting so you can review everything. You confirm when you're ready.

---

## Your data

Everything stays on your machine:

| What | Where |
|------|-------|
| Resume data | `apply4me/.claude/skills/resume/SKILL.md` |
| Generated PDFs | `~/.apply4me/resumes/` |
| LinkedIn cookies | `~/.apply4me/linkedin_cookies.json` |
| App database | `~/.apply4me/apply4me.db` |
| API key | `apply4me/.env` |

---

## Troubleshooting

**The app won't start**
Make sure you ran `node scripts/setup.js` first. If it still fails, try closing Terminal and opening it again.

**"API key not found" error**
Check that your `.env` file has your real key (not the placeholder text) and that you saved the file.

**No jobs showing up after scraping**
Your LinkedIn session may have expired. Go to Settings → **Re-authenticate** and log in again.

**PDF won't generate**
Make sure your SKILL.md has at least your name, one job, and some skills filled in.

---

## Contributing

PRs welcome — especially new ATS adapters (Workday, iCIMS, Taleo) and resume template designs.

---

## License

MIT
