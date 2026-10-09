import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tracker import run, store
from tracker.models import Posting
from tracker.sources import ADAPTERS

NOW = dt.datetime(2026, 10, 9, 4, 0, tzinfo=dt.timezone.utc)


def rec(id_, source, kind, title="Software Intern", company="Intel"):
    return {"id": id_, "source": source, "source_kind": kind, "company": company, "title": title,
            "apply_url": f"https://{id_}", "category": "Software Engineering"}


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.s = store.Store(Path(self.tmp.name) / "jobs.json")

    def tearDown(self):
        self.tmp.cleanup()

    def test_new_then_updated(self):
        self.assertEqual(self.s.upsert(rec("a", "workday:Intel", "company"), NOW), "new")
        self.assertEqual(self.s.upsert(rec("a", "workday:Intel", "company"), NOW), "updated")
        self.assertEqual(self.s.jobs["a"]["first_seen"], "2026-10-09T04:00+00:00")

    def test_company_listing_closes_after_two_missing_runs(self):
        self.s.upsert(rec("a", "workday:Intel", "company"), NOW)
        self.s.close_missing("workday:Intel", set(), True, NOW)
        self.assertTrue(self.s.jobs["a"]["active"])
        self.s.close_missing("workday:Intel", set(), True, NOW)
        self.assertFalse(self.s.jobs["a"]["active"])
        # Reappearing reopens it.
        self.s.upsert(rec("a", "workday:Intel", "company"), NOW)
        self.assertTrue(self.s.jobs["a"]["active"])

    def test_portal_closes_after_unseen_days(self):
        self.s.upsert(rec("p", "jobstreet", "portal"), NOW)
        self.s.close_missing("jobstreet", set(), False, NOW + dt.timedelta(days=5))
        self.assertTrue(self.s.jobs["p"]["active"])
        self.s.close_missing("jobstreet", set(), False, NOW + dt.timedelta(days=22))
        self.assertFalse(self.s.jobs["p"]["active"])

    def test_portal_duplicate_merges_into_company_job(self):
        self.s.upsert(rec("p", "linkedin", "portal", "Software Engineering Intern 2027"), NOW)
        later = NOW + dt.timedelta(hours=1)
        self.assertEqual(self.s.upsert(rec("c", "workday:Intel", "company", "Software Engineering Intern"), later), "merged")
        self.assertEqual(list(self.s.jobs), ["c"])
        job = self.s.jobs["c"]
        self.assertEqual(job["apply_url"], "https://c")
        self.assertEqual(job["first_seen"], "2026-10-09T04:00+00:00")  # keeps the earlier sighting
        self.assertEqual(job["also_on"], [{"source": "linkedin", "url": "https://p"}])

    def test_prune_old_closed(self):
        self.s.upsert(rec("a", "workday:Intel", "company"), NOW)
        self.s.jobs["a"].update(active=False, closed_at="2026-08-01")
        self.s.prune(NOW)
        self.assertEqual(self.s.jobs, {})


class PipelineTests(unittest.TestCase):
    def test_end_to_end(self):
        def fake_fetch(kind):
            def fetch(cfg, company):
                if kind == "jobstreet":
                    return [
                        Posting("jobstreet", "1", "Shell Business Operations", "IT Intern", "Kuala Lumpur", "https://js/1", country_code="MY"),
                        Posting("jobstreet", "2", "Tiny Startup Sdn Bhd", "Software Intern", "Kuala Lumpur", "https://js/2", country_code="MY"),
                    ]
                if company == "Intel":
                    return [
                        Posting("workday:Intel", "JR1", "Intel", "Software Engineering Intern", "Penang, Malaysia", "https://intel/1"),
                        Posting("workday:Intel", "JR2", "Intel", "Marketing Intern", "Penang, Malaysia", "https://intel/2"),
                        Posting("workday:Intel", "JR3", "Intel", "Software Intern", "Bangalore, India", "https://intel/3"),
                    ]
                if company == "Salesforce":
                    raise RuntimeError("boom")
                return []
            return fetch

        fakes = {k: mock.Mock(fetch=fake_fetch(k), CLOSES_BY_ABSENCE=True) for k in ADAPTERS}
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(ADAPTERS, fakes):
            self.assertEqual(run.main(["--data-dir", d, "--deadline", "10"]), 0)
            jobs = json.loads((Path(d) / "jobs.json").read_text())["jobs"]
            health = json.loads((Path(d) / "health.json").read_text())

        titles = sorted((j["company"], j["title"], j["source_kind"]) for j in jobs)
        self.assertEqual(titles, [("Intel", "Software Engineering Intern", "company"),
                                  ("Shell", "IT Intern", "portal")])
        intel = next(j for j in jobs if j["company"] == "Intel")
        self.assertEqual((intel["city_group"], intel["company_type"]), ("Penang / Kedah", "Semiconductor & Hardware"))
        failed = [h["source"] for h in health["sources"] if not h["ok"]]
        self.assertEqual(failed, ["workday:Salesforce"])
        self.assertEqual(health["new_this_run"], 2)
        self.assertTrue(any(c["company"] == "Google" and not c["tracked"] for c in health["companies"]))


if __name__ == "__main__":
    unittest.main()
