"""
LinkedIn job scraper using httpx (no browser — avoids bot detection).

Phase 1: Guest API for job listings — no auth, proper start= pagination
Phase 2: Guest API per-job endpoint for JD text — no auth, server-rendered HTML

Usage:
  python -m pw.scrapers.linkedin --config '{"keywords":["QA Engineer"],"location":"Remote"}'
"""
import asyncio
import json
import re
import sys

import httpx

from pw.auth.session import load_cookies

BACKEND_URL = "http://localhost:8000"

WORK_TYPE_MAP = {"remote": "2", "hybrid": "3", "onsite": "1"}

GEO_ID_MAP: dict[str, str] = {
    "United States":    "103644278",
    "United Kingdom":   "101165590",
    "Canada":           "101174742",
    "Australia":        "101452733",
    "Germany":          "101282230",
    "France":           "105015875",
    "Netherlands":      "102890719",
    "Sweden":           "105117694",
    "Denmark":          "104514075",
    "Norway":           "103819153",
    "Finland":          "100456013",
    "Switzerland":      "106693272",
    "Austria":          "103883259",
    "Belgium":          "100565514",
    "Ireland":          "104738515",
    "Portugal":         "100364837",
    "Spain":            "105646813",
    "Italy":            "103350119",
    "Poland":           "105072130",
    "Czech Republic":   "104508036",
    "Romania":          "106670623",
    "Ukraine":          "102264497",
    "Israel":           "101620260",
    "India":            "102713980",
    "Singapore":        "102454443",
    "Japan":            "101355337",
    "South Korea":      "105149290",
    "Brazil":           "106057199",
    "Mexico":           "103323778",
    "Argentina":        "100446943",
    "New Zealand":      "105490917",
    "South Africa":     "104035573",
}

TIME_FILTER_MAP = {
    "past_hour":    "r3600",
    "past_2hours":  "r7200",
    "past_6hours":  "r21600",
    "past_12hours": "r43200",
    "past_day":     "r86400",
    "past_week":    "r604800",
    "past_month":   "r2592000",
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "accept-language": "en-US,en;q=0.9",
}


def _build_cookies(cookies_list: list[dict]) -> dict[str, str]:
    return {c["name"]: c["value"] for c in cookies_list}


def _extract_job_id(url: str) -> str | None:
    m = re.search(r"/jobs/view/(\d+)", url)
    return m.group(1) if m else None


def parse_guest_listing_html(html: str) -> list[dict]:
    """Parse job cards from LinkedIn guest search API HTML."""
    jobs: list[dict] = []
    seen: set[str] = set()

    # Split on card boundaries using data-entity-urn (reliable anchor)
    card_pat = re.compile(r'data-entity-urn="urn:li:jobPosting:(\d+)"')
    title_pat = re.compile(r'class="[^"]*base-search-card__title[^"]*"[^>]*>\s*(.*?)\s*</\w', re.DOTALL)
    company_pat = re.compile(r'class="[^"]*base-search-card__subtitle[^"]*"[^>]*>.*?<[^/][^>]*>\s*(.*?)\s*</', re.DOTALL)
    location_pat = re.compile(r'class="[^"]*job-search-card__location[^"]*"[^>]*>\s*(.*?)\s*</', re.DOTALL)

    card_matches = list(card_pat.finditer(html))
    for i, m in enumerate(card_matches):
        job_id = m.group(1)
        job_url = f"https://www.linkedin.com/jobs/view/{job_id}/"
        if job_url in seen:
            continue
        seen.add(job_url)

        start = m.start()
        end = card_matches[i + 1].start() if i + 1 < len(card_matches) else len(html)
        card = html[start:end]

        title_m = title_pat.search(card)
        company_m = company_pat.search(card)
        location_m = location_pat.search(card)

        def clean(s: str) -> str:
            return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s)).strip()

        title = clean(title_m.group(1)) if title_m else ""
        if not title:
            continue

        jobs.append({
            "title": title,
            "company": clean(company_m.group(1)) if company_m else "",
            "location": clean(location_m.group(1)) if location_m else "",
            "url": job_url,
            "is_easy_apply": "easy apply" in card.lower(),
        })

    return jobs


