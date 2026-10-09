"""SAP SuccessFactors Career Site Builder pages (e.g. jobs.sap.com).

These sites render search results as HTML:
  GET {base}/search/?q=intern&locationsearch=Malaysia&startrow=0
with rows like
  <tr class="data-row"> <a class="jobTitle-link" href="/job/Kuala-Lumpur-.../1234567/">Title</a>
  ... <span class="jobLocation">Kuala Lumpur, MY</span> ... <span class="jobDate">Oct 1, 2026</span>
"""

from __future__ import annotations

import html
import re

from .. import http
from ..models import Posting, strip_html
from ..dates import iso_date

QUERIES = ["intern", "internship", "industrial training"]
PAGE = 25
MAX_PAGES = 4
CLOSES_BY_ABSENCE = False

ROW_SPLIT_RE = re.compile(r'<tr[^>]*class="[^"]*data-row', re.I)
LINK_RE = re.compile(r'<a[^>]*href="([^"]*/job/[^"]+)"[^>]*class="[^"]*jobTitle-link[^"]*"[^>]*>(.*?)</a>'
                     r'|<a[^>]*class="[^"]*jobTitle-link[^"]*"[^>]*href="([^"]*/job/[^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
LOCATION_RE = re.compile(r'<span[^>]*class="[^"]*jobLocation[^"]*"[^>]*>(.*?)</span>', re.I | re.S)
DATE_RE = re.compile(r'<span[^>]*class="[^"]*jobDate[^"]*"[^>]*>(.*?)</span>', re.I | re.S)
ID_RE = re.compile(r"/(\d{5,})/?$")


def parse(page_html: str, base: str, company: str) -> list[Posting]:
    out = []
    for row in ROW_SPLIT_RE.split(page_html)[1:]:
        m = LINK_RE.search(row)
        if not m:
            continue
        href = html.unescape(m.group(1) or m.group(3))
        title = strip_html(m.group(2) or m.group(4))
        loc = LOCATION_RE.search(row)
        date = DATE_RE.search(row)
        idm = ID_RE.search(href)
        out.append(Posting(
            source=f"successfactors:{company}",
            native_id=idm.group(1) if idm else href,
            company=company,
            title=title,
            location=strip_html(loc.group(1)) if loc else "",
            apply_url=href if href.startswith("http") else base.rstrip("/") + href,
            posted_at=iso_date(strip_html(date.group(1))) if date else None,
        ))
    return out


def fetch(cfg: dict, company: str) -> list[Posting]:
    base = cfg["base_url"].rstrip("/")
    found: dict[str, Posting] = {}
    for q in cfg.get("queries") or QUERIES:
        for page in range(MAX_PAGES):
            text = http.get_text(f"{base}/search/", params={
                "q": q, "locationsearch": cfg.get("locationsearch", "Malaysia"), "startrow": page * PAGE,
            })
            rows = parse(text, base, company)
            for p in rows:
                found.setdefault(p.native_id, p)
            if len(rows) < PAGE:
                break
    return list(found.values())
