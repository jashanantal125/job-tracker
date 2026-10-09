# MY Tech Internship Tracker — Plan

Goal: every 30 minutes, check MNC career sites and job portals for **new tech internships in Malaysia**,
keep a clean list with the **direct apply link**, and notify me. Applying is done manually.

---

## 1. Scope (what counts as a match)

A posting is kept only if **all three** are true:

| Filter | Rule |
|---|---|
| **Location** | Malaysia: Kuala Lumpur, Selangor, Petaling Jaya, Cyberjaya, Putrajaya, Penang, Johor, Kulim, Melaka, Kuching… or "Malaysia (Remote/Hybrid)" |
| **Type** | Internship: `intern`, `internship`, `industrial training`, `latihan industri`, `industrial attachment`, `placement`, `co-op`, `student` |
| **Company** | On the MNC allow-list (`config/companies.yaml`) |

…and the role falls into one of these categories (everything else is dropped):

| Category | Example title keywords |
|---|---|
| Software Engineering | software, backend, frontend, full stack, mobile, android, iOS, developer, SDE, QA / test automation |
| Cloud / DevOps / Infra | cloud, AWS, Azure, GCP, DevOps, SRE, platform, infrastructure, network, Kubernetes |
| Data / AI | data engineer, data analyst, data science, machine learning, AI, analytics, BI |
| Cybersecurity | security, cyber, SOC, IAM, GRC (tech) |
| Tech Consulting | technology consulting, digital consulting, IT advisory, tech risk, solutions consultant, business technology analyst |
| Product Management | product manager, associate PM, product owner, product analyst |
| Enterprise Platforms | Salesforce, SAP (ABAP, S/4HANA, FICO tech), ServiceNow, Oracle (ERP/HCM), Workday, Microsoft Dynamics / Power Platform, Pega, Appian, UiPath / RPA |

**Exclude list** (drops a match even if it hit above): audit, tax, accounting, finance, HR, marketing, sales (non-technical),
legal, supply chain, procurement, mechanical/electrical/process engineering, graduate full-time (non-intern).

Classification approach:
1. Keyword rules on title (+ description) → category. Fast, free, transparent.
2. Optional LLM fallback only for titles the rules can't decide (e.g. "Digital Intern", "Technology Intern") —
   a few calls per day at most.

---

## 2. Sources

The reliable way to watch MNCs is to hit the **applicant-tracking system (ATS) behind each company's career page**.
Most expose a public JSON endpoint the career site itself uses — no login, structured data, stable IDs, direct apply URL.

### Tier 1 — Company career sites via ATS (primary, most reliable)

| ATS | How we fetch | Typical users |
|---|---|---|
| **Workday** | `POST https://{tenant}.wd{n}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs` with search text + location facet | Many big MNCs (banks, tech, energy, FMCG) |
| **SAP SuccessFactors** | career site search / RSS / sitemap | Big 4, European MNCs |
| **Oracle Cloud HCM / Taleo** | `…/hcmRestApi/resources/latest/recruitingCEJobRequisitions` | Oracle and many enterprises |
| **Greenhouse** | `https://boards-api.greenhouse.io/v1/boards/{board}/jobs` | Tech companies |
| **Lever** | `https://api.lever.co/v0/postings/{company}?mode=json` | Tech companies |
| **SmartRecruiters** | `https://api.smartrecruiters.com/v1/companies/{id}/postings` | Mixed |
| **Eightfold / Phenom / iCIMS / Avature** | per-site JSON search endpoint | Mixed |
| **Custom career sites** | JSON endpoint if one exists, else Playwright headless scrape | Google, Microsoft, Amazon, Accenture, etc. |

