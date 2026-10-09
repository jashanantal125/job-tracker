"""Decide whether a posting is a Malaysian tech internship we care about.

A posting is kept when it is
  1. in Malaysia,
  2. an internship (any length) or another student programme lasting 3-6 months,
  3. in one of the tracked tech role categories, and
  4. not a non-tech role (sales, HR, audit, ...).

All rules are plain regexes so they are easy to read and tweak.
"""

from __future__ import annotations

import re

from .models import Match, Posting

# --------------------------------------------------------------------------- location

MALAYSIA_RE = re.compile(
    r"\b(malaysia|kuala lumpur|wilayah persekutuan|selangor|petaling jaya|cyberjaya|"
    r"putrajaya|shah alam|subang( jaya)?|puchong|bangsar|mont kiara|klang|"
    r"penang|pulau pinang|bayan lepas|george ?town|batu kawan|butterworth|seberang perai|"
    r"johor( bahru)?|iskandar|nusajaya|kulim|kedah|melaka|malacca|ipoh|perak|"
    r"seremban|negeri sembilan|kuching|sarawak|kota kinabalu|sabah|kuantan|pahang)\b",
    re.I,
)
MY_COUNTRY_CODES = {"MY", "MYS"}

CITY_GROUPS = [
    ("Penang / Kedah", re.compile(r"penang|pulau pinang|bayan lepas|george ?town|batu kawan|butterworth|seberang|kulim|kedah", re.I)),
    ("Johor", re.compile(r"johor|iskandar|nusajaya", re.I)),
    ("Klang Valley", re.compile(r"kuala lumpur|selangor|petaling|cyberjaya|putrajaya|shah alam|subang|puchong|bangsar|mont kiara|klang|wilayah", re.I)),
]


def is_malaysia(location: str, country_code: str | None = None, extra: list[str] | None = None) -> bool:
    if country_code and country_code.upper() in MY_COUNTRY_CODES:
        return True
    return any(MALAYSIA_RE.search(loc or "") for loc in [location, *(extra or [])])


def city_group(location: str) -> str:
    for name, rx in CITY_GROUPS:
        if rx.search(location or ""):
            return name
    return "Other Malaysia"


# --------------------------------------------------------------------------- internship / programme

# Any of these in the title => internship, whatever its length.
INTERN_RE = re.compile(
    r"\b(interns?|internships?|industrial (training|attachment|placement)|latihan industri|"
    r"praktikal|co-?op|placement( student| year| programme| program)?|"
    r"(summer|winter|vacation(er)?|spring) (analyst|associate|intern\w*|programme|program|scheme|student)|"
    r"student (trainee|worker|placement|programme|program|assistant)|undergraduate|"
    r"externship|work[- ]study|apprentice(ship)?)\b",
    re.I,
)

# These only count when the posting says the programme lasts 3-6 months.
PROGRAMME_RE = re.compile(
    r"\b(programme|program|trainee(ship)?|graduate|fellowship|bootcamp|academy|cadet(ship)?|scholars?)\b",
    re.I,
)

_NUM = r"(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
DURATION_RE = re.compile(
    rf"\b{_NUM}\s*(?:(?:-|–|to|or)\s*{_NUM}\s*)?[- ]?(months?|weeks?)\b",
    re.I,
)
_WORDS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve".split())}


def _num(s: str) -> int:
    return int(s) if s.isdigit() else _WORDS[s.lower()]


def find_duration(text: str) -> tuple[float, float] | None:
    """Return the first plausible (min, max) duration in months, or None."""
    for m in DURATION_RE.finditer(text or ""):
        lo = _num(m.group(1))
        hi = _num(m.group(2)) if m.group(2) else lo
        if m.group(3).lower().startswith("week"):
            lo, hi = lo / 4, hi / 4  # 12 weeks counts as 3 months
            if hi < 1:
                continue
        if 1 <= lo <= hi <= 24:
            return lo, hi
    return None


def format_duration(d: tuple[float, float] | None) -> str | None:
    if not d:
        return None
    lo, hi = round(d[0]), round(d[1])
    return f"{lo} months" if lo == hi else f"{lo}–{hi} months"


def title_prefilter(title: str) -> bool:
    """Cheap check used by sources to decide which postings deserve a detail fetch."""
    return bool(INTERN_RE.search(title or "") or PROGRAMME_RE.search(title or ""))


