"""Amazon / AWS: GET https://www.amazon.jobs/en/search.json?base_query=intern&loc_query=Malaysia&country=MYS"""

from __future__ import annotations

from .. import http
from ..models import Posting, strip_html
from ..dates import iso_date

QUERIES = ["intern", "internship"]
CLOSES_BY_ABSENCE = False


def fetch(cfg: dict, company: str) -> list[Posting]:
    out: dict[str, Posting] = {}
    for q in cfg.get("queries") or QUERIES:
        data = http.get_json("https://www.amazon.jobs/en/search.json", params={
            "base_query": q, "loc_query": "Malaysia", "country": "MYS",
            "result_limit": 100, "offset": 0, "sort": "recent",
        })
        for j in data.get("jobs") or []:
            jid = str(j.get("id_icims") or j.get("id"))
            out.setdefault(jid, Posting(
                source=f"amazon:{company}",
                native_id=jid,
                company=company,
                title=j.get("title") or "",
                location=j.get("normalized_location") or j.get("location") or "",
                country_code=j.get("country_code"),
                apply_url="https://www.amazon.jobs" + (j.get("job_path") or f"/en/jobs/{jid}"),
                posted_at=iso_date(j.get("posted_date")),
                description=strip_html(" ".join(filter(None, [
                    j.get("description_short"), j.get("description"), j.get("basic_qualifications")]))),
            ))
    return list(out.values())
