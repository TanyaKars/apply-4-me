import json
import os
import subprocess
import sys
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session
from app.db import get_session
from app.models import Job

# In Docker this is /app; locally falls back to the repo root
APP_ROOT = os.environ.get("APP_ROOT", str(Path(__file__).parents[3]))

router = APIRouter()

# In-process scrape state — tracks the active scrape subprocess
_scrape_proc: subprocess.Popen | None = None


class ScrapeRequest(BaseModel):
    keywords: list[str] = []
    location: str = "Remote"
    country: str = ""
    city: str = ""
    date_posted: str = "past_week"
    work_types: list[str] = []
    max_applicants: int | None = None


class ApplyRequest(BaseModel):
    job_id: int


@router.post("/setup-session")
async def setup_session():
    """Launch browser for LinkedIn session setup."""
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "pw.auth.session", "--setup"],
            cwd=APP_ROOT
        )
        return {"status": "launched", "pid": proc.pid, "message": "Browser opened. Log in to LinkedIn, then close the browser."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session-status")
async def session_status():
    import json
    import time
    cookie_file = Path.home() / ".apply4me" / "linkedin_cookies.json"
    if not cookie_file.exists():
        return {"has_session": False, "expired": False}
    try:
        cookies = json.loads(cookie_file.read_text())
        li_at = next((c for c in cookies if c.get("name") == "li_at"), None)
        if not li_at:
            return {"has_session": False, "expired": False}
        expires = li_at.get("expires", -1)
        if expires != -1 and expires < time.time():
            return {"has_session": False, "expired": True}
        return {"has_session": True, "expired": False}
    except Exception:
        return {"has_session": False, "expired": False}


@router.post("/scrape")
async def trigger_scrape(req: ScrapeRequest):
    """Trigger LinkedIn job scraper."""
    global _scrape_proc
    if _scrape_proc is not None and _scrape_proc.poll() is None:
        return {"status": "already_running", "pid": _scrape_proc.pid}
    try:
        config = json.dumps({
            "keywords": req.keywords,
            "location": req.location,
            "country": req.country,
            "city": req.city,
            "date_posted": req.date_posted,
            "work_types": req.work_types,
            "max_applicants": req.max_applicants,
        })
        _scrape_proc = subprocess.Popen(
            [sys.executable, "-m", "pw.scrapers.linkedin", "--config", config],
            cwd=APP_ROOT
        )
        return {"status": "started", "pid": _scrape_proc.pid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scrape-status")
async def scrape_status():
    """Returns whether a scrape subprocess is currently running."""
    global _scrape_proc
    if _scrape_proc is None:
        return {"running": False}
    code = _scrape_proc.poll()
    if code is None:
        return {"running": True, "pid": _scrape_proc.pid}
    # Process finished
    _scrape_proc = None
    return {"running": False}


@router.post("/save-config")
async def save_config(payload: dict):
    config_file = Path.home() / ".apply4me" / "config.json"
    config_file.parent.mkdir(exist_ok=True)
    existing = json.loads(config_file.read_text()) if config_file.exists() else {}
    existing.update(payload)
    config_file.write_text(json.dumps(existing, indent=2))
    return {"ok": True}


SUPPORTED_ATS = {"greenhouse", "lever", "ashby", "workday", "easy_apply", "unknown"}


@router.post("/apply/{job_id}")
async def trigger_apply(job_id: int, session: Session = Depends(get_session)):
    """Trigger ATS application for a job."""
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Return early if no automation adapter exists for this ATS type
    if job.ats_type not in SUPPORTED_ATS:
        # For unsupported ATS types the stored ats_url is unreliable
        # (LinkedIn redirects, signup pages, etc.) — always use the job page URL.
        apply_url = job.url or ""
        raise HTTPException(
            status_code=422,
            detail={
                "reason": "unsupported_ats",
                "ats_type": job.ats_type,
                "apply_url": apply_url,
                "message": (
                    f"No automation adapter for '{job.ats_type}' — only "
                    f"{', '.join(sorted(SUPPORTED_ATS))} are supported. "
                    "Open the job link to apply manually."
                ),
            }
        )

    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "pw.ats.run", "--job-id", str(job_id)],
            cwd=APP_ROOT
        )
        return {"status": "started", "pid": proc.pid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
