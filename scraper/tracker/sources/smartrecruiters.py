"""SmartRecruiters: GET https://api.smartrecruiters.com/v1/companies/{id}/postings?country=my"""

from __future__ import annotations

from .. import filters, http
from ..models import Posting, strip_html
from ..dates import iso_date

API = "https://api.smartrecruiters.com/v1/companies"
PAGE = 100
CLOSES_BY_ABSENCE = True


def fetch(cfg: dict, company: str) -> list[Posting]:
    cid = cfg["id"]
    out, offset = [], 0
    while True:
        data = http.get_json(f"{API}/{cid}/postings", params={"country": "my", "limit": PAGE, "offset": offset})
        items = data.get("content") or []
        for j in items:
            loc = j.get("location") or {}
            p = Posting(
                source=f"smartrecruiters:{company}",
                native_id=str(j["id"]),
                company=company,
                title=j.get("name") or "",
                location=", ".join(x for x in [loc.get("city"), loc.get("region"), (loc.get("country") or "").upper()] if x),
                country_code=(loc.get("country") or "").upper() or None,
                apply_url=f"https://jobs.smartrecruiters.com/{cid}/{j['id']}",
                posted_at=iso_date(j.get("releasedDate")),
                description=" ".join(filter(None, [
                    (j.get("typeOfEmployment") or {}).get("label"),
                    (j.get("experienceLevel") or {}).get("label"),
                ])),
            )
            if filters.title_prefilter(p.title):
                try:
                    d = http.get_json(f"{API}/{cid}/postings/{j['id']}", retries=1)
                    sections = (d.get("jobAd") or {}).get("sections") or {}
                    p.description += " " + " ".join(strip_html((s or {}).get("text")) for s in sections.values())
                    p.apply_url = d.get("postingUrl") or p.apply_url
                except http.HttpError:
                    pass
            out.append(p)
        offset += PAGE
        if not items or offset >= (data.get("totalFound") or 0):
            break
    return out
