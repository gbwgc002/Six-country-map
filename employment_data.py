"""Read pinned ILOSTAT observations without dropping dimensions or quality flags."""
import csv
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "ilostat_data"


def read_observations(country, directory=DATA):
    path = Path(directory) / f"{country}_oc2_timeseries.csv"
    observations = {}
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        required = {"REF_AREA", "FREQ", "MEASURE", "SEX", "OC2", "TIME_PERIOD",
                    "OBS_VALUE", "UNIT_MULT", "UNIT_MEASURE", "SOURCE", "OBS_STATUS"}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError(f"Missing CSV dimensions: {path}")
        for row in reader:
            if not row["OC2"].startswith("OC2_ISCO08_"):
                continue
            if (row["REF_AREA"], row["FREQ"], row["MEASURE"], row["UNIT_MEASURE"]) != (
                    country, "A", "EMP_TEMP_NB", "PS"):
                raise ValueError(f"Unexpected country/frequency/measure/unit: {path}")
            if row["SEX"] not in ("SEX_T", "SEX_M", "SEX_F") or not row["UNIT_MULT"]:
                raise ValueError(f"Missing or unsupported sex/unit multiplier: {path}")
            code = row["OC2"].removeprefix("OC2_ISCO08_")
            if code not in ("TOTAL", "X") and not (code.isdigit() and len(code) == 2):
                raise ValueError(f"Unexpected occupation code: {code}")
            key = (row["TIME_PERIOD"], row["SEX"], code)
            if key in observations:
                # Never silently select the last survey when multiple sources coexist.
                raise ValueError(f"Duplicate observation (select a source explicitly): {key}")
            value = None
            if row["OBS_VALUE"].strip():
                number = Decimal(row["OBS_VALUE"]) * Decimal(10) ** int(row["UNIT_MULT"])
                if not number.is_finite() or number < 0:
                    raise ValueError(f"Invalid employment: {key}")
                value = float(number)
            observations[key] = {
                "value": value, "status": row["OBS_STATUS"], "source": row["SOURCE"],
                "notes": {k: row.get(k, "") for k in ("NOTE_SOURCE", "NOTE_INDICATOR", "NOTE_CLASSIF")},
            }
    if not observations:
        raise ValueError(f"No ISCO-08 data: {path}")
    return observations


def year_rows(observations, year, sex="SEX_T"):
    return {code: obs for (y, s, code), obs in observations.items() if y == year and s == sex}


def total_value(observations, year, sex="SEX_T"):
    row = observations.get((year, sex, "TOTAL"))
    if row is None or row["value"] is None or row["value"] <= 0:
        raise ValueError(f"Missing positive published TOTAL: {year}/{sex}")
    return row["value"]


def sex_fields(observations, year, code, inherited=False):
    male = observations.get((year, "SEX_M", code), {})
    female = observations.get((year, "SEX_F", code), {})
    m, f = male.get("value"), female.get("value")
    available = m is not None and f is not None and m + f > 0
    return {
        # A parent group's counts must NEVER be copied into every child.
        "male": round(m) if available and not inherited else None,
        "female": round(f) if available and not inherited else None,
        "female_share": round(f / (m + f) * 100, 1) if available else None,
        "sex_year": year, "sex_reference_code": code,
        "sex_method": "parent_l2_ratio" if inherited else "survey_l2",
        "sex_status": sorted(set(filter(None, [male.get("status"), female.get("status")]))),
    }


def gender_summary(observations, year, included_codes):
    # Includes each L2 group once, even for the India L3 view.
    male = female = covered = 0
    for code in sorted(set(included_codes)):
        fields = sex_fields(observations, year, code)
        row = observations.get((year, "SEX_T", code), {})
        if fields["female_share"] is not None and row.get("value") is not None:
            male += fields["male"]
            female += fields["female"]
            covered += row["value"]
    return {"male": male, "female": female, "year": year,
            "female_share": 100 * female / (male + female) if male + female else None,
            "covered_jobs": round(covered),
            "coverage_pct": min(100, 100 * covered / total_value(observations, year)),
            "method": "unique_l2_groups_with_both_sexes"}


def survey_changes(observations, start, end):
    """Change against published TOTAL, including unclassified employment."""
    a, b = year_rows(observations, start), year_rows(observations, end)
    if not a or not b:
        raise ValueError(f"Missing trend endpoint: {start}–{end}")
    source_a = {r["source"] for r in a.values()}
    source_b = {r["source"] for r in b.values()}
    if source_a != source_b or len(source_a) != 1:
        raise ValueError("Incomparable trend: survey sources differ")
    if any("B" in r["status"] or "break in series" in r["notes"].get("NOTE_INDICATOR", "").lower()
           for (year, sex, _), r in observations.items() if start <= year <= end and sex == "SEX_T"):
        raise ValueError("Incomparable trend: source marks a break in series")
    ta, tb = total_value(observations, start), total_value(observations, end)
    result = {}
    for code in a.keys() & b.keys():
        if not code.isdigit() or any(r["value"] is None or "U" in r["status"] for r in (a[code], b[code])):
            continue
        result[code] = {"change": round(100 * (b[code]["value"] / tb - a[code]["value"] / ta), 2),
                        "year_from": start, "year_to": end, "method": "survey_l2",
                        "reference_code": code}
    return result


def model_changes(country, start="2020", end="2025"):
    """Explicit L1 reference, never labelled a surveyed L2/L3 change."""
    root = ET.parse(DATA / f"{country}_model_hist.xml").getroot()
    values = {}
    for series in root.iter():
        if series.tag.split("}")[-1] != "Series":
            continue
        keys = {}
        for child in series:
            if child.tag.split("}")[-1] == "SeriesKey":
                keys = {v.get("id"): v.get("value") for v in child}
        if keys.get("REF_AREA") != country or keys.get("SEX") != "SEX_T":
            raise ValueError("Unexpected model series")
        code = keys.get("OCU", "").removeprefix("OCU_ISCO08_")
        for child in series:
            if child.tag.split("}")[-1] != "Obs":
                continue
            obs = {s.tag.split("}")[-1]: s.get("value") for s in child}
            key = (obs["ObsDimension"], code)
            if key in values:
                raise ValueError(f"Duplicate model observation: {key}")
            values[key] = float(obs["ObsValue"])
    ta, tb = values[start, "TOTAL"], values[end, "TOTAL"]
    return {code: {"change": round(100 * (values[end, code] / tb - values[start, code] / ta), 2),
                   "year_from": start, "year_to": end, "method": "model_l1_reference", "reference_code": code}
            for year, code in values if year == end and code.isdigit() and len(code) == 1
            and (start, code) in values}


def verify_snapshot(manifest_path=ROOT / "data/employment_sources.json"):
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    for item in manifest["files"] + manifest.get("review_files", []):
        digest = hashlib.sha256((ROOT / item["path"]).read_bytes()).hexdigest()
        if digest != item["sha256"]:
            raise ValueError(f"Source checksum changed; review metadata before rebuilding: {item['path']}")
    return manifest
