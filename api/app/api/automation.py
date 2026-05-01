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


_LOCATIONS = [
    {"name": "United States",  "geo_id": "103644278"},
    {"name": "United Kingdom", "geo_id": "101165590"},
    {"name": "Canada",         "geo_id": "101174742"},
    {"name": "Australia",      "geo_id": "101452733"},
    {"name": "Germany",        "geo_id": "101282230"},
    {"name": "France",         "geo_id": "105015875"},
    {"name": "Netherlands",    "geo_id": "102890719"},
    {"name": "Sweden",         "geo_id": "105117694"},
    {"name": "Denmark",        "geo_id": "104514075"},
    {"name": "Norway",         "geo_id": "103819153"},
    {"name": "Finland",        "geo_id": "100456013"},
    {"name": "Switzerland",    "geo_id": "106693272"},
    {"name": "Austria",        "geo_id": "103883259"},
    {"name": "Belgium",        "geo_id": "100565514"},
    {"name": "Ireland",        "geo_id": "104738515"},
    {"name": "Portugal",       "geo_id": "100364837"},
    {"name": "Spain",          "geo_id": "105646813"},
    {"name": "Italy",          "geo_id": "103350119"},
    {"name": "Poland",         "geo_id": "105072130"},
    {"name": "Czech Republic", "geo_id": "104508036"},
    {"name": "Romania",        "geo_id": "106670623"},
    {"name": "Ukraine",        "geo_id": "102264497"},
    {"name": "Israel",         "geo_id": "101620260"},
    {"name": "India",          "geo_id": "102713980"},
    {"name": "Singapore",      "geo_id": "102454443"},
    {"name": "Japan",          "geo_id": "101355337"},
    {"name": "South Korea",    "geo_id": "105149290"},
    {"name": "Brazil",         "geo_id": "106057199"},
    {"name": "Mexico",         "geo_id": "103323778"},
    {"name": "Argentina",      "geo_id": "100446943"},
    {"name": "New Zealand",    "geo_id": "105490917"},
    {"name": "South Africa",   "geo_id": "104035573"},
]

@router.get("/locations")
async def get_locations():
    """Return supported countries with their LinkedIn geoIds."""
    return _LOCATIONS


class ScrapeRequest(BaseModel):
    keywords: list[str] = []
    location: str = "Remote"
    country: str = ""
    city: str = ""
    date_posted: str = "past_week"
    work_types: list[str] = []
    max_applicants: int | None = None
    easy_apply_only: bool = False


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


SESSION_LIFETIME_HOURS = 3  # LinkedIn sessions last ~2-3 hours in practice

@router.get("/session-status")
async def session_status():
    import time
    cookie_file = Path.home() / ".apply4me" / "linkedin_cookies.json"
    if not cookie_file.exists():
        return {"has_session": False, "expired": False, "expires_at": None}
    try:
        cookies = json.loads(cookie_file.read_text())
        li_at = next((c for c in cookies if c.get("name") == "li_at"), None)
        if not li_at:
            return {"has_session": False, "expired": False, "expires_at": None}

        # Use cookie file mtime as "authenticated_at" — this is when the user last logged in.
        # LinkedIn's cookie.expires is ~1 year (nominal) but the session is invalidated
        # server-side after a few hours, so we use our own estimated expiry.
        authenticated_at = cookie_file.stat().st_mtime
        expires_at = authenticated_at + SESSION_LIFETIME_HOURS * 3600

        if expires_at < time.time():
            return {"has_session": False, "expired": True, "expires_at": expires_at}
        return {"has_session": True, "expired": False, "expires_at": expires_at}
    except Exception:
        return {"has_session": False, "expired": False, "expires_at": None}


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
            "easy_apply_only": req.easy_apply_only,
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
