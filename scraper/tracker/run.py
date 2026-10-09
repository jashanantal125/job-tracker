"""One tracker run: fetch every source, filter, merge into the store, write JSON for the site."""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

from . import config, filters, http
from .models import Posting
from .sources import ADAPTERS, PORTALS
from .store import Store, job_id

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "public" / "data"
HEALTH_REFRESH = dt.timedelta(hours=3)


def build_tasks(companies: list[config.Company], portals: list[dict], only: str | None) -> list[tuple]:
    tasks = []
    for c in companies:
        if c.ats and c.ats.get("enabled", True):
            tasks.append((f"{c.ats['kind']}:{c.name}", c.ats, c))
    for p in portals:
        if p.get("enabled", True):
            tasks.append((p["kind"], p, None))
    if only:
        tasks = [t for t in tasks if only.lower() in t[0].lower()]
    return tasks


def run_source(name: str, cfg: dict, company: config.Company | None) -> tuple[list[Posting], float]:
    start = time.monotonic()
    postings = ADAPTERS[cfg["kind"]].fetch(cfg, company.name if company else "")
    return postings, time.monotonic() - start


def to_record(p: Posting, company: config.Company, m, kind: str) -> dict:
    snippet = p.description[:280].rsplit(" ", 1)[0] + "…" if len(p.description) > 280 else p.description
    location = p.location if filters.is_malaysia(p.location) else \
        next((l for l in p.extra_locations if filters.is_malaysia(l)), p.location or "Malaysia")
    return {
        "id": job_id(p.source, p.native_id),
        "source": p.source,
        "source_kind": "portal" if kind in PORTALS else "company",
        "company": company.name,
        "company_type": config.COMPANY_TYPES[company.type],
        "title": p.title.strip(),
        "category": m.category,
        "classified_by": m.classified_by,
        "duration": m.duration,
        "location": location,
        "city_group": filters.city_group(location),
        "apply_url": p.apply_url,
        "posted_at": p.posted_at,
        "snippet": snippet,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fetch Malaysian MNC tech internships.")
    ap.add_argument("--deadline", type=float, default=float(os.environ.get("TRACKER_DEADLINE", 42)),
                    help="seconds before unfinished sources are abandoned")
    ap.add_argument("--workers", type=int, default=24)
    ap.add_argument("--only", help="run only sources whose name contains this text")
    ap.add_argument("--data-dir", type=Path, default=DATA_DIR)
    ap.add_argument("--dry-run", action="store_true", help="print matches, don't write files")
    args = ap.parse_args(argv)

    now = dt.datetime.now(dt.timezone.utc)
    companies, portals = config.load()
    matcher = config.CompanyMatcher(companies)
    by_name = {c.name: c for c in companies}
    tasks = build_tasks(companies, portals, args.only)

    store = Store(args.data_dir / "jobs.json")
    health_path = args.data_dir / "health.json"
    old_health = json.loads(health_path.read_text()) if health_path.exists() else {}

    http.set_deadline(args.deadline)
    health: list[dict] = []
    events = Counter()

    pool = cf.ThreadPoolExecutor(max_workers=args.workers)
    futures = {pool.submit(run_source, *t): t for t in tasks}
    done, not_done = cf.wait(futures, timeout=args.deadline + 5)
    pool.shutdown(wait=False, cancel_futures=True)

    for fut in done | not_done:
        name, cfg, company = futures[fut]
        kind = cfg["kind"]
        entry = {"source": name, "kind": kind, "company": company.name if company else None,
                 "ok": False, "fetched": 0, "matched": 0, "error": None, "seconds": None}
        health.append(entry)
        if fut in not_done:
            entry["error"] = "timed out (run deadline)"
            continue
        try:
            postings, secs = fut.result()
        except Exception as e:  # noqa: BLE001 - one broken source must not stop the run
            entry["error"] = f"{type(e).__name__}: {e}"[:300]
            continue
        entry.update(ok=True, fetched=len(postings), seconds=round(secs, 1))
        reasons = Counter()
        seen: set[str] = set()
        for p in postings:
            comp = company or matcher.match(p.company)
            if comp is None:
                reasons["not an MNC"] += 1
                continue
            m, reason = filters.evaluate(p)
            reasons[reason] += 1
            if not m:
                continue
            rec = to_record(p, comp, m, kind)
            seen.add(rec["id"])
            events[store.upsert(rec, now)] += 1
            if args.dry_run:
                print(f"  [{m.category}] {comp.name}: {p.title} — {rec['location']}\n    {p.apply_url}")
        entry["matched"] = reasons.pop("matched", 0)
        entry["rejected"] = dict(reasons)
        store.close_missing(name, seen, getattr(ADAPTERS[kind], "CLOSES_BY_ABSENCE", False), now)

    store.prune(now)
    health.sort(key=lambda h: (h["ok"], h["source"]))
    active = [j for j in store.jobs.values() if j["active"]]
    watchlist = [{"company": c.name, "type": config.COMPANY_TYPES[c.type], "careers": c.careers,
                  "tracked": bool(c.ats and c.ats.get("enabled", True))} for c in companies]
    summary = {
        "checked_at": now.isoformat(timespec="minutes"),
        "sources_ok": sum(h["ok"] for h in health),
        "sources_failed": sum(not h["ok"] for h in health),
        "active_jobs": len(active),
        "new_this_run": events["new"],
        "sources": health,
        "companies": sorted(watchlist, key=lambda w: w["company"].lower()),
    }

    print(f"{summary['sources_ok']} sources ok, {summary['sources_failed']} failed, "
          f"{events['new']} new, {len(active)} active", file=sys.stderr)
    for h in health:
        if not h["ok"]:
            print(f"  FAIL {h['source']}: {h['error']}", file=sys.stderr)

    if args.dry_run:
        return 0

    # Only touch files when something meaningful changed, so the scheduled
    # workflow doesn't create a commit (and a Vercel deploy) every 30 minutes.
    old_failed = {h["source"] for h in old_health.get("sources", []) if not h["ok"]}
    new_failed = {h["source"] for h in health if not h["ok"]}
    old_checked = old_health.get("checked_at")
    stale = not old_checked or now - dt.datetime.fromisoformat(old_checked) >= HEALTH_REFRESH
    changed = store.changed or (not args.only and (old_failed != new_failed or stale))
    if changed:
        store.save()
        if not args.only:  # a partial run must not overwrite the full health report
            health_path.write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n")
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"changed={'true' if changed else 'false'}\nnew={events['new']}\n")
    return 0
