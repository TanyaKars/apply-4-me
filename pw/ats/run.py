"""
Entry point for ATS application automation.

Usage:
  python -m pw.ats.run --job-id 42
"""
import asyncio
import json
import subprocess
import sys
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

from pw.auth.session import load_cookies
from pw.auth.builtin_session import storage_state_path as builtin_storage_state_path
from pw.ats.easy_apply import LinkedInEasyApplyAdapter
from pw.ats.ai_filler import AIFillerAdapter


def _kill_stale_playwright_browsers():
    """Kill any Playwright Chromium processes left over from previous crashed runs."""
    subprocess.run(["pkill", "-f", "ms-playwright/chromium"], capture_output=True)

BACKEND_URL = "http://localhost:8000"


async def apply_to_job(job_id: int):
    _kill_stale_playwright_browsers()

    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BACKEND_URL}/api/jobs/{job_id}")
        resp.raise_for_status()
        job = resp.json()

    ats_type = job.get("ats_type") or "unknown"
    ats_url = job.get("ats_url") or job.get("url")

    print(f"ATS type: {ats_type}  URL: {ats_url}")

    if not ats_url:
        print("No ATS URL found for this job.")
        return

    # Resume data is stored on the job itself after tailoring
    raw = job.get("tailored_data")
    resume_data = json.loads(raw) if raw else {}
    pdf_path = job.get("tailored_resume_path", "")

    if not pdf_path or not Path(pdf_path).exists():
        print("No tailored PDF found. Generate one first via the UI.")
        return

    is_builtin = "builtin.com" in (ats_url or "")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=100)
        if is_builtin and (builtin_state := builtin_storage_state_path()):
            context = await browser.new_context(storage_state=builtin_state)
        else:
            cookies = load_cookies()
            context = await browser.new_context()
            await context.add_cookies(cookies)
        page = await context.new_page()

        if ats_type == "easy_apply":
            adapter = LinkedInEasyApplyAdapter(page, resume_data, pdf_path)
            apply_target = job.get("url")
        else:
            adapter = AIFillerAdapter(
                page, resume_data, pdf_path,
                jd_text=job.get("jd_text", ""),
                job_id=job_id,
            )
            apply_target = ats_url

        try:
            success = await adapter.fill_form(apply_target)

            async with httpx.AsyncClient() as client:
                if success:
                    await client.patch(
                        f"{BACKEND_URL}/api/jobs/{job_id}",
                        json={"status": "applied"}
                    )
                    print(f"Job {job_id} marked as applied!")
                else:
                    stop_reason = getattr(adapter, "stop_reason", "")
                    if "account creation" in stop_reason.lower():
                        await client.post(f"{BACKEND_URL}/api/jobs/{job_id}/pend")
                        print(f"Job {job_id} moved to pending — account creation required.")
        finally:
            await browser.close()
            _kill_stale_playwright_browsers()


if __name__ == "__main__":
    args = sys.argv[1:]
    job_id = None
    if "--job-id" in args:
        idx = args.index("--job-id")
        job_id = int(args[idx + 1])

    if not job_id:
        print("Usage: python -m pw.ats.run --job-id <id>")
        sys.exit(1)

    asyncio.run(apply_to_job(job_id))
