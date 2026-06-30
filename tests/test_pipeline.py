"""Unit + integration tests for the candidate transformer."""
import contextlib
import io
import json
import os
import sys
import unittest

HERE = os.path.dirname(__file__)
ROOT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, ROOT)

from src.normalize import (  # noqa: E402
    normalize_phone, normalize_date, normalize_country, normalize_skill,
    normalize_email, extract_emails, extract_phones,
)
from src.merge import merge_profiles  # noqa: E402
from src.confidence import attach_confidence  # noqa: E402
from src.project import project, ProjectionError  # noqa: E402
from src.pipeline import run  # noqa: E402
from src.schema import DEFAULT_SCHEMA  # noqa: E402
from src.validate import validate  # noqa: E402


class TestNormalize(unittest.TestCase):
    def test_phone_e164_us(self):
        self.assertEqual(normalize_phone("(415) 555-2671"), "+14155552671")
        self.assertEqual(normalize_phone("4155552671"), "+14155552671")
        self.assertEqual(normalize_phone("+1 415-555-2671"), "+14155552671")

    def test_phone_intl(self):
        self.assertEqual(normalize_phone("00 91 9826551122"), "+919826551122")
        self.assertEqual(normalize_phone("+44 20 7946 0958"), "+442079460958")

    def test_phone_garbage(self):
        self.assertIsNone(normalize_phone("abc"))
        self.assertIsNone(normalize_phone(""))
        self.assertIsNone(normalize_phone(None))

    def test_dates(self):
        self.assertEqual(normalize_date("Jan 2021"), "2021-01")
        self.assertEqual(normalize_date("2021-04"), "2021-04")
        self.assertEqual(normalize_date("2021/4"), "2021-04")
        self.assertEqual(normalize_date("04/2021"), "2021-04")
        self.assertEqual(normalize_date("2021"), "2021-01")
        self.assertIsNone(normalize_date("present"))
        self.assertIsNone(normalize_date("garbage"))

    def test_country(self):
        self.assertEqual(normalize_country("USA"), "US")
        self.assertEqual(normalize_country("united kingdom"), "GB")
        self.assertEqual(normalize_country("in"), "IN")
        self.assertIsNone(normalize_country("Atlantis"))

    def test_skills(self):
        self.assertEqual(normalize_skill("js"), "JavaScript")
        self.assertEqual(normalize_skill("PYTHON"), "Python")
        self.assertEqual(normalize_skill("K8s"), "Kubernetes")
        self.assertEqual(normalize_skill("FooLang"), "FooLang")  # passthrough

    def test_email(self):
        self.assertEqual(normalize_email("Foo@Bar.com"), "foo@bar.com")
        self.assertIsNone(normalize_email("not-an-email"))
        self.assertEqual(extract_emails("contact me at a@b.com please"), ["a@b.com"])
        self.assertIn("+14155552671", extract_phones("call (415) 555-2671 anytime"))


class TestMerge(unittest.TestCase):
    def test_merge_same_email_different_phone_formats(self):
        a = {
            "candidate_id": "a", "full_name": "Jane Doe",
            "emails": ["jane@x.com"], "phones": ["+14155552671"],
            "location": {"city": None, "region": None, "country": "US"},
            "links": {"linkedin": None, "github": None, "portfolio": None, "other": []},
            "headline": None, "years_experience": None,
            "skills": [{"name": "Python", "confidence": 0.85, "sources": ["recruiter_csv"]}],
            "experience": [], "education": [],
            "provenance": [{"field": "emails", "source": "recruiter_csv", "method": "csv"}],
            "overall_confidence": 0.0,
        }
        b = {
            "candidate_id": "b", "full_name": "Jane D.",
            "emails": ["jane@x.com"], "phones": ["+14155552671"],
            "location": {"city": "SF", "region": None, "country": "US"},
            "links": {"linkedin": None, "github": None, "portfolio": None, "other": []},
            "headline": "SSE", "years_experience": 8,
            "skills": [{"name": "Python", "confidence": 0.8, "sources": ["ats_json"]},
                       {"name": "AWS", "confidence": 0.8, "sources": ["ats_json"]}],
            "experience": [], "education": [],
            "provenance": [{"field": "emails", "source": "ats_json", "method": "ats"}],
            "overall_confidence": 0.0,
        }
        merged = merge_profiles([a, b])
        self.assertEqual(len(merged), 1)
        m = merged[0]
        # ats_json wins for full_name (higher priority).
        self.assertEqual(m["full_name"], "Jane D.")
        self.assertEqual(m["location"]["city"], "SF")
        names = sorted(s["name"] for s in m["skills"])
        self.assertEqual(names, ["AWS", "Python"])
        py = next(s for s in m["skills"] if s["name"] == "Python")
        self.assertGreater(py["confidence"], 0.85)  # boosted

    def test_garbage_source_does_not_crash(self):
        good = {
            "candidate_id": "g", "full_name": "Alice", "emails": ["a@b.com"],
            "phones": [], "location": {"city": None, "region": None, "country": None},
            "links": {"linkedin": None, "github": None, "portfolio": None, "other": []},
            "headline": None, "years_experience": None, "skills": [],
            "experience": [], "education": [],
            "provenance": [{"field": "full_name", "source": "recruiter_csv", "method": "csv"}],
            "overall_confidence": 0.0,
        }
        merged = merge_profiles([good])
        self.assertEqual(len(merged), 1)


