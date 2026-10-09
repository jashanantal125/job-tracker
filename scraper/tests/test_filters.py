import unittest

from tracker import filters
from tracker.models import Posting

KEEP = {
    "Software Engineer Intern": "Software Engineering",
    "Backend Developer Internship (Java)": "Software Engineering",
    "Frontend Engineering Intern - React": "Software Engineering",
    "Mobile App Developer Intern (Flutter)": "Software Engineering",
    "Firmware Engineering Intern": "Software Engineering",
    "QA Automation Intern": "Software Engineering",
    "Cloud Engineer Intern": "Cloud & Infrastructure",
    "DevOps Internship": "Cloud & Infrastructure",
    "Site Reliability Engineering Intern": "Cloud & Infrastructure",
    "IT Support Intern": "Cloud & Infrastructure",
    "Data Analyst Intern": "Data & AI",
    "Machine Learning Engineer Intern": "Data & AI",
    "AI Research Intern": "Data & AI",
    "Business Intelligence Intern": "Data & AI",
    "Cybersecurity Intern": "Cybersecurity",
    "SOC Analyst Intern": "Cybersecurity",
    "Technology Consulting Intern": "Tech Consulting",
    "Intern - Digital Transformation": "Tech Consulting",
    "Cyber Risk Advisory Intern": "Tech Consulting",
    "Solutions Architect Intern": "Tech Consulting",
    "Presales Engineer Intern": "Tech Consulting",
    "IT Business Analyst Internship": "Tech Consulting",
    "Product Manager Intern": "Product Management",
    "Associate Product Manager Intern": "Product Management",
    "Product Owner Intern": "Product Management",
    "SAP ABAP Developer Intern": "Enterprise Platforms",
    "Salesforce Developer Intern": "Enterprise Platforms",
    "ServiceNow Developer Intern": "Enterprise Platforms",
    "Intern, SAP S/4HANA Consulting": "Enterprise Platforms",
    "Oracle ERP Functional Intern": "Enterprise Platforms",
    "Power Platform Intern": "Enterprise Platforms",
    "RPA Developer Intern (UiPath)": "Enterprise Platforms",
    "Microsoft Dynamics 365 Intern": "Enterprise Platforms",
    "IT Intern": "IT / Tech (General)",
    "Information Technology Internship": "IT / Tech (General)",
    "Industrial Training - Software Development": "Software Engineering",
    "Latihan Industri - Pembangun Perisian Software": "Software Engineering",
    "Summer Analyst - Technology": "IT / Tech (General)",
    "Finance Data Analyst Intern": "Data & AI",
    "Co-op Student, Software": "Software Engineering",
}

DROP = [
    "Marketing Intern",
    "Digital Marketing Intern",
    "HR Intern",
    "Talent Acquisition Intern",
    "Audit Intern",
    "Tax Intern",
    "Finance Intern",
    "Software Sales Intern",
    "Supply Chain Intern",
    "Mechanical Engineering Intern",
    "Process Engineer Intern",
    "Failure Analysis Intern",
    "Legal Intern",
    "Internal Auditor",            # not an internship
    "Senior Software Engineer",    # not an internship
    "International Sales Manager", # "intern" must be a whole word
    "Graduate Trainee Programme",  # programme with no 3-6 month duration
    "Strategy Consulting Intern",  # generic consulting, no tech in description
    "Customer Success Intern",
]


class ClassifyTests(unittest.TestCase):
    def test_keep(self):
        for title, category in KEEP.items():
            with self.subTest(title=title):
                ok, _ = filters.internship_duration(title, "")
                self.assertTrue(ok, "should be an internship")
                self.assertEqual(filters.classify(title, "")[0], category)

    def test_drop(self):
        for title in DROP:
            with self.subTest(title=title):
                m, _ = filters.evaluate(Posting("x", "1", "Co", title, "Kuala Lumpur, Malaysia", ""))
                self.assertIsNone(m)

    def test_generic_title_uses_description(self):
        cat, how = filters.classify("Summer Internship 2027", "Work with our cloud team on AWS and Azure infrastructure.")
        self.assertEqual((cat, how), ("Cloud & Infrastructure", "description"))

    def test_generic_title_without_description_needs_review(self):
        self.assertEqual(filters.classify("Internship Programme 2027", "")[0], filters.REVIEW)

    def test_vague_engineering_title_needs_tech_description(self):
        self.assertIsNone(filters.classify("Engineering Intern", "Support wafer fab process and equipment.")[0])
        self.assertEqual(filters.classify("Engineering Intern", "Build Python and Java software services.")[0],
                         "Software Engineering")

    def test_generic_consulting_with_tech_description(self):
        cat, _ = filters.classify("Consulting Intern", "Help clients with cloud migration, data analytics and SAP.")
        self.assertEqual(cat, "Tech Consulting")


class ProgrammeTests(unittest.TestCase):
    def test_programme_within_3_to_6_months(self):
        ok, dur = filters.internship_duration("Technology Graduate Programme", "A 6-month rotational programme.")
        self.assertTrue(ok)
        self.assertEqual(dur, "6 months")

    def test_programme_range(self):
        ok, dur = filters.internship_duration("Digital Academy Trainee", "Duration: 3 to 6 months")
        self.assertTrue(ok)
        self.assertEqual(dur, "3–6 months")

    def test_long_programme_rejected(self):
        ok, _ = filters.internship_duration("Technology Graduate Programme", "A 24-month programme.")
        self.assertFalse(ok)

    def test_weeks(self):
        ok, dur = filters.internship_duration("Tech Bootcamp Programme", "This 12-week programme")
        self.assertTrue(ok)
        self.assertEqual(dur, "3 months")

    def test_internship_any_length_kept(self):
        ok, dur = filters.internship_duration("Software Intern", "This is a 12 month internship")
        self.assertTrue(ok)
        self.assertEqual(dur, "12 months")


class LocationTests(unittest.TestCase):
    def test_malaysia(self):
        for loc in ["Kuala Lumpur, Malaysia", "Penang", "Bayan Lepas, Pulau Pinang", "Cyberjaya",
                    "MY - Selangor - Petaling Jaya", "Kulim, Kedah", "Johor Bahru"]:
            self.assertTrue(filters.is_malaysia(loc), loc)

    def test_not_malaysia(self):
        for loc in ["Singapore", "Bangalore, India", "Jakarta", "Remote"]:
            self.assertFalse(filters.is_malaysia(loc), loc)

    def test_country_code_and_extra_locations(self):
        self.assertTrue(filters.is_malaysia("2 Locations", "MY"))
        self.assertTrue(filters.is_malaysia("Singapore", None, ["Kuala Lumpur"]))

    def test_city_group(self):
        self.assertEqual(filters.city_group("Bayan Lepas, Penang"), "Penang / Kedah")
        self.assertEqual(filters.city_group("Cyberjaya, Selangor"), "Klang Valley")
        self.assertEqual(filters.city_group("Kuching, Sarawak"), "Other Malaysia")


if __name__ == "__main__":
    unittest.main()
