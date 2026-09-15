#!/usr/bin/env python3
"""Apply traceable ILO/NASK 2025 GenAI reference scores to the six-country map.

Published 4-digit means are equally weighted within each displayed 2/3-digit
group. Local employment weights are used ONLY between displayed groups. This
is a project-derived reference index, not an official national ILO estimate.
"""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent
SOURCE_PATH = ROOT / "data/ilo_genai_2025/occupations.json"


def load_source(path=SOURCE_PATH):
    source = json.loads(Path(path).read_text(encoding="utf-8"))
    records = source["occupations"]
    codes = [r["code"] for r in records]
    if len(codes) != len(set(codes)) or not records:
        raise ValueError("Empty or duplicated occupation reference data")
    for record in records:
        score = record["mean"]
        if not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError(f"Invalid reference score: {record['code']}")
    return source


def occupation_exposure(code, records):
    if not isinstance(code, str) or len(code) not in (2, 3, 4) or not code.isdigit():
        raise ValueError(f"Unsupported occupation code: {code!r}")
    children = sorted((r for r in records if r["code"].startswith(code)), key=lambda r: r["code"])
    values = [r["mean"] for r in children]
    result = {
        "exposure": mean(values) if values else None,
        "exposure_min": min(values) if values else None,
        "exposure_max": max(values) if values else None,
        "exposure_source_id": "ilo_wp140_2025",
        "exposure_method": "unit_group_equal_weight" if values else "unmatched",
        "exposure_unit_codes": [r["code"] for r in children],
        "exposure_match_count": len(children),
        "exposure_gradient_counts": dict(sorted(Counter(r["gradient"] for r in children).items())),
    }
    if values:
        result["exposure_rationale"] = (
            f"ILO/NASK 2025：该组 {len(values)} 个已评分四位职业的等权参考均分为 {mean(values):.2f}（0–1），"
            f"细分职业均分范围 {min(values):.2f}–{max(values):.2f}。"
            "未按该组内部的本国就业人数加权；非本国实测值。点击查看细分职业与来源。"
        )
    else:
        result["exposure_rationale"] = "ILO/NASK 2025 数据未匹配此职业组。显示为无数据，不赋零分，不纳入参考均分。"
    return result


def summarize(occupations):
    total_jobs = sum(o.get("jobs") or 0 for o in occupations)
    covered = [o for o in occupations if o["exposure"] is not None and (o.get("jobs") or 0) > 0]
    covered_jobs = sum(o["jobs"] for o in covered)

    def weighted(field):
        return sum(o[field] * o["jobs"] for o in covered) / covered_jobs if covered_jobs else None

    return {
        "mean": weighted("exposure"),
        "composition_min": weighted("exposure_min"),
        "composition_max": weighted("exposure_max"),
        "covered_jobs": covered_jobs,
        "unmatched_jobs": total_jobs - covered_jobs,
        "total_jobs": total_jobs,
        "employment_coverage_pct": 100 * covered_jobs / total_jobs if total_jobs else None,
        "matched_group_count": sum(o["exposure"] is not None for o in occupations),
        "group_count": len(occupations),
        "unmatched_codes": [o["code"] for o in occupations if o["exposure"] is None],
    }


def apply_ai_exposure(payload, source=None):
    source = source if source is not None else load_source()
    if "countries" not in payload:
        raise ValueError("Expected six-country data; the legacy US array is not supported")
    payload["genai_reference"] = {
        **source,
        "method": {
            "group": "Unweighted mean of the published means of matching ISCO-08 four-digit unit groups.",
            "country": "Employment-weighted mean of displayed group reference scores, over matched employment only.",
            "composition_range": "Employment-weighted minima/maxima of constituent unit-group means; not confidence intervals and not calibrated for local tasks.",
            "country_adjustment": "None. Local task content, adoption, infrastructure and skills are not observed.",
            "india_mapping": "NCO-2015 three-digit prefixes matched to ISCO-08 three-digit minor groups as used by the existing map; not a task-level country calibration.",
            "missing": "Unmatched groups are null and excluded from means; their employment remains in the map and coverage denominator.",
            "grades": "Published four-digit gradients are shown only at four-digit level; no gradient or high-exposure headcount is inferred from a group mean.",
            "methodology_url": "ai-exposure-methodology.html",
        },
    }
    for country in payload["countries"].values():
        for occupation in country["occupations"]:
            occupation.update(occupation_exposure(occupation["code"], source["occupations"]))
        country["genai_summary"] = summarize(country["occupations"])
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-data", type=Path, default=ROOT / "site/data.json")
    args = parser.parse_args()
    payload = json.loads(args.site_data.read_text(encoding="utf-8"))
    apply_ai_exposure(payload)
    args.site_data.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for code, country in payload["countries"].items():
        print(code, json.dumps(country["genai_summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
