"""Adapter tests against canned responses shaped like each API's real output.

These check parsing only; whether each company's endpoint is live is reported
by the Sources panel after a real run.
"""

import unittest
from unittest import mock

from tracker import http
from tracker.sources import (amazon, eightfold, greenhouse, jobstreet, lever, linkedin, oracle,
                             smartrecruiters, successfactors, workday)


class WorkdayTests(unittest.TestCase):
    def test_lists_malaysia_jobs_and_fetches_intern_details(self):
        facets = [{"facetParameter": "locationMainGroup", "values": [
            {"facetParameter": "locationCountry", "descriptor": "Country", "values": [
                {"descriptor": "Malaysia", "id": "MY123", "count": 2},
                {"descriptor": "India", "id": "IN1", "count": 50}]}]}]
        posts = [
            {"title": "Software Engineering Intern", "externalPath": "/job/Penang/Software-Intern_JR1",
             "locationsText": "2 Locations", "postedOn": "Posted Today", "bulletFields": ["JR1"]},
            {"title": "Senior Process Engineer", "externalPath": "/job/Kulim/Process_JR2",
             "locationsText": "Kulim, Malaysia", "postedOn": "Posted 30+ Days Ago", "bulletFields": ["JR2"]},
        ]
        detail = {"jobPostingInfo": {"jobDescription": "<p>Write <b>Python</b> code</p>",
                                     "location": "Penang, Malaysia", "additionalLocations": ["Kuala Lumpur"],
                                     "country": {"descriptor": "Malaysia"}, "startDate": "2026-10-01"}}
        bodies = []

        def post(url, body, **kw):
            bodies.append(body)
            if body["limit"] == 1:
                return {"total": 500, "facets": facets, "jobPostings": []}
            return {"total": 2, "jobPostings": posts}

        with mock.patch.object(http, "post_json", side_effect=post), \
                mock.patch.object(http, "get_json", return_value=detail) as get:
            out = workday.fetch({"host": "intel.wd1.myworkdayjobs.com", "tenant": "intel", "site": "External"}, "Intel")

        self.assertEqual(bodies[1]["appliedFacets"], {"locationCountry": ["MY123"]})
        self.assertEqual(len(out), 2)
        intern = out[0]
        self.assertEqual(intern.native_id, "JR1")
        self.assertEqual(intern.location, "Penang, Malaysia")
        self.assertEqual(intern.description, "Write Python code")
        self.assertEqual(intern.posted_at, "2026-10-01")
        self.assertEqual(intern.apply_url, "https://intel.wd1.myworkdayjobs.com/en-US/External/job/Penang/Software-Intern_JR1")
        get.assert_called_once()  # detail only fetched for the internship

    def test_falls_back_to_keyword_search_without_malaysia_facet(self):
        def post(url, body, **kw):
            if body["limit"] == 1:
                return {"total": 3, "facets": []}
            return {"total": 0, "jobPostings": []}

        with mock.patch.object(http, "post_json", side_effect=post) as p:
            workday.fetch({"host": "h", "tenant": "t", "site": "s"}, "X")
        texts = [c.args[1]["searchText"] for c in p.call_args_list[1:]]
        self.assertEqual(texts, workday.FALLBACK_QUERIES)


class GreenhouseLeverTests(unittest.TestCase):
    def test_greenhouse(self):
        data = {"jobs": [{"id": 42, "title": "Data Intern", "absolute_url": "https://boards.greenhouse.io/x/jobs/42",
                          "location": {"name": "Kuala Lumpur"}, "first_published": "2026-10-02T01:00:00Z",
                          "content": "&lt;p&gt;SQL and Python&lt;/p&gt;", "offices": [{"name": "KL", "location": "Kuala Lumpur, Malaysia"}]}]}
        with mock.patch.object(http, "get_json", return_value=data):
            (p,) = greenhouse.fetch({"board": "x"}, "X")
        self.assertEqual((p.native_id, p.posted_at, p.description), ("42", "2026-10-02", "SQL and Python"))

    def test_lever(self):
        data = [{"id": "abc", "text": "Backend Intern", "hostedUrl": "https://jobs.lever.co/grab/abc",
                 "categories": {"location": "Kuala Lumpur", "commitment": "Internship"}, "country": "MY",
                 "createdAt": 1790000000000, "descriptionPlain": "Go services", "lists": []}]
        with mock.patch.object(http, "get_json", return_value=data):
            (p,) = lever.fetch({"site": "grab"}, "Grab")
        self.assertEqual((p.country_code, p.apply_url), ("MY", "https://jobs.lever.co/grab/abc"))
        self.assertIn("Internship", p.description)


