"""Workday career sites (https://{tenant}.wdN.myworkdayjobs.com/{site}).

Uses the JSON endpoint the career site itself calls:
  POST https://{host}/wday/cxs/{tenant}/{site}/jobs
  GET  https://{host}/wday/cxs/{tenant}/{site}{externalPath}   (job detail)

Strategy: read the facets once, find the Malaysia location values, then list
every Malaysian job (usually a few pages) and filter locally. If no Malaysia
facet exists, fall back to keyword searches.
"""

from __future__ import annotations

from .. import filters, http
from ..models import Posting, strip_html
from ..dates import iso_date, relative_date

PAGE = 20
MAX_JOBS = 600
FALLBACK_QUERIES = ["intern", "internship", "industrial training", "trainee"]
CLOSES_BY_ABSENCE = True


def _walk_facets(facets, out):
    for f in facets or []:
        param = f.get("facetParameter")
        for v in f.get("values") or []:
            if "facetParameter" in v:  # nested facet group
                _walk_facets([v], out)
            elif param:
                out.append((param, f.get("descriptor") or "", v))


def malaysia_facets(facets) -> dict[str, list[str]]:
    flat: list = []
    _walk_facets(facets, flat)
    by_param: dict[str, list[str]] = {}
    for param, _desc, v in flat:
        label = v.get("descriptor") or ""
        if v.get("id") and filters.is_malaysia(label):
            by_param.setdefault(param, []).append(v["id"])
    if not by_param:
        return {}
    # Facets in different params are AND-ed, so use exactly one: prefer country.
    for param in by_param:
        if "country" in param.lower():
            return {param: by_param[param]}
    best = max(by_param, key=lambda k: len(by_param[k]))
    return {best: by_param[best]}


def _list(base: str, applied: dict, text: str) -> list[dict]:
    out, offset, total = [], 0, None
    while offset < MAX_JOBS:
        data = http.post_json(f"{base}/jobs", {
            "appliedFacets": applied, "limit": PAGE, "offset": offset, "searchText": text,
        })
        posts = data.get("jobPostings") or []
        if total is None:  # Workday only reports the total on the first page
            total = data.get("total") or 0
        out.extend(posts)
        offset += PAGE
        if not posts or offset >= total:
            break
    return out


def _detail(base: str, path: str) -> dict:
    try:
        return http.get_json(f"{base}{path}", retries=1).get("jobPostingInfo") or {}
    except http.HttpError:
        return {}


def fetch(cfg: dict, company: str) -> list[Posting]:
    host, tenant = cfg["host"], cfg["tenant"]
    sites = cfg.get("sites") or [cfg["site"]]
    results: dict[str, Posting] = {}

    for site in sites:
        base = f"https://{host}/wday/cxs/{tenant}/{site}"
        first = http.post_json(f"{base}/jobs", {"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""})
        applied = malaysia_facets(first.get("facets"))
        raw: list[dict] = []
        if applied:
            raw = _list(base, applied, "")
        else:
            for q in FALLBACK_QUERIES:
                raw.extend(_list(base, {}, q))

        for j in raw:
            path = j.get("externalPath")
            title = j.get("title") or ""
            if not path or path in results:
                continue
            bullets = j.get("bulletFields") or []
            p = Posting(
                source=f"workday:{company}",
                native_id=bullets[0] if bullets else path,
                company=company,
                title=title,
                location=j.get("locationsText") or "",
                apply_url=f"https://{host}/en-US/{site}{path}",
                posted_at=relative_date(j.get("postedOn") or ""),
                country_code="MY" if applied else None,
            )
            if filters.title_prefilter(title):
                info = _detail(base, path)
                if info:
                    p.description = strip_html(info.get("jobDescription"))
                    p.location = info.get("location") or p.location
                    p.extra_locations = list(info.get("additionalLocations") or [])
                    country = (info.get("country") or {}).get("descriptor") or ""
                    if filters.is_malaysia(country):
                        p.country_code = "MY"
                    p.posted_at = iso_date(info.get("startDate")) or p.posted_at
                    p.apply_url = info.get("externalUrl") or p.apply_url
            results[path] = p
    return list(results.values())
