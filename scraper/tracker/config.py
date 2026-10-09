from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "companies.toml"

COMPANY_TYPES = {
    "tech": "Tech",
    "consulting": "Consulting & IT Services",
    "semicon": "Semiconductor & Hardware",
    "gbs": "Banking, Energy & GBS Hubs",
    "malaysian": "Malaysian MNC",
}


@dataclass
class Company:
    name: str
    type: str
    aliases: list[str]
    careers: str = ""
    ats: dict | None = None
    patterns: list[re.Pattern] = field(default_factory=list, repr=False)


_SUFFIX_RE = re.compile(
    r"\b(sdn|bhd|berhad|sendirian|malaysia|\(m\)|m|ltd|limited|inc|incorporated|corporation|corp|"
    r"co|plc|llc|llp|pte|pvt|group|holdings?|global|services|the)\b")


def normalize(name: str) -> str:
    s = (name or "").lower().replace("&", " and ")
    s = re.sub(r"[^a-z0-9()+ ]+", " ", s)
    s = _SUFFIX_RE.sub(" ", s)
    s = s.replace("(", " ").replace(")", " ")
    return re.sub(r"\s+", " ", s).strip()


def load(path: Path = CONFIG_PATH) -> tuple[list[Company], list[dict]]:
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    companies = []
    for c in raw.get("company", []):
        if c.get("type") not in COMPANY_TYPES:
            raise ValueError(f"{c.get('name')}: unknown type {c.get('type')!r}")
        aliases = [c["name"], *c.get("aliases", [])]
        comp = Company(name=c["name"], type=c["type"], aliases=aliases,
                       careers=c.get("careers", ""), ats=c.get("ats"))
        comp.patterns = [re.compile(rf"\b{re.escape(normalize(a))}\b") for a in aliases if normalize(a)]
        companies.append(comp)
    return companies, raw.get("portal", [])


class CompanyMatcher:
    """Maps a free-text employer name (from a job portal) to a tracked company."""

    def __init__(self, companies: list[Company]):
        self.companies = companies

    def match(self, employer: str) -> Company | None:
        norm = normalize(employer)
        if not norm:
            return None
        best, best_len = None, 0
        for c in self.companies:
            for rx in c.patterns:
                if rx.search(norm) and len(rx.pattern) > best_len:
                    best, best_len = c, len(rx.pattern)
        return best
