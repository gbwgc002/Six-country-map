import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from build_country_data import build_data, india_distribution, trend_fields
from employment_data import (ROOT, read_observations, survey_changes, sex_fields,
                             gender_summary, total_value)
from occupation_skills import skill_fields
from scripts.check_source_updates import check


class EmploymentTests(unittest.TestCase):
    def test_india_reads_person_not_male_distribution(self):
        # Independently checked against MOSPI PLFS 2023–24, Table 25, A147–149.
        shares = india_distribution()
        self.assertEqual(shares["112"], 1.79)  # Male distribution is 2.43.
        self.assertEqual(shares["911"], 1.45)  # Male distribution is 0.59.
        self.assertEqual(len(shares), 127)
        self.assertAlmostEqual(sum(shares.values()), 99.99)

    def test_parent_sex_counts_are_not_repeated_in_india_children(self):
        obs = read_observations("IND")
        row = sex_fields(obs, "2024", "25", inherited=True)
        self.assertIsNone(row["male"])
        self.assertIsNone(row["female"])
        self.assertIsNotNone(row["female_share"])
        self.assertEqual(gender_summary(obs, "2024", ["25", "25"]),
                         gender_summary(obs, "2024", ["25"]))

    def test_trend_denominator_includes_unclassified_employment(self):
        def record(n):
            return {"value": n, "status": "", "source": "LFS", "notes": {}}
        obs = {(year, "SEX_T", code): record(n) for year, code, n in [
            ("2020", "11", 20), ("2020", "12", 60), ("2020", "X", 20), ("2020", "TOTAL", 100),
            ("2021", "11", 20), ("2021", "12", 30), ("2021", "X", 50), ("2021", "TOTAL", 100)]}
        self.assertEqual(survey_changes(obs, "2020", "2021")["11"]["change"], 0)

    def test_mixed_survey_and_break_in_series_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "sources differ"):
            survey_changes(read_observations("PAK"), "2020", "2025")
        with self.assertRaisesRegex(ValueError, "break in series"):
            survey_changes(read_observations("NGA"), "2023", "2024")

    def test_low_reliability_and_missing_trend_endpoints_are_excluded(self):
        changes = survey_changes(read_observations("KEN"), "2021", "2022")
        self.assertNotIn("21", changes)  # U value in 2022.
        self.assertNotIn("34", changes)  # Missing value in 2022.

    def test_duplicate_and_wrong_unit_cannot_silently_overwrite(self):
        source = ROOT / "ilostat_data/IDN_oc2_timeseries.csv"
        with source.open(newline="") as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames
            row = next(reader)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / source.name
            with path.open("w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader(); writer.writerows([row, row])
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                read_observations("IDN", directory)
            row["UNIT_MULT"] = ""
            with path.open("w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fields)
                writer.writeheader(); writer.writerow(row)
            with self.assertRaisesRegex(ValueError, "multiplier"):
                read_observations("IDN", directory)

    def test_skills_are_official_broad_levels_not_degrees(self):
        self.assertEqual(skill_fields("22")["skill_level"], 4)
        self.assertEqual(skill_fields("14")["skill_level"], 3)
        self.assertEqual(skill_fields("91")["skill_level"], 1)
        self.assertEqual(skill_fields("61")["skill_level"], 2)
        self.assertEqual([skill_fields(c)["skill_level"] for c in ("01", "02", "03")], [4, 2, 1])

    def test_generated_data_contract_and_deterministic_rebuild(self):
        generated = build_data()
        self.assertEqual(generated, json.loads((ROOT / "site/data.json").read_text()))
        self.assertEqual(generated["schema_version"], 2)
        for cc, country in generated["countries"].items():
            rows = country["occupations"]
            self.assertEqual(len({o["code"] for o in rows}), len(rows))
            self.assertEqual(sum(o["jobs"] for o in rows), country["total_jobs"])
            self.assertTrue(all(o["jobs"] > 0 for o in rows))
            summary = country["gender_summary"]
            self.assertLessEqual(summary["male"] + summary["female"],
                                 country["employment_summary"]["source_total_jobs"] + 1000)
            for o in rows:
                self.assertNotIn("education_idx", o)
                if cc != "IND" and o["male"] is not None:
                    # Sources round independently; tolerate <= 2 people per row.
                    self.assertAlmostEqual(o["male"] + o["female"], o["jobs"], delta=2)
                if cc == "PAK":
                    self.assertIsNone(o["share_change"])
        kenya = generated["countries"]["KEN"]["employment_summary"]
        self.assertEqual(kenya["source_unclassified_jobs"], 2535990)
        self.assertAlmostEqual(kenya["source_classification_coverage_pct"], 85.1316999)

    def test_india_uses_direct_same_year_isco_counts(self):
        from unittest.mock import patch
        with patch("build_country_data.india_distribution", side_effect=AssertionError("Legacy scaling used")):
            india = build_data()["countries"]["IND"]
        self.assertEqual(india["data_year"], "2025")
        self.assertEqual(india["occ_count"], 40)
        self.assertFalse(india["employment_summary"]["map_is_scaled_estimate"])
        self.assertEqual(india["employment_summary"]["source_total_jobs"], 476557086)
        # The raw 2025 source has an unexplained T versus M+F discrepancy.
        # Preserve it instead of allocating missing people to either sex.
        self.assertEqual(india["gender_summary"]["male"] + india["gender_summary"]["female"], 476542322)
        obs = read_observations("IND")
        for row in india["occupations"]:
            self.assertEqual(len(row["code"]), 2)
            self.assertEqual(row["jobs_method"], "survey_l2")
            self.assertEqual(row["sex_year"], "2025")
            self.assertEqual(row["jobs"], round(obs["2025", "SEX_T", row["code"]]["value"]))
            self.assertIsNotNone(row["male"])
            self.assertIsNotNone(row["female"])
            self.assertEqual(row["male"], round(obs["2025", "SEX_M", row["code"]]["value"]))
            self.assertEqual(row["female"], round(obs["2025", "SEX_F", row["code"]]["value"]))
        self.assertFalse(any(f["path"].endswith(".xlsx") for f in india["source_files"]))

    def test_india_restores_historical_period_without_using_2025_changes(self):
        from decimal import Decimal
        country = build_data()["countries"]["IND"]
        with (ROOT / "ilostat_data/IND_oc2_timeseries.csv").open(newline="") as f:
            raw = {(r["TIME_PERIOD"], r["OC2"].removeprefix("OC2_ISCO08_")):
                   Decimal(r["OBS_VALUE"]) * Decimal(10) ** int(r["UNIT_MULT"])
                   for r in csv.DictReader(f) if r["SEX"] == "SEX_T"
                   and r["OC2"].startswith("OC2_ISCO08_") and r["OBS_VALUE"]}
        self.assertEqual(country["trend_summary"]["period"], "2022–2024")
        self.assertTrue(country["trend_summary"]["historical_reference"])
        self.assertEqual(len(country["occupations"]), 40)
        for row in country["occupations"]:
            code = row["code"]
            expected = Decimal(100) * (raw["2024", code] / raw["2024", "TOTAL"]
                                       - raw["2022", code] / raw["2022", "TOTAL"])
            self.assertAlmostEqual(row["share_change"], float(expected), delta=0.005001)
            self.assertEqual(row["share_change_desc"], "2022–2024")
            self.assertEqual(row["share_change_method"], "survey_l2")
            self.assertEqual(row["share_change_status"], "available")
            self.assertEqual(row["jobs_year"], "2025")
            self.assertEqual(row["sex_year"], "2025")

    def test_missing_trends_keep_specific_reasons_and_history(self):
        countries = build_data()["countries"]
        for row in countries["PAK"]["occupations"]:
            self.assertIsNone(row["share_change"])
            self.assertEqual(row["share_change_status"], "paused_comparability")
        self.assertEqual(countries["PAK"]["trend_summary"]["available_survey_years"],
                         ["2015", "2016", "2018", "2019", "2020", "2021", "2025"])
        self.assertIsNone(countries["PAK"]["trend_summary"]["period"])
        kenya = {r["code"]: r for r in countries["KEN"]["occupations"]}
        self.assertEqual({c for c, r in kenya.items() if r["share_change"] is None},
                         {"21", "26", "62", "74", "82"})
        for code in ("21", "26", "62", "74", "82"):
            self.assertEqual(kenya[code]["share_change_status"], "low_reliability")
            self.assertIn("U（低可靠性）", kenya[code]["share_change_note"])
            self.assertGreater(kenya[code]["jobs"], 0)
        for cc, expected in [("NGA", 31), ("IDN", 31), ("RUS", 40)]:
            rows = countries[cc]["occupations"]
            self.assertEqual(sum(r["share_change"] is not None for r in rows), expected)
            for row in rows:
                if row["share_change"] is None:
                    self.assertEqual(row["share_change_status"], "missing_model_reference")

    def test_absent_endpoint_is_not_zero_and_zero_change_is_available(self):
        config = {"trend": ("2021", "2022")}
        obs = read_observations("KEN")
        result = trend_fields("34", obs, survey_changes(obs, "2021", "2022"), config)
        self.assertIsNone(result["share_change"])
        self.assertEqual(result["share_change_status"], "missing_endpoint")
        zero = {"11": {"change": 0, "method": "survey_l2", "reference_code": "11"}}
        result = trend_fields("11", {}, zero, config)
        self.assertEqual(result["share_change"], 0)
        self.assertEqual(result["share_change_status"], "available")

    def test_supplied_missing_years_are_flagged_without_relabelling(self):
        manifest = json.loads((ROOT / "data/employment_sources.json").read_text())
        generated = build_data()["countries"]
        for cc, year, count in [("NGA", "2023", 132), ("KEN", "2022", 111)]:
            item = next(f for f in manifest["files"] if f["path"].endswith(f"{cc}_oc2_timeseries.csv"))
            result = check(item, ROOT / "data/source_review/2026-09-15")
            self.assertEqual(result["status"], "review_required")
            self.assertEqual(result["removed_years"], [year])
            self.assertEqual(result["removed_observations"], count)
            self.assertEqual(result["added_observations"], 0)
            self.assertEqual(result["modified_observations"], 0)
            self.assertEqual(generated[cc]["data_year"], year)
            self.assertFalse(generated[cc]["source_review"]["display_year_in_delivery"])
            self.assertIn("当前发布状态待核实", generated[cc]["source_review"]["note"])

    def test_legacy_builder_cannot_overwrite_current_site(self):
        original = (ROOT / "site/data.json").read_bytes()
        process = subprocess.run([sys.executable, str(ROOT / "build_site_data.py"),
                                  "--output", str(ROOT / "site/data.json")], capture_output=True)
        self.assertNotEqual(process.returncode, 0)
        self.assertEqual(original, (ROOT / "site/data.json").read_bytes())


if __name__ == "__main__":
    unittest.main()
