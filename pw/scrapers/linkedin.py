"""
LinkedIn job scraper using saved session cookies.

Usage:
  python -m pw.scrapers.linkedin --config '{"keywords":["QA Engineer"],"location":"Remote"}'
"""
import asyncio
import json
import sys
import time
from typing import Optional
from urllib.parse import quote

import httpx
from playwright.async_api import async_playwright, Page

from pw.auth.session import load_cookies

BACKEND_URL = "http://localhost:8000"


def build_linkedin_search_url(keywords: list[str], location: str, date_posted: str) -> str:
    kw = quote(" ".join(keywords))
    loc = quote(location)

    time_filter_map = {
        "past_day": "r86400",
        "past_week": "r604800",
        "past_month": "r2592000",
    }
    time_filter = time_filter_map.get(date_posted, "r604800")

    return (
        f"https://www.linkedin.com/jobs/search/"
        f"?keywords={kw}&location={loc}&f_TPR={time_filter}&f_LF=f_AL"
    )


async def scroll_to_load_all(page: Page, max_scrolls: int = 10):
    """Scroll the job list container to load more results."""
    for _ in range(max_scrolls):
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(1500)

        # Try clicking "Show more jobs" button if it exists
        btn = page.locator("button.infinite-scroller__show-more-button")
        if await btn.is_visible():
            await btn.click()
            await page.wait_for_timeout(2000)


async def extract_job_cards(page: Page) -> list[dict]:
    """Extract job cards from LinkedIn search results page."""
    cards = []

    job_list = page.locator("ul.jobs-search__results-list li, div.job-search-card")
    count = await job_list.count()

    for i in range(min(count, 50)):
        try:
            card = job_list.nth(i)

            title_el = card.locator("h3.base-search-card__title, a.job-card-list__title")
            company_el = card.locator("h4.base-search-card__subtitle, a.job-card-container__company-name")
            location_el = card.locator("span.job-search-card__location, li.job-card-container__metadata-item")
            link_el = card.locator("a.base-card__full-link, a[href*='/jobs/view/']")

            title = await title_el.first.inner_text() if await title_el.count() > 0 else ""
            company = await company_el.first.inner_text() if await company_el.count() > 0 else ""
            location = await location_el.first.inner_text() if await location_el.count() > 0 else ""
            href = await link_el.first.get_attribute("href") if await link_el.count() > 0 else ""

            title = title.strip()
            company = company.strip()
            location = location.strip()

            # Clean LinkedIn URL — remove tracking params
            if href and "?" in href:
                href = href.split("?")[0]

            if title and href:
                cards.append({
                    "title": title,
                    "company": company,
                    "location": location,
                    "url": href,
                })
        except Exception:
            continue

    return cards


async def extract_job_detail(page: Page, job_url: str) -> dict:
    """Open a job detail page and extract JD text + external apply URL."""
    try:
        await page.goto(job_url, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(2000)

        # Extract JD text
        jd_el = page.locator("div.description__text, div.jobs-description__content, div#job-details")
        jd_text = ""
        if await jd_el.count() > 0:
            jd_text = await jd_el.first.inner_text()

        # Find external apply URL (non Easy-Apply jobs have "Apply" button with external URL)
        apply_btn = page.locator("a.apply-button, a[href*='greenhouse'], a[href*='lever.co'], a[href*='ashbyhq'], a[href*='workday']")
        ats_url = ""
        ats_type = "unknown"

        if await apply_btn.count() > 0:
            ats_url = await apply_btn.first.get_attribute("href") or ""
            if "greenhouse" in ats_url:
                ats_type = "greenhouse"
            elif "lever.co" in ats_url:
                ats_type = "lever"
            elif "ashby" in ats_url:
                ats_type = "ashby"
            elif "workday" in ats_url:
                ats_type = "workday"

        return {
            "jd_text": jd_text.strip(),
            "ats_url": ats_url,
            "ats_type": ats_type,
        }
    except Exception as e:
        print(f"  Error extracting detail from {job_url}: {e}")
        return {"jd_text": "", "ats_url": "", "ats_type": "unknown"}


async def post_jobs_to_backend(jobs: list[dict]):
    """POST scraped jobs to backend for deduplication and storage."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(f"{BACKEND_URL}/api/jobs/bulk", json=jobs)
            resp.raise_for_status()
            data = resp.json()
            print(f"  Saved {len(data)} jobs to backend")
            return data
        except Exception as e:
            print(f"  Failed to post to backend: {e}")
            return []


async def scrape(config: dict):
    keywords = config.get("keywords", ["Software Engineer"])
    location = config.get("location", "Remote")
    date_posted = config.get("date_posted", "past_week")
    blacklist = set(config.get("blacklist_companies", []))

    print(f"Scraping LinkedIn for: {keywords} in {location}")

    cookies = load_cookies()
    search_url = build_linkedin_search_url(keywords, location, date_posted)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        )
        await context.add_cookies(cookies)

        page = await context.new_page()
        print(f"Navigating to: {search_url}")
        await page.goto(search_url, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(3000)

        await scroll_to_load_all(page)

        cards = await extract_job_cards(page)
        print(f"Found {len(cards)} job cards")

        # Filter blacklisted companies
        cards = [c for c in cards if c["company"] not in blacklist]

        # Enrich each card with JD + ATS URL
        enriched = []
        for i, card in enumerate(cards):
            print(f"  [{i+1}/{len(cards)}] Getting details: {card['title']} @ {card['company']}")
            detail = await extract_job_detail(page, card["url"])
            enriched.append({**card, **detail})
            await asyncio.sleep(1.5)  # polite delay

        await browser.close()

    if enriched:
        await post_jobs_to_backend(enriched)

    return enriched


if __name__ == "__main__":
    args = sys.argv[1:]
    config = {}
    if "--config" in args:
        idx = args.index("--config")
        config = json.loads(args[idx + 1])

    asyncio.run(scrape(config))
