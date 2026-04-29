"""
LinkedIn job scraper using saved session cookies.

Usage:
  python -m pw.scrapers.linkedin --config '{"keywords":["QA Engineer"],"location":"Remote"}'
"""
import asyncio
import json
import sys
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

    # No f_LF filter — include all jobs, not just Easy Apply
    return (
        f"https://www.linkedin.com/jobs/search/"
        f"?keywords={kw}&location={loc}&f_TPR={time_filter}"
    )


async def scroll_to_load_all(page: Page, max_scrolls: int = 10):
    for _ in range(max_scrolls):
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(1500)
        # "Show more jobs" button (class varies — match loosely)
        btn = page.locator("button:has-text('Show more jobs')")
        if await btn.is_visible():
            await btn.click()
            await page.wait_for_timeout(2000)


async def extract_job_cards(page: Page) -> list[dict]:
    """Extract job cards via JS — class-name-agnostic, works with current LinkedIn HTML."""
    cards = await page.evaluate("""() => {
        const results = [];
        const seen = new Set();

        // All job-detail links are reliable anchors regardless of class name changes
        const links = document.querySelectorAll('a[href*="/jobs/view/"]');

        for (const link of links) {
            const href = link.href.split('?')[0];
            if (!href || seen.has(href)) continue;
            seen.add(href);

            // Title: text of the link or its first strong/span child
            const title = (
                link.querySelector('strong, span[aria-hidden="true"]')?.innerText ||
                link.innerText
            ).trim();
            if (!title) continue;

            // Walk up to the card container (li or div with job-card in class)
            let card = link.parentElement;
            for (let i = 0; i < 6 && card; i++) {
                const tag = card.tagName;
                const cls = card.className || '';
                if (tag === 'LI' || cls.includes('job-card') || cls.includes('jobs-search-results__list-item')) break;
                card = card.parentElement;
            }
            if (!card) card = link.parentElement;

            // Company
            const companyEl = card.querySelector(
                'a[href*="/company/"], [class*="company"], [class*="primary-description"], [class*="subtitle"]'
            );
            const company = companyEl?.innerText.trim() || '';

            // Location
            const locEl = card.querySelector(
                '[class*="metadata-item"], [class*="location"], [class*="workplace-type"], li'
            );
            const location = locEl?.innerText.trim() || '';

            results.push({ title, company, location, url: href });
        }

        return results;
    }""")
    return cards


async def extract_job_detail(page: Page, job_url: str) -> dict:
    """Open job page and extract JD text + external apply URL."""
    try:
        await page.goto(job_url, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(2000)

        # JD text
        jd_el = page.locator(
            "div.description__text, div.jobs-description__content, "
            "div#job-details, article.jobs-description__container"
        )
        jd_text = await jd_el.first.inner_text() if await jd_el.count() > 0 else ""

        # External ATS apply URL
        apply_btn = page.locator(
            "a[href*='greenhouse.io'], a[href*='lever.co'], "
            "a[href*='ashbyhq.com'], a[href*='workday.com'], "
            "a[href*='icims.com'], a[href*='taleo.net'], "
            "a.apply-button[href], a[data-tracking-control-name*='apply']"
        )
        ats_url = ""
        ats_type = "unknown"

        if await apply_btn.count() > 0:
            ats_url = await apply_btn.first.get_attribute("href") or ""
            for keyword, name in [
                ("greenhouse", "greenhouse"), ("lever.co", "lever"),
                ("ashby", "ashby"), ("workday", "workday"),
                ("icims", "icims"), ("taleo", "taleo"),
            ]:
                if keyword in ats_url:
                    ats_type = name
                    break

        return {"jd_text": jd_text.strip(), "ats_url": ats_url, "ats_type": ats_type}
    except Exception as e:
        print(f"  Error extracting detail from {job_url}: {e}")
        return {"jd_text": "", "ats_url": "", "ats_type": "unknown"}


async def post_jobs_to_backend(jobs: list[dict]):
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
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        await context.add_cookies(cookies)

        page = await context.new_page()
        print(f"Navigating to: {search_url}")
        await page.goto(search_url, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(4000)

        await scroll_to_load_all(page)

        cards = await extract_job_cards(page)
        print(f"Found {len(cards)} job cards")

        cards = [c for c in cards if c["company"] not in blacklist]

        enriched = []
        for i, card in enumerate(cards[:50]):
            print(f"  [{i+1}/{len(cards)}] {card['title']} @ {card['company']}")
            detail = await extract_job_detail(page, card["url"])
            enriched.append({**card, **detail})
            await asyncio.sleep(1.5)

        await browser.close()

    if enriched:
        await post_jobs_to_backend(enriched)

    print(f"Done. {len(enriched)} jobs processed.")
    return enriched


if __name__ == "__main__":
    args = sys.argv[1:]
    config = {}
    if "--config" in args:
        idx = args.index("--config")
        config = json.loads(args[idx + 1])

    asyncio.run(scrape(config))
