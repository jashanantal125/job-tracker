"""Eightfold.ai career sites: GET https://{host}/api/apply/v2/jobs?domain=...&query=...&location=Malaysia"""

from __future__ import annotations

from .. import http
from ..models import Posting, strip_html
from ..dates import iso_date

QUERIES = ["intern", "internship"]
PAGE = 10
MAX_PAGES = 6
CLOSES_BY_ABSENCE = False


def fetch(cfg: dict, company: str) -> list[Posting]:
    host, domain = cfg["host"], cfg["domain"]
    out: dict[str, Posting] = {}
    for q in cfg.get("queries") or QUERIES:
        for page in range(MAX_PAGES):
            data = http.get_json(f"https://{host}/api/apply/v2/jobs", params={
                "domain": domain, "query": q, "location": "Malaysia",
                "start": page * PAGE, "num": PAGE, "sort_by": "timestamp",
            })
            positions = data.get("positions") or []
            for j in positions:
                jid = str(j.get("id"))
                out.setdefault(jid, Posting(
                    source=f"eightfold:{company}",
                    native_id=jid,
                    company=company,
                    title=j.get("name") or "",
                    location=j.get("location") or "",
                    extra_locations=list(j.get("locations") or []),
                    apply_url=j.get("canonicalPositionUrl") or f"https://{host}/careers/job/{jid}",
                    posted_at=iso_date(j.get("t_create")),
                    description=strip_html(j.get("job_description")),
                ))
            if len(positions) < PAGE or (page + 1) * PAGE >= (data.get("count") or 0):
                break
    return list(out.values())
