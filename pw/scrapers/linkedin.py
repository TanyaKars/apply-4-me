"""
LinkedIn job scraper using saved session cookies.

Usage:
  python -m pw.scrapers.linkedin --config '{"keywords":["QA Engineer"],"location":"Remote"}'
"""
import asyncio
import json
import re
import sys
from urllib.parse import quote

import httpx
from playwright.async_api import async_playwright, Page

from pw.auth.session import load_cookies

BACKEND_URL = "http://localhost:8000"


WORK_TYPE_MAP = {"remote": "2", "hybrid": "3", "onsite": "1"}

APPLICANT_LIMITS = {
    "lt10": 10,
    "lt50": 50,
    "lt100": 100,
}


def build_linkedin_search_url(
    keywords: list[str],
    location: str,
    date_posted: str,
    work_types: list[str] | None = None,
) -> str:
    kw = quote(" ".join(keywords))
    loc = quote(location)

    time_filter_map = {
        "past_day": "r86400",
        "past_week": "r604800",
        "past_month": "r2592000",
    }
    time_filter = time_filter_map.get(date_posted, "r604800")

    url = (
        f"https://www.linkedin.com/jobs/search/"
        f"?keywords={kw}&location={loc}&f_TPR={time_filter}"
    )

    if work_types:
        codes = [WORK_TYPE_MAP[wt] for wt in work_types if wt in WORK_TYPE_MAP]
        if codes:
            # f_WT takes comma-separated codes — do NOT encode the comma
            url += f"&f_WT={','.join(codes)}"

    return url


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
    """Open job page and extract JD text + external apply URL + applicant count."""
    try:
        await page.goto(job_url, wait_until="domcontentloaded", timeout=30_000)
        await page.wait_for_timeout(2000)

        # JD text
        jd_el = page.locator(
            "div.description__text, div.jobs-description__content, "
            "div#job-details, article.jobs-description__container"
        )
        jd_text = await jd_el.first.inner_text() if await jd_el.count() > 0 else ""

        # External ATS apply URL — only match known ATS domains, never LinkedIn-internal links
        apply_btn = page.locator(
            "a[href*='greenhouse.io'], a[href*='lever.co'], "
            "a[href*='ashbyhq.com'], a[href*='workday.com'], "
            "a[href*='icims.com'], a[href*='taleo.net'], "
            "a[href*='smartrecruiters.com'], a[href*='jobvite.com'], "
            "a.apply-button[href*='http']"
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

        # If no external ATS found, check for LinkedIn Easy Apply
        if ats_type == "unknown":
            easy_apply = page.locator(
                "button:has-text('Easy Apply'), "
                "button.jobs-apply-button:has-text('Apply'), "
                "[data-job-id] button:has-text('Apply')"
            )
            # Also check page text as fallback — more resilient to DOM changes
            has_easy_apply_text = await page.evaluate("""() => {
                const btns = document.querySelectorAll('button');
                for (const b of btns) {
                    if (b.innerText && b.innerText.trim().toLowerCase().includes('easy apply')) return true;
                }
                return false;
            }""")
            if await easy_apply.count() > 0 or has_easy_apply_text:
                ats_url = job_url  # apply on LinkedIn itself
                ats_type = "easy_apply"

        # Closed check — skip jobs no longer accepting applications
        closed = await page.evaluate("""() => {
            const body = document.body.innerText.toLowerCase();
            return body.includes('no longer accepting applications') ||
                   body.includes('not accepting applications');
        }""")
        if closed:
            return {"closed": True, "jd_text": "", "ats_url": "", "ats_type": "unknown", "applicant_count": None}

        # Applicant count — text like "42 applicants" / "Over 200 applicants" / "Be among the first 25"
        # LinkedIn changes class names frequently, so walk all text nodes for "applicant"
        applicant_count: int | None = None
        try:
            count_text = await page.evaluate("""() => {
                // Walk every visible text node looking for "applicant"
                const walker = document.createTreeWalker(
                    document.body,
                    NodeFilter.SHOW_TEXT,
                    null
                );
                let node;
                while ((node = walker.nextNode())) {
                    const t = node.textContent.trim();
                    if (t.toLowerCase().includes('applicant')) {
                        return t;
                    }
                }
                return '';
            }""")
            if count_text:
                nums = re.findall(r"\d[\d,]*", count_text)
                if nums:
                    applicant_count = int(nums[-1].replace(",", ""))
        except Exception:
            pass

        return {
            "jd_text": jd_text.strip(),
            "ats_url": ats_url,
            "ats_type": ats_type,
            "applicant_count": applicant_count,
        }
    except Exception as e:
        print(f"  Error extracting detail from {job_url}: {e}")
        return {"jd_text": "", "ats_url": "", "ats_type": "unknown", "applicant_count": None}


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
    date_posted = config.get("date_posted", "past_week")
    blacklist = set(config.get("blacklist_companies", []))
    work_types = config.get("work_types", [])
    max_applicants: int | None = config.get("max_applicants")  # None means no limit

    # Build location from city + country (or legacy flat "location" field)
    country = config.get("country", "")
    city = config.get("city", "")
    if city and country:
        location = f"{city}, {country}"
    elif country:
        location = country
    else:
        location = config.get("location", "Remote")

    if date_posted not in ("past_day", "past_week", "past_month"):
        print(f"  Warning: unknown date_posted value '{date_posted}', defaulting to past_week")

    print(f"Scraping LinkedIn for: {keywords} in {location}")
    print(f"  Date posted: {date_posted}")
    print(f"  Work types: {work_types or 'any'}")
    print(f"  Max applicants: {max_applicants if max_applicants is not None else 'any'}")

    cookies = load_cookies()
    search_url = build_linkedin_search_url(keywords, location, date_posted, work_types or None)

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

        blacklist_lower = {b.lower() for b in blacklist}
        cards = [c for c in cards if c["company"].lower() not in blacklist_lower]

        # Filter cards by location text when a specific country is requested.
        # LinkedIn's remote filter still surfaces international jobs, so we
        # post-filter: keep cards whose location is empty/generic OR contains
        # the target country name.
        if country:
            country_variants = [country.lower()]
            if country.lower() in ("united states", "usa", "us"):
                country_variants += ["united states", "usa", "u.s."]
            elif country.lower() in ("united kingdom", "uk"):
                country_variants += ["united kingdom", "uk", "great britain"]

            # Known countries to exclude (anything that looks like another country)
            # We use an allowlist: keep only if location is blank/remote OR contains target
            def _location_ok(loc: str) -> bool:
                loc = loc.lower().strip()
                if not loc or loc in ("remote", "worldwide", "anywhere"):
                    return True
                return any(v in loc for v in country_variants)

            before = len(cards)
            cards = [c for c in cards if _location_ok(c.get("location", ""))]
            print(f"Location filter ({country}): {before} → {len(cards)} cards")

        # Filter by work type keywords in the job title.
        # LinkedIn's f_WT filter leaks jobs — catch what slips through by
        # rejecting titles that explicitly mention excluded work types.
        if work_types and not any(wt in work_types for wt in ("onsite", "hybrid")):
            # User wants remote only — drop cards that say otherwise in the title
            ONSITE_KEYWORDS = {
                "on-site", "onsite", "on site", "in-person", "in person",
                "hybrid", "office-based", "office based", "must be local",
            }
            def _title_is_remote(title: str) -> bool:
                t = title.lower()
                return not any(kw in t for kw in ONSITE_KEYWORDS)

            before = len(cards)
            cards = [c for c in cards if _title_is_remote(c.get("title", ""))]
            print(f"Work type title filter (remote only): {before} → {len(cards)} cards")

        enriched = []
        for i, card in enumerate(cards[:50]):
            print(f"  [{i+1}/{len(cards)}] {card['title']} @ {card['company']}")
            detail = await extract_job_detail(page, card["url"])

            if detail.get("closed"):
                print(f"    Skipping — no longer accepting applications")
                continue

            # Filter by applicant count if set
            count = detail.get("applicant_count")
            print(f"    Applicants: {count if count is not None else 'unknown'}")
            if max_applicants is not None:
                if count is None:
                    # Could not extract count — skip to be safe when filter is strict
                    print(f"    Skipping — applicant count unknown, filter is {max_applicants}")
                    continue
                if count > max_applicants:
                    print(f"    Skipping — {count} applicants > limit {max_applicants}")
                    continue

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