class TestProjection(unittest.TestCase):
    rec = {
        "candidate_id": "x", "full_name": "Jane Doe",
        "emails": ["jane@acme.com", "jane.d@acme.com"],
        "phones": ["+14155552671"],
        "location": {"city": "SF", "region": "CA", "country": "US"},
        "links": {"linkedin": "u", "github": None, "portfolio": None, "other": []},
        "headline": "SSE",
        "years_experience": 8,
        "skills": [{"name": "Python", "confidence": 0.9, "sources": ["x"]},
                   {"name": "AWS", "confidence": 0.8, "sources": ["x"]}],
        "experience": [], "education": [], "provenance": [],
        "overall_confidence": 0.9,
    }

    def test_custom_projection(self):
        with open(os.path.join(ROOT, "configs", "custom.json")) as f:
            cfg = json.load(f)
        out = project(self.rec, cfg)
        self.assertEqual(out["full_name"], "Jane Doe")
        self.assertEqual(out["primary_email"], "jane@acme.com")
        self.assertEqual(out["phone"], "+14155552671")
        self.assertEqual(out["country"], "US")
        self.assertEqual(out["skills"], ["Python", "AWS"])

    def test_required_missing_error(self):
        cfg = {"fields": [{"path": "ghost", "from": "nope", "type": "string", "required": True}],
               "on_missing": "error"}
        with self.assertRaises(ProjectionError):
            project(self.rec, cfg)

    def test_omit_missing(self):
        cfg = {"fields": [{"path": "ghost", "from": "nope", "type": "string"},
                          {"path": "full_name", "type": "string"}],
               "on_missing": "omit"}
        out = project(self.rec, cfg)
        self.assertNotIn("ghost", out)
        self.assertEqual(out["full_name"], "Jane Doe")


class TestEndToEnd(unittest.TestCase):
    samples = os.path.join(ROOT, "samples")

    def test_default_pipeline(self):
        res = run(inputs={
            "csv": os.path.join(self.samples, "recruiter.csv"),
            "ats": os.path.join(self.samples, "ats.json"),
            "resumes": os.path.join(self.samples, "resumes"),
            "notes": os.path.join(self.samples, "notes"),
        })
        self.assertGreater(res["count"], 0)
        # Jane appears in CSV (twice), ATS, resume, notes -> should merge.
        jane = [r for r in res["records"] if "jane" in r["full_name"].lower()]
        self.assertEqual(len(jane), 1)
        self.assertIn("+14155552671", jane[0]["phones"])
        self.assertTrue(jane[0]["overall_confidence"] > 0.5)
        # Validation produces no errors against default schema.
        for rec in res["records"]:
            self.assertEqual(validate(rec, DEFAULT_SCHEMA), [])

    def test_missing_source_graceful(self):
        # Suppress the expected "[warn] path not found" stdout noise -
        # we're deliberately feeding a bad path to prove the pipeline survives.
        bad_path = os.path.join(ROOT, "_does_not_exist.json")
        with contextlib.redirect_stdout(io.StringIO()):
            res = run(inputs={
                "csv": os.path.join(self.samples, "recruiter.csv"),
                "ats": bad_path,
                "resumes": None, "notes": None,
            })
        self.assertGreater(res["count"], 0)


if __name__ == "__main__":
    unittest.main()
