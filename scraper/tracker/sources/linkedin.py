"""LinkedIn public (logged-out) job search, best effort.

GET https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search
    ?keywords=intern&location=Malaysia&geoId=106808692&f_JT=I&f_TPR=r604800&start=0

f_JT=I is the "Internship" job type, f_TPR=r604800 limits to the past week.
LinkedIn rate-limits heavily (HTTP 429), so this source is expected to fail
sometimes; that never removes jobs already found.
"""

from __future__ import annotations

import html
import re

from .. import http
from ..models import Posting, strip_html
from ..dates import iso_date

QUERIES = ["", "software", "data", "consulting", "product", "cloud"]
PAGE = 25
MAX_PAGES = 2
CLOSES_BY_ABSENCE = False

CARD_SPLIT_RE = re.compile(r"<li[\s>]", re.I)
URN_RE = re.compile(r"urn:li:jobPosting:(\d+)")
URL_RE = re.compile(r'class="[^"]*base-card__full-link[^"]*"[^>]*href="([^"]+)"|href="([^"]+)"[^>]*class="[^"]*base-card__full-link', re.I)
TITLE_RE = re.compile(r'class="[^"]*base-search-card__title[^"]*"[^>]*>(.*?)</h3>', re.I | re.S)
COMPANY_RE = re.compile(r'class="[^"]*base-search-card__subtitle[^"]*"[^>]*>(.*?)</h4>', re.I | re.S)
LOCATION_RE = re.compile(r'class="[^"]*job-search-card__location[^"]*"[^>]*>(.*?)</span>', re.I | re.S)
DATE_RE = re.compile(r'<time[^>]*datetime="([^"]+)"', re.I)
JOB_ID_IN_URL_RE = re.compile(r"-(\d{6,})(?:\?|$)")


def parse(page_html: str) -> list[Posting]:
    out = []
    for card in CARD_SPLIT_RE.split(page_html)[1:]:
        title = TITLE_RE.search(card)
        if not title:
            continue
        url_m = URL_RE.search(card)
        url = html.unescape((url_m.group(1) or url_m.group(2))) if url_m else ""
        jid_m = URN_RE.search(card) or JOB_ID_IN_URL_RE.search(url.split("?")[0] + "?")
        if not jid_m:
            continue
        jid = jid_m.group(1)
        company = COMPANY_RE.search(card)
        loc = LOCATION_RE.search(card)
        date = DATE_RE.search(card)
        out.append(Posting(
            source="linkedin",
            native_id=jid,
            company=strip_html(company.group(1)) if company else "",
            title=strip_html(title.group(1)),
            location=strip_html(loc.group(1)) if loc else "",
            apply_url=f"https://www.linkedin.com/jobs/view/{jid}/",
            posted_at=iso_date(date.group(1)) if date else None,
        ))
    return out


def fetch(cfg: dict, company: str) -> list[Posting]:
    out: dict[str, Posting] = {}
    for q in cfg.get("queries") or QUERIES:
        for page in range(MAX_PAGES):
            text = http.get_text(
                "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search",
                params={"keywords": q, "location": "Malaysia", "geoId": "106808692",
                        "f_JT": "I", "f_TPR": "r604800", "start": page * PAGE},
                retries=0,
            )
            cards = parse(text)
            for p in cards:
                out.setdefault(p.native_id, p)
            if len(cards) < PAGE:
                break
    return list(out.values())
