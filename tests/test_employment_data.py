import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from build_country_data import build_data, india_distribution
from employment_data import (ROOT, read_observations, survey_changes, sex_fields,
                             gender_summary, total_value)
from occupation_skills import skill_fields


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
                if cc == "IND":
                    self.assertIsNone(o["male"])
                    self.assertIsNone(o["female"])
                elif o["male"] is not None:
                    # Sources round independently; tolerate <= 2 people per row.
                    self.assertAlmostEqual(o["male"] + o["female"], o["jobs"], delta=2)
                if cc == "PAK":
                    self.assertIsNone(o["share_change"])
        kenya = generated["countries"]["KEN"]["employment_summary"]
        self.assertEqual(kenya["source_unclassified_jobs"], 2535990)
        self.assertAlmostEqual(kenya["source_classification_coverage_pct"], 85.1316999)

    def test_legacy_builder_cannot_overwrite_current_site(self):
        original = (ROOT / "site/data.json").read_bytes()
        process = subprocess.run([sys.executable, str(ROOT / "build_site_data.py"),
                                  "--output", str(ROOT / "site/data.json")], capture_output=True)
        self.assertNotEqual(process.returncode, 0)
        self.assertEqual(original, (ROOT / "site/data.json").read_bytes())


if __name__ == "__main__":
    unittest.main()
