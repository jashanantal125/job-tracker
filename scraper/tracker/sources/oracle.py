"""Oracle Recruiting Cloud (Oracle HCM "CandidateExperience" sites).

GET https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions
    ?onlyData=true&expand=requisitionList.secondaryLocations
    &finder=findReqs;siteNumber={site},keyword="intern",limit=25,offset=0,sortBy=POSTING_DATES_DESC
"""

from __future__ import annotations

import urllib.parse

from .. import http
from ..models import Posting
from ..dates import iso_date

QUERIES = ["intern", "internship", "industrial training", "trainee"]
PAGE = 25
MAX_PAGES = 8
CLOSES_BY_ABSENCE = False  # keyword searches, not a full listing


def _page(host: str, site: str, keyword: str, offset: int) -> dict:
    finder = (f'findReqs;siteNumber={site},keyword="{keyword}",limit={PAGE},'
              f"offset={offset},sortBy=POSTING_DATES_DESC")
    url = (f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
           f"?onlyData=true&expand=requisitionList.secondaryLocations"
           f"&finder={urllib.parse.quote(finder, safe='=;,')}")
    data = http.get_json(url)
    items = data.get("items") or [{}]
    return items[0]


def fetch(cfg: dict, company: str) -> list[Posting]:
    host, site = cfg["host"], cfg["site"]
    out: dict[str, Posting] = {}
    for q in cfg.get("queries") or QUERIES:
        for page in range(MAX_PAGES):
            block = _page(host, site, q, page * PAGE)
            reqs = block.get("requisitionList") or []
            for r in reqs:
                rid = str(r.get("Id"))
                if rid in out:
                    continue
                secondary = [s.get("Name") or "" for s in r.get("secondaryLocations") or []]
                codes = {r.get("PrimaryLocationCountry")} | {s.get("CountryCode") for s in r.get("secondaryLocations") or []}
                out[rid] = Posting(
                    source=f"oracle:{company}",
                    native_id=rid,
                    company=company,
                    title=r.get("Title") or "",
                    location=r.get("PrimaryLocation") or "",
                    extra_locations=secondary,
                    country_code="MY" if "MY" in codes else None,
                    apply_url=f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}/job/{rid}",
                    posted_at=iso_date(r.get("PostedDate")),
                    description=r.get("ShortDescriptionStr") or "",
                )
            if len(reqs) < PAGE or (page + 1) * PAGE >= (block.get("TotalJobsCount") or 0):
                break
    return list(out.values())
