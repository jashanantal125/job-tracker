# MY Tech Internships

Tracks **tech internships at MNCs in Malaysia**. A scheduled job checks company
career sites and job portals every 30 minutes, and a static website lists every match
with its apply link. New postings are flagged on the site.

**Roles tracked:** Software Engineering (backend, frontend, mobile, QA automation),
Cloud & Infrastructure, Data & AI, Cybersecurity, Tech Consulting, Product Management,
Enterprise Platforms (SAP, Salesforce, ServiceNow, Oracle, Workday, Dynamics, Power
Platform, RPA), plus general IT internships.

**Included:** internships of any length, and other student programmes that last 3–6 months.
**Companies:** the MNC list in [`scraper/config/companies.toml`](scraper/config/companies.toml)
(global MNCs and Malaysian MNCs).

## How it works

```
GitHub Actions (every 30 min)
  └─ python3 -m tracker
       ├─ company career sites (Workday, SmartRecruiters, Greenhouse, Lever, Oracle,
       │   SuccessFactors, Eightfold, Amazon)            → every job at that company in Malaysia
       ├─ JobStreet + LinkedIn                          → kept only if the employer is on the MNC list
       ├─ filters: Malaysia? internship? tech role? not sales/HR/audit/…?
       ├─ merge into public/data/jobs.json  (new / still open / closed, duplicates merged)
       └─ public/data/health.json           (which sources worked)
  └─ commit (only when something changed) → Vercel redeploys the site
```

| Path | What |
|---|---|
| `scraper/tracker/filters.py` | All matching rules: locations, internship keywords, role categories, exclusions |
| `scraper/tracker/sources/` | One adapter per career-site system or portal |
| `scraper/config/companies.toml` | Company list, aliases, career-site details |
| `public/` | The website (plain HTML/CSS/JS, no build step) |
| `.github/workflows/scrape.yml` | The 30-minute schedule |

The scraper uses only the Python standard library (3.11+), so there is nothing to install.

## Setup

1. **Vercel:** *Add New → Project*, import this repo, keep the defaults (`vercel.json`
   already sets the output directory to `public/`) and deploy.
2. **Run once:** GitHub → *Actions → Fetch internships → Run workflow*. After it
   finishes, open the site's **Sources** tab to see which sources work.
3. **Auto-deploys from the bot's commits.** Vercel's Hobby plan can block deployments from
   commits authored by `github-actions[bot]` on private repos. Either:
   - create a Deploy Hook (Vercel → Project → Settings → Git → Deploy Hooks) and add it as a
     repository secret named `VERCEL_DEPLOY_HOOK` (GitHub → Settings → Secrets and
     variables → Actions). The workflow calls it after each data commit; or
   - add repository *variables* `DATA_COMMIT_NAME` / `DATA_COMMIT_EMAIL` set to your own
     GitHub name and email, so data commits are authored by you.
4. Scheduled workflows only run on the repository's **default branch**. Make sure the
   branch containing this code is the default (or merge it into `main`).

### GitHub Actions minutes

The repo is private, so Actions minutes count against the free 2,000/month. Each run is
designed to finish in under a minute (no dependencies to install, a 42 s fetch budget),
which is about 1,440 minutes/month. If you hit the limit, make the repo public (unlimited
minutes) or change the cron in `scrape.yml` to hourly.

## Everyday use

- **New** jobs are highlighted, counted in the tab title, and shown in a banner since your
  last visit. With the tab open, the page re-checks every 5 minutes and pops a toast (and a
  browser notification if you enable it in the footer).
- Mark jobs **Saved / Applied / Hidden**. These live in your browser's local storage; use
  *Export / Import* in the footer to move them to another device.
- **Needs review** shows vague postings (e.g. "Internship Programme 2027") that the rules
  couldn't classify.

## Maintaining

- **A source shows red in Sources:** the career-site details in `companies.toml` are wrong
  or the site changed. Open the company's job search page, check the URL
  (e.g. `https://<tenant>.wd3.myworkdayjobs.com/<site>`) and fix it, or set `enabled = false`.
- **Add a company:** copy a block in `companies.toml`. Without an `[company.ats]` table it is
  still matched on JobStreet/LinkedIn and listed under "Check manually".
- **A role is wrongly kept or dropped:** edit the regexes in `filters.py` and add the title
  to `tests/test_filters.py`.

Run locally:

```bash
cd scraper
python3 -m unittest discover -s tests -t .      # tests
python3 -m tracker --dry-run                    # fetch everything, print matches, write nothing
python3 -m tracker --dry-run --only intel       # just one source
```

Preview the site: `cd public && python3 -m http.server`, then open http://localhost:8000
