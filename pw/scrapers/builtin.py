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

# Work type → URL path segment (builtin.com/jobs/remote, /jobs/hybrid, /jobs/office)
WORK_TYPE_PATH: dict[str, str] = {
    "remote": "remote",
    "hybrid": "hybrid",
    "onsite": "office",
}

# Country name → Builtin ISO 3166-1 alpha-3 code
COUNTRY_CODE_MAP: dict[str, str] = {
    "United States":  "USA",
    "United Kingdom": "GBR",
    "Canada":         "CAN",
    "Australia":      "AUS",
    "Germany":        "DEU",
    "France":         "FRA",
    "Netherlands":    "NLD",
    "Ireland":        "IRL",
    "Sweden":         "SWE",
    "Denmark":        "DNK",
    "Norway":         "NOR",
    "Finland":        "FIN",
    "Switzerland":    "CHE",
    "Austria":        "AUT",
    "Belgium":        "BEL",
    "Portugal":       "PRT",
    "Spain":          "ESP",
    "Italy":          "ITA",
    "Poland":         "POL",
    "Czech Republic": "CZE",
    "Romania":        "ROU",
    "Ukraine":        "UKR",
    "Israel":         "ISR",
    "India":          "IND",
    "Singapore":      "SGP",
    "Japan":          "JPN",
    "South Korea":    "KOR",
    "Brazil":         "BRA",
    "Mexico":         "MEX",
    "Argentina":      "ARG",
    "New Zealand":    "NZL",
    "South Africa":   "ZAF",
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


def _html_to_text(raw: str) -> str:
    """Convert HTML fragment to readable plain text."""
    raw = re.sub(r"<br\s*/?>", "\n", raw, flags=re.IGNORECASE)
    raw = re.sub(r"</(p|div|h[1-6]|section|article|tr)>", "\n", raw, flags=re.IGNORECASE)
    raw = re.sub(r"</li>", "\n", raw, flags=re.IGNORECASE)
    raw = re.sub(r"<li[^>]*>", "• ", raw, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", raw)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&nbsp;", " ").replace("&#39;", "'").replace("&quot;", '"')
    # Strip each line, drop Builtin UI noise, collapse consecutive blank lines
    _UI_NOISE = re.compile(
        r"^(read full description|view all jobs at .+|view .+ profile|report job|save job|apply now|"
        r"summary generated by built ?in.*)$",
        re.IGNORECASE,
    )
    lines = [line.strip() for line in text.splitlines()]
    result: list[str] = []
    prev_blank = False
    for line in lines:
        if _UI_NOISE.match(line):
            continue
        is_blank = not line
        if is_blank and prev_blank:
            continue
        result.append(line)
        prev_blank = is_blank
    return "\n".join(result).strip()


def _parse_listing_html(html: str) -> list[dict]:
    """Parse Builtin listing page (Alpine.js structure with job-card-{id} divs)."""
    jobs: list[dict] = []
    seen: set[str] = set()

    # Split HTML at each job card boundary
    card_blocks = re.split(r'(?=<div[^>]+id="job-card-\d+[^"]*")', html)

    for block in card_blocks:
        if not re.match(r'<div[^>]+id="job-card-\d+', block):
            continue

        # Title link: <a href="/job/..." data-id="job-card-title" ...>Title</a>
        title_m = re.search(
            r'<a\b[^>]*href="(/job/[^"]+)"[^>]*data-id="job-card-title"[^>]*>\s*"?([^"<\n]+)',
            block,
        ) or re.search(
            r'data-id="job-card-title"[^>]*href="(/job/[^"]+)"[^>]*>\s*"?([^"<\n]+)',
            block,
        )
        if not title_m:
            continue

        href = title_m.group(1)
        title = title_m.group(2).strip().strip('"').strip()
        url = f"https://builtin.com{href}"
        if url in seen:
            continue
        seen.add(url)

        # Company name — try data-id="job-card-company" or class containing "company"
        company = ""
        for pat in (
            r'data-id="job-card-company"[^>]*>\s*([^<]+)',
            r'class="[^"]*company[^"]*"[^>]*>\s*([^<\n]+)',
        ):
            cm = re.search(pat, block)
            if cm:
                company = cm.group(1).strip()
                break

        # Location — try data-id="job-card-location" or class containing "location"
        location = ""
        for pat in (
            r'data-id="job-card-location"[^>]*>\s*([^<]+)',
            r'class="[^"]*location[^"]*"[^>]*>\s*([^<\n]+)',
        ):
            lm = re.search(pat, block)
            if lm:
                location = lm.group(1).strip()
                break

        jobs.append({
            "title": title,
            "company": company,
            "location": location,
            "url": url,
            "is_easy_apply": False,
            "source": "builtin",
        })

    return jobs[:50]


def _parse_html_fallback(html: str) -> list[dict]:
    """Last-resort fallback — extracts job URLs from raw /job/ hrefs."""
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
    keyword: str,
    work_types: list[str],
    days_since_updated: int | None,
    country: str,
    state: str,
    cookies: dict,
) -> list[dict]:
    """Fetch job listings for a single keyword via Builtin guest search."""
    # Build URL path: /jobs, /jobs/remote, /jobs/remote/hybrid, etc.
    type_segs = [WORK_TYPE_PATH[wt] for wt in work_types if wt in WORK_TYPE_PATH]
    path = "/jobs/" + "/".join(type_segs) if type_segs else "/jobs"

    country_code = COUNTRY_CODE_MAP.get(country, "USA") if country else "USA"
    params: dict[str, str] = {
        "search": keyword,
        "country": country_code,
        "allLocations": "true",
    }
    if days_since_updated:
        params["daysSinceUpdated"] = str(days_since_updated)
    if state and country_code == "USA":
        params["state"] = state

    qs = "&".join(f"{k}={v}" for k, v in params.items())
    url = f"https://builtin.com{path}?{qs}"
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

    # Primary: Alpine.js job-card-{id} structure
    cards = _parse_listing_html(html)
    if cards:
        print(f"  Alpine.js parser: {len(cards)} cards")
        return cards

    # Secondary: Next.js __NEXT_DATA__ (some Builtin pages use it)
    next_data = _extract_next_data(html)
    if next_data:
        raw_jobs = _find_jobs_in_next_data(next_data)
        print(f"  __NEXT_DATA__: {len(raw_jobs)} raw job entries")
        if raw_jobs:
            nd_cards = [c for r in raw_jobs if (c := _parse_job_card(r)) is not None]
            print(f"  Parsed: {len(nd_cards)} valid cards")
            return nd_cards
        page_props = next_data.get("props", {}).get("pageProps", {})
        print(f"  pageProps keys: {list(page_props.keys())}")
    else:
        print("  No __NEXT_DATA__ found")

    # Last resort: extract any /job/ hrefs
    fallback = _parse_html_fallback(html)
    print(f"  URL-fallback: {len(fallback)} cards")
    return fallback


