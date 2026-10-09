"""Lever postings: GET https://api.lever.co/v0/postings/{site}?mode=json  (api.eu.lever.co for EU)"""

from __future__ import annotations

from .. import http
from ..models import Posting
from ..dates import iso_date

CLOSES_BY_ABSENCE = True


def fetch(cfg: dict, company: str) -> list[Posting]:
    host = "api.eu.lever.co" if cfg.get("region") == "eu" else "api.lever.co"
    data = http.get_json(f"https://{host}/v0/postings/{cfg['site']}", params={"mode": "json"})
    out = []
    for j in data or []:
        cats = j.get("categories") or {}
        lists = " ".join(
            f"{li.get('text', '')} {li.get('content', '')}" for li in j.get("lists") or [])
        out.append(Posting(
            source=f"lever:{company}",
            native_id=j["id"],
            company=company,
            title=j.get("text") or "",
            location=cats.get("location") or "",
            extra_locations=list(cats.get("allLocations") or []),
            country_code=j.get("country"),
            apply_url=j.get("hostedUrl") or j.get("applyUrl") or "",
            posted_at=iso_date(j.get("createdAt")),
            description=f"{j.get('descriptionPlain') or ''} {cats.get('commitment') or ''} {lists}",
        ))
    return out