Each company is one config entry; adding a company = adding a few lines, not new code
(unless it's a brand-new ATS type, which is one new adapter).

### Tier 2 — Malaysian job portals / aggregators (catch what Tier 1 misses)

| Source | Notes |
|---|---|
| JobStreet (SEEK) | Search API behind the website; filter by "internship" + IT classification + MNC name match |
| Hiredly | Strong for MY internships |
| LinkedIn (guest job search) | Fragile, heavy rate-limiting and ToS restrictions → low frequency, best-effort only |
| Glints, MauKerja, Indeed MY | Optional, lower priority |
| TalentCorp / MySTEP / university career portals | Optional, mostly manual-review sources |

Rules for Tier 2: respect robots.txt / ToS, low request rate, cache, and only keep postings whose company is on the MNC list.
When a portal posting and a company-site posting are the same job, keep the **company-site apply link**.

### Starter MNC list (to be verified per company — ATS type + Malaysia location IDs)

- **Big Tech / Software:** Google, Microsoft, Amazon / AWS, Meta, Oracle, IBM, SAP, Salesforce, ServiceNow, Adobe, Cisco, VMware/Broadcom, Dell, HP / HPE, Lenovo, Huawei, Alibaba Cloud, ByteDance/TikTok, Grab, Shopee / Sea, Agoda, Visa, Mastercard, PayPal
- **Consulting / IT Services:** Accenture, Deloitte, PwC, EY, KPMG, Capgemini, IBM Consulting, Infosys, TCS, Wipro, HCLTech, NTT Data, Fujitsu, Kyndryl, DXC, Cognizant, Avanade, Thoughtworks
- **Semicon / Hardware (Penang/Kulim tech roles):** Intel, AMD, Micron, Infineon, NXP, Keysight, Motorola Solutions, Bosch, Western Digital, Lam Research, Texas Instruments
- **Global Business Services / Tech hubs in KL:** HSBC, Standard Chartered, Citi, Shell, BP, DHL IT Services, Nestlé, Unilever, P&G, Experian, Schneider Electric, Siemens, Ericsson, Nokia, Maersk, Prudential, AIA, Great Eastern
- **Malaysian MNCs (optional — see open questions):** Petronas, Maybank, CIMB, Axiata/CelcomDigi, Sime Darby, Tenaga

---

## 3. Architecture

```
            ┌──────────── every 30 min (cron) ────────────┐
            ▼                                              │
config/companies.yaml ─▶ Fetchers (1 adapter per ATS/portal, run concurrently)
                              │  raw postings
                              ▼
                        Normalizer  →  common Job schema
                              ▼
                        Filters: Malaysia? Intern? MNC? Category? Exclusions?
                              ▼
                        Dedupe (company + job_id, then fuzzy title+company across sources)
                              ▼
                        Store (SQLite / jobs.json): first_seen, last_seen, status
                              ├──▶ Notifier: NEW jobs → Telegram / Discord / email
                              └──▶ Dashboard (static page): filter, search, apply link, mark "applied"
```

### Job schema
```
id, source, company, title, category, location, work_mode,
apply_url, posted_at, first_seen_at, last_seen_at,
is_active, description_snippet, my_status (new | saved | applied | rejected | ignored), notes
```

- **New** = first time we've seen this id → notify.
- If a posting disappears for N consecutive runs → mark `is_active = false` (closed), keep history.

### Tech stack
- **Python 3.12**: `httpx` (async fetching), `pydantic` (schema), `pyyaml`, `selectolax` (HTML), `playwright` (only for JS-only sites)
- **Storage**: SQLite (`data/jobs.db`) + exported `data/jobs.json` for the dashboard
- **Scheduler**: GitHub Actions cron `*/30 * * * *` (see hosting notes)
- **Notifications**: Telegram bot (simplest on phone) — Discord webhook / email as alternatives
- **Dashboard**: static HTML/JS on GitHub Pages reading `jobs.json`; "applied" status saved in browser or committed back

### Repo layout
```
config/companies.yaml       # company → ATS type, tenant/board id, location filter
config/rules.yaml           # include/exclude keywords, categories, MY locations
src/fetchers/               # workday.py, successfactors.py, oracle.py, greenhouse.py, lever.py, ...
src/fetchers/portals/       # jobstreet.py, hiredly.py, linkedin.py
src/pipeline.py             # fetch → normalize → filter → dedupe → store → notify
src/classify.py             # role category rules (+ optional LLM fallback)
src/store.py, src/notify.py
web/                        # dashboard
data/jobs.db, data/jobs.json
tests/                      # fixtures of real responses per adapter + filter tests
.github/workflows/scrape.yml
```

---

## 4. Hosting the 30-minute schedule

| Option | Cost | Notes |
|---|---|---|
| **GitHub Actions cron** | Free on a **public** repo | Easiest. Cron can be delayed a few minutes at busy times. Private repo: 48 runs/day × ~2–3 min ≈ 3,000–4,000 min/month → exceeds the 2,000 free minutes |
| Small VPS / home server + cron | ~RM15–25/month or free | Most reliable timing, needed if many sites require Playwright |
| Cloudflare Workers Cron | Free tier | Good for JSON APIs; no Playwright |

Recommendation: start on GitHub Actions; move to a VPS if timing or minutes become a problem.

---

## 5. Build phases

1. **Foundation** — schema, config format, filter + classification rules with unit tests on ~100 real sample titles.
2. **Tier 1 adapters** — Workday, Greenhouse, Lever, SmartRecruiters, SuccessFactors, Oracle. Onboard ~20 companies first, verify each returns MY postings.
3. **Store + diff + notifier** — SQLite, new/closed detection, Telegram alert with title · company · location · apply link.
4. **Scheduler** — GitHub Actions every 30 min, commit `jobs.json`, failure alerts if a source breaks.
5. **Dashboard** — table with category/company/location filters, "new since last visit", mark applied.
6. **Tier 2 portals** — JobStreet + Hiredly first, LinkedIn best-effort; cross-source dedupe.
7. **Expand & harden** — grow company list to 80–100, source health report (which sources returned 0 / errored), LLM fallback for ambiguous titles.

---

## 6. Risks & how we handle them

- **Sites change / block bots** → prefer official ATS JSON over HTML, per-source health checks, alert when a source errors or suddenly returns 0.
- **Portal ToS (esp. LinkedIn)** → Tier 2 is optional and low-frequency; Tier 1 is the backbone.
- **Off-cycle postings with vague titles** ("Intern – Technology") → keyword rules + LLM fallback + "uncategorised" bucket I can review.
- **Duplicates across sources** → stable IDs + fuzzy matching, prefer the company apply link.
- **Internship season** → Malaysian intake peaks roughly Sep–Mar for the following year's placements; the 30-min cadence matters most then.

---

## 7. Open questions

1. Count **Malaysian MNCs** (Petronas, Maybank, CIMB, Axiata…) or **foreign MNCs only**?
2. Include **graduate programmes / trainee** roles, or strictly internships?
3. Notification channel: Telegram, Discord, email, or just the dashboard?
4. OK to make the repo **public** (free GitHub Actions minutes), or keep private and use a VPS?
5. Any must-have companies missing from the starter list?