class SmartRecruitersTests(unittest.TestCase):
    def test_list_and_detail(self):
        listing = {"totalFound": 1, "content": [{"id": "99", "name": "Cloud Intern", "releasedDate": "2026-10-03T00:00:00.000Z",
                                                  "location": {"city": "Kuala Lumpur", "country": "my"},
                                                  "typeOfEmployment": {"label": "Intern"}}]}
        detail = {"postingUrl": "https://jobs.smartrecruiters.com/Visa/99-cloud-intern",
                  "jobAd": {"sections": {"jobDescription": {"text": "<p>AWS</p>"}}}}
        with mock.patch.object(http, "get_json", side_effect=[listing, detail]):
            (p,) = smartrecruiters.fetch({"id": "Visa"}, "Visa")
        self.assertEqual(p.country_code, "MY")
        self.assertEqual(p.apply_url, "https://jobs.smartrecruiters.com/Visa/99-cloud-intern")
        self.assertIn("AWS", p.description)


class OracleTests(unittest.TestCase):
    def test_requisitions(self):
        data = {"items": [{"TotalJobsCount": 1, "requisitionList": [
            {"Id": "555", "Title": "Software Intern", "PostedDate": "2026-09-30", "PrimaryLocation": "Kuala Lumpur, Malaysia",
             "PrimaryLocationCountry": "MY", "ShortDescriptionStr": "Java", "secondaryLocations": []}]}]}
        with mock.patch.object(http, "get_json", return_value=data) as g:
            out = oracle.fetch({"host": "eeho.fa.us2.oraclecloud.com", "site": "CX_45001", "queries": ["intern"]}, "Oracle")
        self.assertIn('keyword=%22intern%22', g.call_args.args[0])
        self.assertEqual(out[0].apply_url,
                         "https://eeho.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_45001/job/555")


class HtmlSourceTests(unittest.TestCase):
    def test_successfactors(self):
        page = '''<table><tr class="data-row">
          <td><a href="/job/Kuala-Lumpur-SAP-Intern-14/1234567/" class="jobTitle-link">SAP Intern &amp; Developer</a></td>
          <td><span class="jobLocation">Kuala Lumpur, MY</span></td><td><span class="jobDate">Oct 2, 2026</span></td>
        </tr></table>'''
        (p,) = successfactors.parse(page, "https://jobs.sap.com", "SAP")
        self.assertEqual((p.native_id, p.title, p.posted_at), ("1234567", "SAP Intern & Developer", "2026-10-02"))
        self.assertEqual(p.apply_url, "https://jobs.sap.com/job/Kuala-Lumpur-SAP-Intern-14/1234567/")

    def test_linkedin(self):
        page = '''<li><div class="base-card" data-entity-urn="urn:li:jobPosting:4012345678">
          <a class="base-card__full-link" href="https://my.linkedin.com/jobs/view/software-intern-at-intel-4012345678?position=1">
          <h3 class="base-search-card__title">  Software Intern </h3>
          <h4 class="base-search-card__subtitle"><a href="#">Intel Corporation</a></h4>
          <span class="job-search-card__location">Penang, Malaysia</span>
          <time class="job-search-card__listdate" datetime="2026-10-05">4 days ago</time></div></li>'''
        (p,) = linkedin.parse(page)
        self.assertEqual((p.native_id, p.company, p.title, p.location, p.posted_at),
                         ("4012345678", "Intel Corporation", "Software Intern", "Penang, Malaysia", "2026-10-05"))
        self.assertEqual(p.apply_url, "https://www.linkedin.com/jobs/view/4012345678/")


class PortalAndMiscTests(unittest.TestCase):
    def test_jobstreet(self):
        data = {"data": [{"id": 777, "title": "IT Intern", "companyName": "Shell Business Operations",
                          "locations": [{"label": "Kuala Lumpur"}], "listingDate": "2026-10-06T03:00:00Z", "teaser": "Support"}]}
        with mock.patch.object(http, "get_json", return_value=data):
            out = jobstreet.fetch({"queries": ["intern"]}, "")
        self.assertEqual((out[0].company, out[0].apply_url), ("Shell Business Operations", "https://my.jobstreet.com/job/777"))

    def test_amazon(self):
        data = {"jobs": [{"id_icims": "2800000", "title": "Cloud Support Intern", "normalized_location": "Kuala Lumpur, MYS",
                          "country_code": "MYS", "job_path": "/en/jobs/2800000/cloud-support-intern",
                          "posted_date": "October 3, 2026", "description_short": "AWS"}]}
        with mock.patch.object(http, "get_json", return_value=data):
            (p,) = amazon.fetch({"queries": ["intern"]}, "Amazon / AWS")
        self.assertEqual((p.posted_at, p.apply_url), ("2026-10-03", "https://www.amazon.jobs/en/jobs/2800000/cloud-support-intern"))

    def test_eightfold(self):
        data = {"count": 1, "positions": [{"id": 1, "name": "Software Engineer Intern", "location": "Kuala Lumpur, Malaysia",
                                           "t_create": 1790000000, "canonicalPositionUrl": "https://x/careers/job/1"}]}
        with mock.patch.object(http, "get_json", return_value=data):
            (p,) = eightfold.fetch({"host": "x", "domain": "microsoft.com", "queries": ["intern"]}, "Microsoft")
        self.assertEqual(p.apply_url, "https://x/careers/job/1")


if __name__ == "__main__":
    unittest.main()
