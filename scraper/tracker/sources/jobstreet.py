"""JobStreet Malaysia (SEEK) search API, as used by my.jobstreet.com.

GET https://my.jobstreet.com/api/jobsearch/v5/search?siteKey=MY-Main&where=All Malaysia&keywords=intern

Portal results carry the advertiser's name; the pipeline keeps only those
that match a company on the MNC list.
"""

from __future__ import annotations

from .. import http
from ..models import Posting
from ..dates import iso_date

QUERIES = ["intern", "internship", "industrial training", "latihan industri"]
PAGE = 100
MAX_PAGES = 3
CLOSES_BY_ABSENCE = False


def _company(j: dict) -> str:
    adv = j.get("advertiser") or {}
    return j.get("companyName") or adv.get("description") or ""


def _location(j: dict) -> str:
    locs = j.get("locations")
    if isinstance(locs, list) and locs:
        return ", ".join(l.get("label") or "" for l in locs if isinstance(l, dict))
    return j.get("location") or j.get("suburb") or ""


def fetch(cfg: dict, company: str) -> list[Posting]:
    out: dict[str, Posting] = {}
    for q in cfg.get("queries") or QUERIES:
        for page in range(1, MAX_PAGES + 1):
            data = http.get_json("https://my.jobstreet.com/api/jobsearch/v5/search", params={
                "siteKey": "MY-Main", "where": "All Malaysia", "keywords": q,
                "page": page, "pageSize": PAGE, "sortmode": "ListedDate", "locale": "en-MY",
            })
            items = data.get("data") or []
            for j in items:
                jid = str(j.get("id"))
                out.setdefault(jid, Posting(
                    source="jobstreet",
                    native_id=jid,
                    company=_company(j),
                    title=j.get("title") or "",
                    location=_location(j) or "Malaysia",
                    country_code="MY",
                    apply_url=f"https://my.jobstreet.com/job/{jid}",
                    posted_at=iso_date(j.get("listingDate")),
                    description=" ".join(filter(None, [j.get("teaser"), " ".join(j.get("bulletPoints") or [])])),
                ))
            if len(items) < PAGE:
                break
    return list(out.values())
