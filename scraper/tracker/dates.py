"""Date parsing shared by the source adapters."""

from __future__ import annotations

import datetime as dt
import re


def today() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date()


def iso_date(value) -> str | None:
    """Best-effort conversion of the many date shapes sources return to YYYY-MM-DD."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        ts = value / 1000 if value > 10**11 else value
        return dt.datetime.fromtimestamp(ts, dt.timezone.utc).date().isoformat()
    s = str(value).strip()
    m = re.match(r"(\d{4}-\d{2}-\d{2})", s)
    if m:
        return m.group(1)
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return dt.datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    return relative_date(s)


def relative_date(text: str) -> str | None:
    """Parse 'Posted Today', 'Posted 3 Days Ago', '30+ Days Ago', '2 weeks ago'."""
    t = text.lower()
    if "today" in t or "just" in t or "hour" in t or "minute" in t:
        return today().isoformat()
    if "yesterday" in t:
        return (today() - dt.timedelta(days=1)).isoformat()
    m = re.search(r"(\d+)\+?\s*(day|week|month)", t)
    if m:
        n = int(m.group(1)) * {"day": 1, "week": 7, "month": 30}[m.group(2)]
        return (today() - dt.timedelta(days=n)).isoformat()
    return None
