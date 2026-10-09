"""Greenhouse job boards: GET https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true"""

from __future__ import annotations

from .. import http
from ..models import Posting, strip_html
from ..dates import iso_date

CLOSES_BY_ABSENCE = True


def fetch(cfg: dict, company: str) -> list[Posting]:
    board = cfg["board"]
    data = http.get_json(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs", params={"content": "true"})
    out = []
    for j in data.get("jobs") or []:
        offices = [o.get("location") or o.get("name") or "" for o in j.get("offices") or []]
        out.append(Posting(
            source=f"greenhouse:{company}",
            native_id=str(j["id"]),
            company=company,
            title=j.get("title") or "",
            location=(j.get("location") or {}).get("name") or "",
            extra_locations=[o for o in offices if o],
            apply_url=j.get("absolute_url") or "",
            posted_at=iso_date(j.get("first_published") or j.get("updated_at")),
            description=strip_html(j.get("content")),
        ))
    return out