async def fetch_job_listings(
    keywords: list[str],
    location: str,
    date_posted: str,
    work_types: list[str],
    easy_apply_only: bool,
    max_applicants: int | None,
    max_pages: int = 10,
    cookies: dict | None = None,
) -> list[dict]:
    """Fetch job listings via LinkedIn guest API with proper pagination."""
    base_params: dict = {
        "keywords": " ".join(keywords),
        "location": location,
        "f_TPR": TIME_FILTER_MAP.get(date_posted, "r604800"),
        "sortBy": "R",
    }

    if work_types:
        codes = [WORK_TYPE_MAP[wt] for wt in work_types if wt in WORK_TYPE_MAP]
        if codes:
            base_params["f_WT"] = ",".join(codes)

    if easy_apply_only:
        base_params["f_AL"] = "true"

    if max_applicants is not None:
        base_params["f_EA"] = "true"

    all_jobs: list[dict] = []
    seen_urls: set[str] = set()

    async with httpx.AsyncClient(headers=_HEADERS, cookies=cookies or {}, timeout=30.0, follow_redirects=True) as client:
        for page_num in range(max_pages):
            params = {**base_params, "start": page_num * 25}
            url = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
            print(f"Page {page_num + 1} (start={params['start']})")

            try:
                resp = await client.get(url, params=params)
            except Exception as e:
                print(f"  Request failed: {e}")
                break

            print(f"  HTTP {resp.status_code}, body length: {len(resp.text)}")
            print(f"  Body preview: {resp.text[:300]!r}")
            if not resp.is_success or not resp.text.strip():
                print("  Empty or error response — done")
                break

            page_jobs = parse_guest_listing_html(resp.text)
            new_jobs = [j for j in page_jobs if j["url"] not in seen_urls]
            print(f"  Cards: {len(page_jobs)}, new: {len(new_jobs)}")

            if not new_jobs:
                print("  No new jobs — done")
                break

            for j in new_jobs:
                seen_urls.add(j["url"])
            all_jobs.extend(new_jobs)
            print(f"  Running total: {len(all_jobs)}")

            await asyncio.sleep(1.0)

    return all_jobs


def _extract_element_html(html: str, tag_end: int) -> str:
    """Extract inner HTML by matching the closing tag (avoids bleeding into sibling elements)."""
    tag_match = re.search(r"<(\w+)[^>]*$", html[: tag_end + 1])
    tag_name = tag_match.group(1).lower() if tag_match else "div"
    open_re = re.compile(f"<{tag_name}[\\s>]", re.IGNORECASE)
    close_re = re.compile(f"</{tag_name}>", re.IGNORECASE)
    depth, pos = 1, tag_end + 1
    while pos < len(html) and depth > 0:
        om = open_re.search(html, pos)
        cm = close_re.search(html, pos)
        if not cm:
            break
        if om and om.start() < cm.start():
            depth += 1
            pos = om.end()
        else:
            depth -= 1
            if depth == 0:
                return html[tag_end + 1 : cm.start()]
            pos = cm.end()
    return html[tag_end + 1 : tag_end + 12000]  # fallback


