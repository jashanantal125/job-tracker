from __future__ import annotations

import html
import re
from dataclasses import dataclass, field


@dataclass
class Posting:
    """A raw job posting as returned by one source, before filtering."""

    source: str  # e.g. "workday:Intel" or "jobstreet"
    native_id: str
    company: str  # canonical name for company sources, raw advertiser name for portals
    title: str
    location: str
    apply_url: str
    posted_at: str | None = None  # ISO date (YYYY-MM-DD) when known
    description: str = ""
    country_code: str | None = None  # "MY" when the source says so explicitly
    extra_locations: list[str] = field(default_factory=list)


@dataclass
class Match:
    category: str
    classified_by: str  # "title" | "description" | "review"
    duration: str | None


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    text = html.unescape(text)  # some APIs double-escape (Greenhouse)
    text = re.sub(r"(?i)<\s*(br|/p|/li|/div|/h\d)\s*/?>", " ", text)
    text = _TAG_RE.sub(" ", text)
    return _WS_RE.sub(" ", html.unescape(text)).strip()