def _extract_role_section(html: str) -> str:
    """Extract 'The Role' section from a Builtin job detail page.

    Looks for a heading containing 'The Role' then collects all text until
    the next section heading (h2/h3 or a sibling section boundary).
    """
    # Section heading patterns (case-insensitive)
    # The Role heading followed by content until the next heading
    m = re.search(
        r'<(?:h2|h3|h4)[^>]*>\s*(?:<[^>]+>)*\s*The Role\s*(?:</[^>]+>)*\s*</(?:h2|h3|h4)>(.*?)'
        r'(?=<(?:h2|h3|h4)[^>]*>|\Z)',
        html, re.DOTALL | re.IGNORECASE,
    )
    if m:
        text = _html_to_text(m.group(1))
        if len(text) > 80:
            return text

    # Fallback: find "The Role" as plain text and grab following content
    idx = html.lower().find("the role")
    if idx != -1:
        tag_close = html.find(">", idx)
        if tag_close != -1:
            raw = html[tag_close + 1: tag_close + 8000]
            stop = re.search(r'<(?:h2|h3)[^>]*>', raw)
            if stop:
                raw = raw[: stop.start()]
            text = _html_to_text(raw)
            if len(text) > 80:
                return text

    return ""


def _extract_jd_text(html: str) -> str:
    """Extract job description from a Builtin job detail page."""
    # 1. Try __NEXT_DATA__ — full content is often there even when UI truncates
    next_data = _extract_next_data(html)
    if next_data:
        page_props = next_data.get("props", {}).get("pageProps", {})
        job = page_props.get("job") or page_props.get("jobPosting") or {}
        for key in ("role", "theRole", "responsibilities", "description", "jobDescription", "body", "content"):
            text = job.get(key)
            if text and isinstance(text, str) and len(text) > 80:
                return _html_to_text(text)

    # 2. HTML: find "The Role" section specifically
    role_text = _extract_role_section(html)
    if role_text:
        return role_text

    # 3. Generic HTML fallback
    for marker in ("job-description", "jobDescription", "description__content", "job-details"):
        idx = html.find(marker)
        if idx == -1:
            continue
        tag_end = html.find(">", idx)
        if tag_end == -1:
            continue
        raw = html[tag_end + 1: tag_end + 12000]
        text = _html_to_text(raw)
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
    keywords = config.get("keywords", ["Software Engineer"])[:5]
    work_types = config.get("work_types", [])
    days_since_updated: int | None = config.get("days_since_updated")
    country: str = config.get("country", "United States")
    state: str = config.get("state", "")
    blacklist = {b.lower() for b in config.get("blacklist_companies", [])}

    cookies = _build_cookies(load_cookies())

    print(f"Scraping Builtin for: {keywords}")
    print(f"  Work types: {work_types or 'any'}")
    print(f"  Days since updated: {days_since_updated or 'any'}")
    print(f"  Country: {country}, State: {state or 'any'}")

    # Run a separate search per keyword and deduplicate by URL
    all_cards: list[dict] = []
    seen_urls: set[str] = set()
    for kw in keywords:
        print(f"\n--- Searching: '{kw}' ---")
        kw_cards = await fetch_job_listings(kw, work_types, days_since_updated, country, state, cookies)
        new = [c for c in kw_cards if c["url"] not in seen_urls]
        for c in new:
            seen_urls.add(c["url"])
        all_cards.extend(new)
        print(f"  New unique cards from '{kw}': {len(new)}")
        await asyncio.sleep(1.0)

    cards = all_cards
    print(f"\nTotal cards collected: {len(cards)}")

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
