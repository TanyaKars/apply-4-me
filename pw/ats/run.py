"""
Entry point for ATS application automation.

Usage:
  python -m pw.ats.run --job-id 42
"""
import asyncio
import json
import sys
from pathlib import Path

import httpx
from playwright.async_api import async_playwright

from pw.auth.session import load_cookies
from pw.ats.detector import detect_ats, get_adapter

BACKEND_URL = "http://localhost:8000"


async def apply_to_job(job_id: int):
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BACKEND_URL}/api/jobs/{job_id}")
        resp.raise_for_status()
        job = resp.json()

    # Use the stored ats_type — re-detecting from the URL fails for LinkedIn Easy Apply
    # because linkedin.com URLs don't match any ATS pattern.
    ats_type = job.get("ats_type") or "unknown"
    ats_url = job.get("ats_url") or job.get("url")

    # Fall back to URL-based detection only when stored type is unknown
    if ats_type == "unknown" and ats_url:
        ats_type = detect_ats(ats_url)

    print(f"ATS type: {ats_type}  URL: {ats_url}")

    if not ats_url:
        print("No ATS URL found for this job.")
        return

    AdapterClass = get_adapter(ats_type)
    if not AdapterClass:
        print(f"No adapter for ATS type: {ats_type}. Please apply manually.")
        return

    # Get resume data
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BACKEND_URL}/api/resume/")
        resume_payload = resp.json()

    resume_data = resume_payload.get("data", {})
    pdf_path = job.get("tailored_resume_path", "")

    if not pdf_path or not Path(pdf_path).exists():
        print("No tailored PDF found. Generate one first via the UI.")
        return

    cookies = load_cookies()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=100)
        context = await browser.new_context()
        # Add LinkedIn cookies in case needed for auth
        await context.add_cookies(cookies)
        page = await context.new_page()

        # For easy_apply, always navigate to the job page itself, not any cached ats_url
        apply_target = job.get("url") if ats_type == "easy_apply" else ats_url
        adapter = AdapterClass(page, resume_data, pdf_path)
        success = await adapter.fill_form(apply_target)

        if success:
            # Update job status
            async with httpx.AsyncClient() as client:
                await client.patch(
                    f"{BACKEND_URL}/api/jobs/{job_id}",
                    json={"status": "applied"}
                )
            print(f"Job {job_id} marked as applied!")

        await browser.close()


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
