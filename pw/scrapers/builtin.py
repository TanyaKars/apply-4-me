"""
Builtin.com job scraper using httpx (no browser — minimal bot detection).

Fetches https://builtin.com/jobs and extracts job listings from the
Next.js __NEXT_DATA__ payload embedded in the HTML. Auth is optional —
cookies are loaded if available, otherwise the scraper runs unauthenticated.

Usage:
  python -m pw.scrapers.builtin --config '{"keywords":["QA Engineer"],"work_types":["remote"]}'
"""
import asyncio
import json
import re
import sys

import httpx

from pw.auth.builtin_session import load_cookies

BACKEND_URL = "http://localhost:8000"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
}

# Builtin query params for work type filtering
WORK_TYPE_PARAMS: dict[str, str] = {
    "remote": "remote=true",
    "hybrid": "hybrid=true",
    "onsite": "inOffice=true",
}


def _build_cookies(cookies_list: list[dict]) -> dict[str, str]:
    return {c["name"]: c["value"] for c in cookies_list}


def _extract_next_data(html: str) -> dict | None:
    m = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html, re.DOTALL,
    )
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def _find_jobs_in_next_data(data: dict) -> list[dict]:
    """Walk known paths in Builtin's Next.js page data to find job listings."""
    page_props = data.get("props", {}).get("pageProps", {})
    candidates = [
        page_props.get("jobs"),
        page_props.get("initialJobs"),
        page_props.get("jobListings"),
        (page_props.get("searchResults") or {}).get("jobs"),
        (page_props.get("initialSearchResults") or {}).get("jobs"),
        (page_props.get("data") or {}).get("jobs"),
    ]
    return next((c for c in candidates if isinstance(c, list) and c), [])


def _parse_job_card(raw: dict) -> dict | None:
    """Normalize a raw Builtin job dict into our standard shape."""
    title = raw.get("title") or raw.get("name") or ""
    if not title:
        return None

    company_raw = raw.get("company") or raw.get("companyName") or ""
    company = company_raw.get("name") if isinstance(company_raw, dict) else str(company_raw)

    loc_raw = raw.get("location") or raw.get("locations") or ""
    if isinstance(loc_raw, list):
        loc_raw = loc_raw[0] if loc_raw else {}
    if isinstance(loc_raw, dict):
        location = loc_raw.get("name") or loc_raw.get("city") or ""
    else:
        location = str(loc_raw)

    slug = raw.get("slug") or ""
    job_id = raw.get("id") or raw.get("jobId") or ""
    url = raw.get("url") or raw.get("applyUrl") or ""
    if not url:
        if slug:
            url = f"https://builtin.com/job/{slug}"
        elif job_id:
            url = f"https://builtin.com/job/{job_id}"
        else:
            return None
    if not url.startswith("http"):
        url = f"https://builtin.com{url}"

    return {
        "title": title.strip(),
        "company": company.strip(),
        "location": location.strip(),
        "url": url,
        "is_easy_apply": False,
        "source": "builtin",
    }


def _parse_html_fallback(html: str) -> list[dict]:
    """Fallback when __NEXT_DATA__ is absent — extracts job URLs from raw HTML."""
    seen: set[str] = set()
    jobs: list[dict] = []
    for path in re.findall(r'href="(/job/[^"?#]+)"', html):
        if path in seen:
            continue
        seen.add(path)
        parts = path.strip("/").split("/")
        title = parts[-2].replace("-", " ").title() if len(parts) >= 3 else parts[-1].replace("-", " ").title()
        jobs.append({
            "title": title,
            "company": "",
            "location": "",
            "url": f"https://builtin.com{path}",
            "is_easy_apply": False,
            "source": "builtin",
        })
    return jobs[:50]


