"""One-off: extra MNC Workday tenants + paced LinkedIn search, dumped as TSV."""
import concurrent.futures as cf
import sys
import time

from tracker import filters, http
from tracker.sources import linkedin, smartrecruiters, workday

WORKDAY = [  # (name, host, tenant, site) -- unverified guesses, failures are fine
    ("P&G", "pg.wd5", "pg", "1000"), ("UOB", "uobgroup.wd3", "uobgroup", "UOBExternal"),
    ("Visa", "visa.wd5", "visa", "Visa_Early_Careers"), ("Visa", "visa.wd5", "visa", "Visa"),
    ("Mastercard", "mastercard.wd1", "mastercard", "CorporateCareers"),
    ("Shell", "shell.wd3", "shell", "ShellCareers"), ("Kimberly-Clark", "kimberlyclark.wd1", "kimberlyclark", "GLOBAL"),
    ("Coca-Cola", "coke.wd1", "coke", "coca-cola-careers"), ("Philips", "philips.wd3", "philips", "jobs-and-careers"),
    ("GSK", "gsk.wd5", "gsk", "GSKCareers"), ("AstraZeneca", "astrazeneca.wd3", "astrazeneca", "Careers"),
    ("Pfizer", "pfizer.wd1", "pfizer", "PfizerCareers"), ("Sanofi", "sanofi.wd3", "sanofi", "SanofiCareers"),
    ("Novartis", "novartis.wd3", "novartis", "Novartis_Careers"), ("Baker Hughes", "bakerhughes.wd5", "bakerhughes", "BakerHughes"),
    ("Manulife", "manulife.wd3", "manulife", "MFCJH_Jobs"), ("Mondelez", "mdlz.wd3", "mdlz", "External"),
    ("Abbott", "abbott.wd5", "abbott", "abbottcareers"), ("Maersk", "maersk.wd3", "maersk", "Maersk_Careers"),
    ("Equinix", "equinix.wd1", "equinix", "External"), ("Caterpillar", "cat.wd5", "cat", "CaterpillarCareers"),
    ("3M", "3m.wd1", "3m", "Search"), ("Roche", "roche.wd3", "roche", "roche-ext"),
    ("BAT", "bat.wd3", "bat", "BAT_Careers"), ("Zurich", "zurich.wd3", "zurich", "zurich"),
    ("Bayer", "bayer.wd3", "bayer", "Bayer_Careers"), ("Nike", "nike.wd1", "nike", "nke"),
    ("Hilton", "hilton.wd1", "hilton", "External"), ("Expedia", "expedia.wd5", "expedia", "search"),
    ("Western Digital", "wd.wd1", "wd", "WD"), ("Sony", "sonyglobal.wd1", "sonyglobal", "SonyGlobalCareers"),
    ("Daikin", "daikin.wd1", "daikin", "External"), ("Thermo Fisher", "thermofisher.wd5", "thermofisher", "ThermoFisherCareers"),
    ("Moody's", "moodys.wd5", "moodys", "Careers"), ("S&P Global", "spgi.wd5", "spgi", "SPGI_Careers"),
    ("Kenvue", "kenvue.wd1", "kenvue", "KenvueCareers"), ("Haleon", "haleon.wd3", "haleon", "Haleon_Careers"),
    ("Dyson", "dyson.wd3", "dyson", "Dyson"), ("Bank of America", "ghr.wd1", "ghr", "Lateral-US"),
    ("Wells Fargo", "wf.wd1", "wf", "WellsFargoJobs"), ("Prudential", "pru.wd3", "pru", "Careers"),
]
SMART = ["Continental", "ContinentalAG", "Ikea", "AbbVie", "Visa", "Wise", "Sephora", "LOreal", "Heineken",
         "Ubisoft2", "AirAsia", "Canva", "Deliveroo", "Atlassian", "Lazada"]
LINKEDIN_Q = ["intern", "strategy intern", "business analyst intern", "product intern", "product management intern",
              "project intern", "project management intern", "PMO intern", "consulting intern",
              "business development intern", "management intern", "operations intern", "transformation intern",
              "corporate strategy", "commercial intern", "planning intern"]

def emit(name, p):
    if not filters.is_malaysia(p.location, p.country_code, p.extra_locations):
        return
    ok, dur = filters.internship_duration(p.title, p.description)
    if not ok and not filters.INTERN_RE.search(p.title):
        return
    desc = " ".join(p.description.split())[:350].replace("\t", " ")
    print("\t".join(str(x) for x in ["ROW", p.posted_at or "", name, p.company or name, p.title.strip(),
                                       p.location, dur or "", p.apply_url, desc]), flush=True)

def run_wd(t):
    name, host, tenant, site = t
    return name, workday.fetch({"kind": "workday", "host": f"{host}.myworkdayjobs.com", "tenant": tenant, "site": site}, name)

def run_sr(i):
    return i, smartrecruiters.fetch({"kind": "smartrecruiters", "id": i}, i)

http.set_deadline(330)
with cf.ThreadPoolExecutor(16) as pool:
    futs = [pool.submit(run_wd, t) for t in WORKDAY] + [pool.submit(run_sr, i) for i in SMART]
    seen = set()
    # LinkedIn sequentially and slowly in the main thread while ATS fetches run
    for q in LINKEDIN_Q:
        for page in range(4):
            try:
                text = http.get_text("https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search",
                                     params={"keywords": q, "location": "Malaysia", "geoId": "106808692",
                                             "f_TPR": "r1209600", "start": page * 25}, retries=1)
            except Exception as e:  # noqa: BLE001
                print(f"LIFAIL\t{q}\t{page}\t{e}"[:200], file=sys.stderr)
                time.sleep(8)
                break
            cards = linkedin.parse(text)
            print(f"LI\t{q}\t{page}\t{len(cards)}", file=sys.stderr)
            for p in cards:
                if p.native_id not in seen:
                    seen.add(p.native_id)
                    emit("linkedin", p)
            time.sleep(3)
            if len(cards) < 25:
                break
    for f in cf.as_completed(futs, timeout=200):
        try:
            name, ps = f.result()
        except Exception as e:  # noqa: BLE001
            print(f"FAIL\t{e}"[:200], file=sys.stderr)
            continue
        print(f"OK\t{name}\t{len(ps)}", file=sys.stderr)
        for p in ps:
            emit(name, p)
