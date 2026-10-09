"""Source adapters.

Each adapter module exposes `fetch(cfg: dict, company: str) -> list[Posting]`.
`cfg` is the `[company.ats]` / `[[portal]]` table from config/companies.toml.

`CLOSES_BY_ABSENCE` says whether a posting missing from a successful fetch
means it was taken down (true for full company listings, false for portal
searches limited to recent results).
"""

from __future__ import annotations

from . import amazon, eightfold, greenhouse, jobstreet, lever, linkedin, oracle, smartrecruiters, successfactors, workday

ADAPTERS = {
    "workday": workday,
    "greenhouse": greenhouse,
    "lever": lever,
    "smartrecruiters": smartrecruiters,
    "oracle": oracle,
    "successfactors": successfactors,
    "eightfold": eightfold,
    "amazon": amazon,
    "jobstreet": jobstreet,
    "linkedin": linkedin,
}

PORTALS = {"jobstreet", "linkedin"}