def _html_to_text(raw: str) -> str:
    raw = re.sub(r"<br\s*/?>", "\n", raw, flags=re.IGNORECASE)
    raw = re.sub(r"</(p|div|h[1-6]|section|article|tr)>", "\n", raw, flags=re.IGNORECASE)
    raw = re.sub(r"</li>", "\n", raw, flags=re.IGNORECASE)
    raw = re.sub(r"<li[^>]*>", "• ", raw, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", raw)
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&nbsp;", " ").replace("&#39;", "'").replace("&quot;", '"')
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    return text.strip()


def _extract_jd_text(html: str) -> str:
    """Extract job description text from LinkedIn job page HTML."""
    for marker in ("show-more-less-html__markup", "description__text", "job-details"):
        idx = html.find(marker)
        if idx == -1:
            continue
        tag_end = html.find(">", idx)
        if tag_end == -1:
            continue
        inner = _extract_element_html(html, tag_end)
        text = _html_to_text(inner)
        if len(text) > 100:
            return text
    return ""


async def fetch_job_detail(client: httpx.AsyncClient, job_url: str, is_easy_apply: bool) -> dict:
    """Fetch JD text from LinkedIn guest job posting API (server-rendered HTML, no JS needed)."""
    job_id = _extract_job_id(job_url)
    if not job_id:
        return {"jd_text": "", "ats_type": "unknown", "ats_url": "", "applicant_count": None}

    detail_url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
    try:
        resp = await client.get(detail_url)
        if not resp.is_success:
            return {"jd_text": "", "ats_type": "unknown", "ats_url": "", "applicant_count": None}

        html = resp.text
        lower = html.lower()

        if "no longer accepting" in lower or "not accepting applications" in lower:
            return {"closed": True, "jd_text": "", "ats_type": "unknown", "ats_url": "", "applicant_count": None}

        jd_text = _extract_jd_text(html)

        applicant_count: int | None = None
        count_m = re.search(r"([\d,]+)\s+applicant", html, re.IGNORECASE)
        if count_m:
            applicant_count = int(count_m.group(1).replace(",", ""))

        ats_type = "easy_apply" if is_easy_apply else "unknown"
        ats_url = job_url if is_easy_apply else ""

        return {
            "jd_text": jd_text,
            "ats_type": ats_type,
            "ats_url": ats_url,
            "applicant_count": applicant_count,
        }
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
    date_posted = config.get("date_posted", "past_week")
    blacklist = set(config.get("blacklist_companies", []))
    work_types = config.get("work_types", [])
    max_applicants: int | None = config.get("max_applicants")
    easy_apply_only = config.get("easy_apply_only", False)

    country = config.get("country", "")
    city = config.get("city", "")
    if city and country:
        location = f"{city}, {country}"
    elif country:
        location = country
    else:
        location = config.get("location", "Remote")

    if date_posted not in TIME_FILTER_MAP:
        print(f"  Warning: unknown date_posted '{date_posted}', defaulting to past_week")

    cookies = _build_cookies(load_cookies())

    print(f"Scraping LinkedIn for: {keywords} in {location}")
    print(f"  Date posted: {date_posted}")
    print(f"  Work types: {work_types or 'any'}")
    print(f"  Max applicants: {max_applicants if max_applicants is not None else 'any'}")
    print(f"  Easy Apply only: {easy_apply_only}")

    cards = await fetch_job_listings(
        keywords, location, date_posted, work_types, easy_apply_only, max_applicants,
        cookies=cookies,
    )
    print(f"Total cards collected: {len(cards)}")

    # Blacklist filter
    blacklist_lower = {b.lower() for b in blacklist}
    cards = [c for c in cards if c["company"].lower() not in blacklist_lower]

    # Title-level remote filter (catch leakage from LinkedIn's f_WT)
    if work_types and not any(wt in work_types for wt in ("onsite", "hybrid")):
        ONSITE_KEYWORDS = {
            "on-site", "onsite", "on site", "in-person", "in person",
            "hybrid", "office-based", "office based", "must be local",
        }
        before = len(cards)
        cards = [c for c in cards if not any(kw in c["title"].lower() for kw in ONSITE_KEYWORDS)]
        print(f"Remote title filter: {before} → {len(cards)} cards")

    enriched = []
    async with httpx.AsyncClient(headers=_HEADERS, cookies=cookies, timeout=30.0, follow_redirects=True) as client:
        for i, card in enumerate(cards[:50]):
            ea_flag = " [Easy Apply]" if card.get("is_easy_apply") else ""
            print(f"  [{i+1}/{min(len(cards), 50)}] {card['title']} @ {card['company']}{ea_flag}")

            detail = await fetch_job_detail(client, card["url"], is_easy_apply=card.get("is_easy_apply", False))

            if detail.get("closed"):
                print("    Skipping — no longer accepting applications")
                continue

            print(f"    ATS: {detail.get('ats_type', 'unknown')} | JD: {len(detail.get('jd_text', ''))} chars")
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
