import copy
import json
from pathlib import Path
import unittest

from ai_exposure import apply_ai_exposure, load_source, occupation_exposure, summarize


def unit(code, score, tasks=1):
    return {"code": code, "mean": score, "sd": 0.1, "gradient": "Not Exposed", "task_count": tasks}


class ReferenceTests(unittest.TestCase):
    def test_published_examples_and_full_source_counts(self):
        source = load_source()
        rows = {r["code"]: r for r in source["occupations"]}
        self.assertEqual(len(rows), 427)
        self.assertEqual(sum(r["task_count"] for r in rows.values()), 3265)
        # Independent values cross-checked against the paper's annex A1.
        self.assertEqual((rows["2512"]["mean"], rows["2512"]["gradient"]), (0.53, "Exposed: Gradient 3"))
        self.assertEqual((rows["4110"]["mean"], rows["4110"]["gradient"]), (0.60, "Exposed: Gradient 4"))
        self.assertEqual(rows["9111"]["mean"], 0.14)

    def test_group_mean_is_not_weighted_by_task_row_count(self):
        result = occupation_exposure("11", [unit("1111", 0.1, 20), unit("1112", 0.9, 1)])
        self.assertEqual(result["exposure"], 0.5)
        self.assertEqual(result["exposure_min"], 0.1)
        self.assertEqual(result["exposure_max"], 0.9)
        self.assertNotIn("exposure_gradient", result)

    def test_india_uses_three_digits_not_parent_two_digits(self):
        result = occupation_exposure("251", [unit("2511", 0.4), unit("2512", 0.6), unit("2521", 0.9)])
        self.assertEqual(result["exposure"], 0.5)
        self.assertEqual(result["exposure_unit_codes"], ["2511", "2512"])

    def test_unmatched_and_zero_have_distinct_denominators(self):
        records = [unit("1111", 0), unit("1211", 0.8)]
        rows = [dict(code=code, jobs=jobs, **occupation_exposure(code, records))
                for code, jobs in [("11", 30), ("12", 10), ("01", 60)]]
        summary = summarize(rows)
        self.assertIsNone(rows[-1]["exposure"])
        self.assertAlmostEqual(summary["mean"], 0.2)
        self.assertEqual(summary["covered_jobs"], 40)
        self.assertEqual(summary["employment_coverage_pct"], 40)
        self.assertEqual(summary["unmatched_jobs"], 60)

    def test_all_missing_has_no_fabricated_mean(self):
        result = summarize([dict(code="01", jobs=50, **occupation_exposure("01", []))])
        self.assertIsNone(result["mean"])
        self.assertIsNone(result["composition_min"])
        self.assertEqual(result["employment_coverage_pct"], 0)

    def test_composition_range_uses_employment_weights(self):
        records = [unit("1111", 0.1), unit("1112", 0.5), unit("1211", 0.6), unit("1212", 0.8)]
        rows = [dict(code=code, jobs=jobs, **occupation_exposure(code, records))
                for code, jobs in [("11", 3), ("12", 1)]]
        summary = summarize(rows)
        self.assertAlmostEqual(summary["mean"], 0.4)
        self.assertAlmostEqual(summary["composition_min"], 0.225)
        self.assertAlmostEqual(summary["composition_max"], 0.575)

    def test_enrichment_is_idempotent_and_preserves_non_ai_fields(self):
        path = Path(__file__).resolve().parents[1] / "site/data.json"
        data = json.loads(path.read_text())
        before = copy.deepcopy(data)
        apply_ai_exposure(data)
        self.assertEqual(before, data)
        self.assertEqual(data["countries"]["IDN"]["genai_summary"]["unmatched_codes"], ["01", "02", "03"])
        self.assertEqual(data["countries"]["IDN"]["genai_summary"]["unmatched_jobs"], 539970)
        for country in data["countries"].values():
            self.assertEqual(country["genai_summary"]["total_jobs"], country["total_jobs"])
            summary = country["genai_summary"]
            self.assertLessEqual(summary["composition_min"], summary["mean"])
            self.assertLessEqual(summary["mean"], summary["composition_max"])
            for row in country["occupations"]:
                if row["exposure"] is not None:
                    self.assertTrue(0 <= row["exposure"] <= 1)


if __name__ == "__main__":
    unittest.main()
