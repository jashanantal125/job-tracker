"""One-off: deeper paced LinkedIn search + job descriptions for business-type intern roles."""
import re
import sys
import time

from tracker import filters, http
from tracker.models import strip_html
from tracker.sources import linkedin

QUERIES = ["intern", "internship", "strategy intern", "business analyst intern", "product intern",
           "product management intern", "project intern", "project management intern", "PMO intern",
           "consulting intern", "management intern", "transformation intern", "corporate strategy intern",
           "business intern", "operations excellence intern", "commercial intern", "special project intern",
           "management trainee intern", "planning intern", "advisory intern", "2027 intern", "january intake intern",
           "december intake intern", "november intake intern"]
ROLE_RE = re.compile(r"strateg|business|product|project|consult|analyst|planning|transformation|pmo|"
                     r"commercial|advisory|management|excellence|operations|performance|portfolio|growth|"
                     r"proposition|governance|special", re.I)
SKIP_RE = re.compile(r"software|engineer\b|developer|accounting|account|tax|audit|\bhr\b|human resources|"
                     r"media plann|talent|legal|devops|it intern", re.I)
WHEN_RE = re.compile(r"[^.]{0,80}(?:intake|start date|commenc|duration|\b\d{1,2}\s*(?:-|to|–)?\s*\d{0,2}\s*months?\b|"
                     r"january|february|march|november|december|2027)[^.]{0,80}", re.I)

http.set_deadline(600)
seen, found = set(), []
for q in QUERIES:
    for page in range(6):
        try:
            text = http.get_text("https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search",
                                 params={"keywords": q, "location": "Malaysia", "geoId": "106808692",
                                         "f_TPR": "r1209600", "start": page * 10}, retries=1)
        except Exception as e:  # noqa: BLE001
            print(f"LIFAIL\t{q}\t{page}\t{e}"[:200], file=sys.stderr)
            time.sleep(10)
            break
        cards = linkedin.parse(text)
        print(f"LI\t{q}\t{page}\t{len(cards)}", file=sys.stderr)
        for p in cards:
            if p.native_id in seen:
                continue
            seen.add(p.native_id)
            if filters.is_malaysia(p.location, p.country_code) and filters.INTERN_RE.search(p.title) \
                    and ROLE_RE.search(p.title) and not SKIP_RE.search(p.title):
                found.append(p)
        time.sleep(2)
        if not cards:
            break

print(f"{len(seen)} cards, {len(found)} candidates", file=sys.stderr)
for p in found:
    desc = ""
    try:
        html = http.get_text(f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{p.native_id}", retries=1)
        m = re.search(r'class="show-more-less-html__markup[^"]*"[^>]*>(.*?)</div>', html, re.S)
        desc = " ".join(strip_html(m.group(1) if m else "").split())
    except Exception as e:  # noqa: BLE001
        desc = f"(detail failed: {e})"[:80]
    when = " | ".join(dict.fromkeys(w.group(0).strip() for w in WHEN_RE.finditer(desc)))[:500]
    print("\t".join(["ROW", p.posted_at or "", p.company, p.title.strip(), p.location, p.apply_url,
                     when.replace("\t", " "), desc[:400].replace("\t", " ")]), flush=True)
    time.sleep(1.5)
