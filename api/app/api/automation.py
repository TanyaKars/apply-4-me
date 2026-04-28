import json
import subprocess
import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class ScrapeRequest(BaseModel):
    keywords: list[str] = []
    location: str = "Remote"
    date_posted: str = "past_week"


class ApplyRequest(BaseModel):
    job_id: int


@router.post("/setup-session")
async def setup_session():
    """Launch browser for LinkedIn session setup."""
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "pw.auth.session", "--setup"],
            cwd="/Users/tatianakarsova/Documents/Code/apply4me"
        )
        return {"status": "launched", "pid": proc.pid, "message": "Browser opened. Log in to LinkedIn, then close the browser."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session-status")
async def session_status():
    from pathlib import Path
    cookie_file = Path.home() / ".apply4me" / "linkedin_cookies.json"
    return {"has_session": cookie_file.exists()}


@router.post("/scrape")
async def trigger_scrape(req: ScrapeRequest):
    """Trigger LinkedIn job scraper."""
    try:
        import json
        config = json.dumps({
            "keywords": req.keywords,
            "location": req.location,
            "date_posted": req.date_posted
        })
        proc = subprocess.Popen(
            [sys.executable, "-m", "pw.scrapers.linkedin", "--config", config],
            cwd="/Users/tatianakarsova/Documents/Code/apply4me"
        )
        return {"status": "started", "pid": proc.pid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/save-config")
async def save_config(payload: dict):
    config_file = Path.home() / ".apply4me" / "config.json"
    config_file.parent.mkdir(exist_ok=True)
    existing = json.loads(config_file.read_text()) if config_file.exists() else {}
    existing.update(payload)
    config_file.write_text(json.dumps(existing, indent=2))
    return {"ok": True}


@router.post("/apply/{job_id}")
async def trigger_apply(job_id: int):
    """Trigger ATS application for a job."""
    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "pw.ats.run", "--job-id", str(job_id)],
            cwd="/Users/tatianakarsova/Documents/Code/apply4me"
        )
        return {"status": "started", "pid": proc.pid}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
