"""Persistent job list (public/data/jobs.json), merged run by run.

- New postings get `first_seen` = now; the web page uses it for "new" alerts.
- A company-site posting missing from 2 successful fetches in a row is marked
  closed. Portal / keyword-search postings close after 21 days unseen.
- Closed postings are pruned 45 days after closing.
- The same job found on a portal and on the company site is merged; the
  company-site apply link wins.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
from pathlib import Path

MISSING_RUNS_TO_CLOSE = 2
UNSEEN_DAYS_TO_CLOSE = 21
PRUNE_CLOSED_AFTER_DAYS = 45


def job_id(source: str, native_id: str) -> str:
    return hashlib.sha1(f"{source}|{native_id}".encode()).hexdigest()[:12]


def _title_key(title: str) -> frozenset[str]:
    words = re.findall(r"[a-z0-9]+", title.lower())
    stop = {"intern", "internship", "interns", "the", "and", "of", "for", "a", "in", "malaysia", "student"}
    return frozenset(w for w in words if w not in stop and not re.fullmatch(r"20\d\d", w))


def _similar(a: str, b: str) -> bool:
    ka, kb = _title_key(a), _title_key(b)
    if not ka or not kb:
        return ka == kb
    return len(ka & kb) / len(ka | kb) >= 0.75


class Store:
    def __init__(self, path: Path):
        self.path = path
        self.jobs: dict[str, dict] = {}
        if path.exists():
            data = json.loads(path.read_text() or "{}")
            self.jobs = {j["id"]: j for j in data.get("jobs", [])}
        self._original = self.dump()

    # ------------------------------------------------------------------ upsert

    def _find_duplicate(self, rec: dict) -> dict | None:
        for j in self.jobs.values():
            if j["id"] != rec["id"] and j["company"] == rec["company"] and j["active"] \
                    and j["source_kind"] != rec["source_kind"] and _similar(j["title"], rec["title"]):
                return j
        return None

    def upsert(self, rec: dict, now: dt.datetime) -> str:
        """Insert or refresh a matched posting. Returns 'new', 'updated' or 'merged'."""
        today = now.date().isoformat()
        existing = self.jobs.get(rec["id"])
        if existing is None:
            dup = self._find_duplicate(rec)
            if dup is not None:
                return self._merge(dup, rec, today)
            rec.update(first_seen=now.isoformat(timespec="minutes"), last_seen=today,
                       active=True, closed_at=None, missing_runs=0, also_on=[])
            self.jobs[rec["id"]] = rec
            return "new"
        for key in ("title", "category", "classified_by", "location", "city_group", "duration",
                    "snippet", "company_type", "posted_at"):
            if rec.get(key) is not None:
                existing[key] = rec[key]
        existing["apply_url"] = rec["apply_url"]
        existing.update(last_seen=today, active=True, closed_at=None, missing_runs=0)
        return "updated"

    def _merge(self, dup: dict, rec: dict, today: str) -> str:
        """Same job from another source: keep one entry, prefer the company-site link."""
        if rec["source_kind"] == "company":
            primary, secondary = rec, dup
            rec.update(first_seen=dup["first_seen"], last_seen=today, active=True,
                       closed_at=None, missing_runs=0, also_on=[])
            del self.jobs[dup["id"]]
            self.jobs[rec["id"]] = rec
        else:
            primary, secondary = dup, rec
            dup["last_seen"] = today
        links = {a["source"]: a for a in primary.get("also_on", [])}
        for a in [{"source": secondary["source"], "url": secondary["apply_url"]}, *secondary.get("also_on", [])]:
            if a["source"] != primary["source"]:
                links[a["source"]] = a
        primary["also_on"] = sorted(links.values(), key=lambda a: a["source"])
        return "merged"

    # ------------------------------------------------------------------ closing

    def close_missing(self, source: str, seen_ids: set[str], closes_by_absence: bool, now: dt.datetime) -> None:
        """Called after a *successful* fetch of `source`."""
        today = now.date()
        for j in self.jobs.values():
            if j["source"] != source or not j["active"] or j["id"] in seen_ids:
                continue
            if closes_by_absence:
                j["missing_runs"] = j.get("missing_runs", 0) + 1
                if j["missing_runs"] >= MISSING_RUNS_TO_CLOSE:
                    j.update(active=False, closed_at=today.isoformat())
            elif (today - dt.date.fromisoformat(j["last_seen"])).days >= UNSEEN_DAYS_TO_CLOSE:
                j.update(active=False, closed_at=today.isoformat())

    def prune(self, now: dt.datetime) -> None:
        cutoff = now.date() - dt.timedelta(days=PRUNE_CLOSED_AFTER_DAYS)
        self.jobs = {k: j for k, j in self.jobs.items()
                     if j["active"] or not j.get("closed_at") or dt.date.fromisoformat(j["closed_at"]) > cutoff}

    # ------------------------------------------------------------------ output

    def dump(self) -> str:
        jobs = sorted(self.jobs.values(), key=lambda j: (j["first_seen"], j["id"]), reverse=True)
        return json.dumps({"jobs": jobs}, indent=1, ensure_ascii=False, sort_keys=True) + "\n"

    @property
    def changed(self) -> bool:
        return self.dump() != self._original

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(self.dump())