def internship_duration(title: str, description: str) -> tuple[bool, str | None]:
    """(is_eligible, duration_label)."""
    duration = find_duration(f"{title} . {description}")
    label = format_duration(duration)
    if INTERN_RE.search(title or ""):
        return True, label
    if PROGRAMME_RE.search(title or "") and duration and 3 <= duration[0] and duration[1] <= 6.5:
        return True, label
    return False, label


# --------------------------------------------------------------------------- role categories

CATEGORIES = [
    "Enterprise Platforms",
    "Product Management",
    "Tech Consulting",
    "Cybersecurity",
    "Data & AI",
    "Cloud & Infrastructure",
    "Software Engineering",
    "IT / Tech (General)",
]
REVIEW = "Needs Review"


def _rx(pattern: str) -> re.Pattern:
    return re.compile(rf"\b({pattern})\b", re.I)


# Ordered: the first matching category wins (an "SAP Developer Intern" is
# Enterprise Platforms, not Software Engineering).
STRONG_TITLE_RULES: list[tuple[str, re.Pattern]] = [
    ("Enterprise Platforms", _rx(
        r"salesforce|sfdc|sap|s/?4 ?hana|abap|successfactors|ariba|servicenow|service now|"
        r"oracle (erp|hcm|fusion|cloud|apps|netsuite)|netsuite|workday|"
        r"(microsoft |ms )?dynamics( 365)?|d365|power (platform|apps|automate|bi)|"
        r"pega|appian|outsystems|mendix|uipath|rpa|robotic process automation|"
        r"automation anywhere|blue prism|erp|crm")),
    ("Product Management", _rx(
        r"product (manager|management|owner|analyst|ops|operations)|associate product|apm|"
        r"technical program(me)? manag\w*")),
    ("Tech Consulting", _rx(
        r"(technology|tech|digital|it|cloud|data|cyber|sap|erp|systems?) (consult\w*|advisory|strategy|risk)|"
        r"technology (analyst|solutions?)|business technology|digital transformation|"
        r"solutions? (consultant|architect|engineer|analyst)|pre-?sales|"
        r"(it|technical) business analyst|business systems? analyst|systems analyst|"
        r"tech(nology)? risk|digital trust|it audit")),
    ("Cybersecurity", _rx(
        r"cyber\w*|security|infosec|soc|penetration|pentest\w*|iam|identity (and|&) access|"
        r"threat|vulnerability|forensics?")),
    ("Data & AI", _rx(
        r"data (engineer\w*|scien\w*|analy\w*|governance|management|platform)|data|"
        r"machine learning|ml|ai|artificial intelligence|deep learning|nlp|computer vision|"
        r"gen ?ai|llm|analytics|business intelligence|bi")),
    ("Cloud & Infrastructure", _rx(
        r"cloud|devops|devsecops|sre|site reliability|platform engineer\w*|infrastructure|"
        r"network(ing)?|kubernetes|aws|azure|gcp|linux|system administrat\w*|sysadmin|"
        r"it (support|operations|ops|infrastructure)|end user computing|data cent(er|re)")),
    ("Software Engineering", _rx(
        r"software|developer|development engineer|programmer|coder|sde|swe|"
        r"back-?end|front-?end|full-?stack|web|mobile|android|ios|flutter|react|java|python|"
        r"dotnet|asp\.net|app(lication)? (developer|development|engineer\w*)|firmware|embedded software|"
        r"test automation|automation test\w*|software (qa|test\w*|quality)|qa (automation|engineer)|"
        r"game (developer|programmer)|blockchain|api")),
]

# Weak tech words: only enough on their own when nothing non-tech is in the title.
GENERIC_TECH_RE = _rx(
    r"it|information technology|technology|tech|digital|information systems?|"
    r"computer science|ict|innovation")

# Too vague to classify from the title alone; decided by the description.
VAGUE_TECH_RE = _rx(r"engineering|engineer|technical|technology|analyst")

# Generic consulting / analyst titles need tech evidence in the description.
GENERIC_CONSULTING_RE = _rx(r"consult\w*|advisory|business analyst|strategy")

# Always dropped, even if a tech word is present ("Software Sales Intern").
HARD_EXCLUDE_RE = _rx(
    r"sales|marketing|brand\w*|human resources?|hr|people (team|ops)|talent acquisition|"
    r"recruit\w*|legal|law|tax|accounting|accountant|payroll|procurement|purchasing|"
    r"customer (service|support|success)|call cent(er|re)|graphic design\w*|content creat\w*|"
    r"copywrit\w*|events?|corporate communications?|public relations|pr|actuar\w*|"
    r"(financial |external |internal )?audit(or|ing)?|treasury|supply chain|logistics|warehouse|"
    r"manufacturing|facilit(y|ies)|ehs|hse|safety|social media|journalis\w*|admin(istrative)? assistant")