async def fetch_job_listings(
    keywords: list[str],
    work_types: list[str],
    cookies: dict,
) -> list[dict]:
    keyword_str = "+".join(keywords)
    params: list[str] = [f"search={keyword_str}"]
    for wt in work_types:
        if wt in WORK_TYPE_PARAMS:
            params.append(WORK_TYPE_PARAMS[wt])

    url = f"https://builtin.com/jobs?{'&'.join(params)}"
    print(f"Fetching: {url}")

    async with httpx.AsyncClient(
        headers=_HEADERS, cookies=cookies, timeout=30.0, follow_redirects=True
    ) as client:
        try:
            resp = await client.get(url)
        except Exception as e:
            print(f"  Request failed: {e}")
            return []

        print(f"  HTTP {resp.status_code}, body: {len(resp.text)} chars")
        if not resp.is_success:
            return []
        html = resp.text

    next_data = _extract_next_data(html)
    if next_data:
        raw_jobs = _find_jobs_in_next_data(next_data)
        print(f"  __NEXT_DATA__: {len(raw_jobs)} raw job entries")
        if raw_jobs:
            cards = [c for r in raw_jobs if (c := _parse_job_card(r)) is not None]
            print(f"  Parsed: {len(cards)} valid cards")
            return cards
        # __NEXT_DATA__ found but jobs not at expected paths — log keys for debugging
        page_props = next_data.get("props", {}).get("pageProps", {})
        print(f"  pageProps keys: {list(page_props.keys())}")
    else:
        print("  No __NEXT_DATA__ found — falling back to HTML parsing")

    return _parse_html_fallback(html)


def _extract_jd_text(html: str) -> str:
    """Extract job description from a Builtin job detail page."""
    next_data = _extract_next_data(html)
    if next_data:
        page_props = next_data.get("props", {}).get("pageProps", {})
        job = page_props.get("job") or page_props.get("jobPosting") or {}
        for key in ("description", "jobDescription", "body", "content"):
            text = job.get(key)
            if text and isinstance(text, str) and len(text) > 50:
                clean = re.sub(r"<[^>]+>", " ", text)
                return re.sub(r"\s+", " ", clean).strip()

    for marker in ("job-description", "jobDescription", "description__content", "job-details"):
        idx = html.find(marker)
        if idx == -1:
            continue
        tag_end = html.find(">", idx)
        if tag_end == -1:
            continue
        raw = html[tag_end + 1: tag_end + 12000]
        text = re.sub(r"<[^>]+>", " ", raw)
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) > 100:
            return text

    return ""


async def fetch_job_detail(client: httpx.AsyncClient, job_url: str) -> dict:
    try:
        resp = await client.get(job_url)
        if not resp.is_success:
            return {"jd_text": "", "ats_type": "unknown", "ats_url": "", "applicant_count": None}
        jd_text = _extract_jd_text(resp.text)
        return {"jd_text": jd_text, "ats_type": "unknown", "ats_url": "", "applicant_count": None}
    except Exception as e:
        print(f"  Error fetching detail for {job_url}: {e}")
        return {"jd_text": "", "ats_type": "unknown", "ats_url": "", "applicant_count": None}


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
    work_types = config.get("work_types", [])
    blacklist = {b.lower() for b in config.get("blacklist_companies", [])}

    cookies = _build_cookies(load_cookies())

    print(f"Scraping Builtin for: {keywords}")
    print(f"  Work types: {work_types or 'any'}")

    cards = await fetch_job_listings(keywords, work_types, cookies)
    print(f"Total cards: {len(cards)}")

    if blacklist:
        cards = [c for c in cards if c["company"].lower() not in blacklist]
        print(f"After blacklist: {len(cards)}")

    enriched = []
    async with httpx.AsyncClient(
        headers=_HEADERS, cookies=cookies, timeout=30.0, follow_redirects=True
    ) as client:
        for i, card in enumerate(cards[:50]):
            print(f"  [{i+1}/{min(len(cards), 50)}] {card['title']} @ {card['company']}")
            detail = await fetch_job_detail(client, card["url"])
            print(f"    JD: {len(detail.get('jd_text', ''))} chars")
            enriched.append({**card, **detail})
            await asyncio.sleep(0.5)

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
