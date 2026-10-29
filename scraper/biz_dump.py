"""One-off: dump every Malaysian internship (all functions) from tracker sources as TSV."""
import concurrent.futures as cf
import sys

from tracker import config, filters, http
from tracker.run import build_tasks
from tracker.sources import ADAPTERS

QUERIES = {
    "linkedin": ["intern", "strategy", "business analyst", "product", "project", "management trainee",
                 "consulting", "business", "operations", "commercial", "transformation", "planning"],
    "jobstreet": ["intern", "internship", "strategy intern", "business analyst intern", "product intern",
                  "project intern", "management intern", "consulting intern", "business intern"],
}

_get_text = http.get_text
def get_text(url, params=None, **kw):
    if params and "f_TPR" in params:
        params = {**params, "f_TPR": "r1209600"}  # 14 days
    return _get_text(url, params=params, **kw)
http.get_text = get_text

companies, portals = config.load()
for p in portals:
    if p["kind"] in QUERIES:
        p["queries"] = QUERIES[p["kind"]]
matcher = config.CompanyMatcher(companies)
tasks = build_tasks(companies, portals, None)
http.set_deadline(240)

def go(t):
    name, cfg, comp = t
    return t, ADAPTERS[cfg["kind"]].fetch(cfg, comp.name if comp else "")

rows = set()
with cf.ThreadPoolExecutor(24) as pool:
    futs = [pool.submit(go, t) for t in tasks]
    for f in cf.as_completed(futs, timeout=280):
        try:
            (name, cfg, comp), ps = f.result()
        except Exception as e:  # noqa: BLE001
            print(f"FAIL\t{e}"[:200], file=sys.stderr)
            continue
        for p in ps:
            c = comp or matcher.match(p.company)
            if not filters.is_malaysia(p.location, p.country_code, p.extra_locations):
                continue
            ok, dur = filters.internship_duration(p.title, p.description)
            if not ok and not filters.INTERN_RE.search(p.title):
                continue
            desc = " ".join(p.description.split())[:350].replace("\t", " ")
            rows.add("\t".join(str(x) for x in [
                "ROW", p.posted_at or "", "MNC" if c else "other", c.name if c else p.company,
                p.title.strip(), p.location, dur or "", p.apply_url, desc]))
for r in sorted(rows, key=lambda r: r.split("\t")[1], reverse=True):
    print(r)
print(f"{len(rows)} rows", file=sys.stderr)