# Dropped unless the title also has a strong tech category ("Finance Data Analyst" stays).
SOFT_EXCLUDE_RE = _rx(
    r"financ\w*|risk|credit|banking|operations|mechanical|electrical|electronics?|chemical|civil|"
    r"process|hardware|analog|layout|failure analysis|product engineer\w*|test engineer\w*|"
    r"validation|reliability|quality|design engineer\w*|research|r&d|planning|admin\w*|"
    r"assembly|packaging|materials?|mechatronics?|biomedical|clinical|medical")

# Exceptions to HARD_EXCLUDE that are still tech.
HARD_EXCLUDE_EXCEPTIONS_RE = _rx(r"pre-?sales|it audit|technology audit|cyber audit|sales ?force")

TECH_SIGNAL_RE = _rx(
    r"software|developer|programming|coding|python|java|javascript|sql|cloud|aws|azure|gcp|"
    r"data|analytics|machine learning|ai|cyber\w*|security|sap|salesforce|servicenow|oracle|"
    r"erp|crm|digital transformation|technology|it systems|devops|api|agile|scrum|"
    r"computer science|information technology|automation")

# Words removed to decide whether a title is completely generic ("Summer Internship 2027").
_GENERIC_FILLER_RE = re.compile(
    r"\b(interns?|internships?|industrial|training|attachment|placement|latihan|industri|programme|"
    r"program|student|students|summer|winter|vacation|spring|undergraduate|trainee|scheme|"
    r"malaysia|kuala lumpur|penang|cyberjaya|20\d\d|intake|batch|january|february|march|april|"
    r"may|june|july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|"
    r"sept|oct|nov|dec|q[1-4]|the|and|for|of|in|at|to|a|an|months?|\d+)\b",
    re.I,
)


def _title_category(title: str) -> str | None:
    for category, rx in STRONG_TITLE_RULES:
        if rx.search(title):
            return category
    return None


def _description_category(description: str) -> str | None:
    """Pick the category with the most keyword hits in the description (needs >= 2)."""
    best, best_hits = None, 1
    for category, rx in STRONG_TITLE_RULES:
        hits = len(rx.findall(description))
        if hits > best_hits:
            best, best_hits = category, hits
    return best


def _is_generic_title(title: str) -> bool:
    rest = _GENERIC_FILLER_RE.sub(" ", title)
    rest = re.sub(r"[^a-z]+", " ", rest, flags=re.I).strip()
    return rest == ""


def classify(title: str, description: str = "") -> tuple[str | None, str]:
    """Return (category or None, how) for a posting already known to be an internship."""
    title = title or ""
    description = description or ""

    if HARD_EXCLUDE_RE.search(title) and not HARD_EXCLUDE_EXCEPTIONS_RE.search(title):
        return None, "excluded"

    strong = _title_category(title)
    if strong:
        return strong, "title"
    if SOFT_EXCLUDE_RE.search(title):
        return None, "excluded"

    if GENERIC_CONSULTING_RE.search(title):
        if len(TECH_SIGNAL_RE.findall(description)) >= 2:
            return "Tech Consulting", "description"
        return None, "non-tech consulting"

    if GENERIC_TECH_RE.search(title):
        return _description_category(description) or "IT / Tech (General)", "title"

    if VAGUE_TECH_RE.search(title):
        from_desc = _description_category(description)
        return (from_desc, "description") if from_desc else (None, "no tech category")

    if _is_generic_title(title):
        from_desc = _description_category(description)
        if from_desc:
            return from_desc, "description"
        return REVIEW, "review"

    return None, "no tech category"


# --------------------------------------------------------------------------- full evaluation


def evaluate(p: Posting) -> tuple[Match | None, str]:
    """Return (match, reason). reason explains a rejection, for health stats."""
    if not is_malaysia(p.location, p.country_code, p.extra_locations):
        return None, "not malaysia"
    ok, duration = internship_duration(p.title, p.description)
    if not ok:
        return None, "not internship"
    category, how = classify(p.title, p.description)
    if not category:
        return None, how
    return Match(category=category, classified_by=how, duration=duration), "matched"
