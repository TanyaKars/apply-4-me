"""Detect ATS type from a job application URL."""
from typing import Optional


ATS_PATTERNS = {
    "greenhouse": [
        "boards.greenhouse.io",
        "greenhouse.io/embed",
        "grnh.se",
    ],
    "lever": [
        "jobs.lever.co",
        "lever.co/",
    ],
    "ashby": [
        "jobs.ashbyhq.com",
        "ashbyhq.com",
        "app.ashbyhq.com",
    ],
    "workday": [
        "myworkdayjobs.com",
        "workday.com/en-us/applications",
    ],
}


def detect_ats(url: str) -> str:
    """Return ATS type string from URL."""
    if not url:
        return "unknown"
    url_lower = url.lower()
    for ats_type, patterns in ATS_PATTERNS.items():
        for pattern in patterns:
            if pattern in url_lower:
                return ats_type
    return "unknown"


def get_adapter(ats_type: str):
    """Return the appropriate adapter class."""
    from pw.ats.greenhouse import GreenhouseAdapter
    from pw.ats.lever import LeverAdapter
    from pw.ats.ashby import AshbyAdapter

    adapters = {
        "greenhouse": GreenhouseAdapter,
        "lever": LeverAdapter,
        "ashby": AshbyAdapter,
    }
    return adapters.get(ats_type)
