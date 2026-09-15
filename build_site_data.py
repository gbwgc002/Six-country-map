"""
Build a compact JSON for the website by merging CSV stats with AI exposure scores.

Reads occupations.csv (for stats) and scores.json (for AI exposure).
Writes legacy-output/us-data.json; never overwrites the six-country site.

Usage:
    uv run python build_site_data.py
"""

import csv
import json
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "legacy-output/us-data.json")
    args = parser.parse_args()
    if args.output.resolve() == (ROOT / "site/data.json").resolve():
        parser.error("The legacy US builder cannot overwrite six-country site/data.json")
    # Load AI exposure scores
    with (ROOT / "scores.json").open(encoding="utf-8") as f:
        scores_list = json.load(f)
    scores = {s["slug"]: s for s in scores_list}

    # Load CSV stats
    with (ROOT / "occupations.csv").open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Merge
    data = []
    for row in rows:
        slug = row["slug"]
        score = scores.get(slug, {})
        data.append({
            "title": row["title"],
            "slug": slug,
            "category": row["category"],
            "pay": int(row["median_pay_annual"]) if row["median_pay_annual"] else None,
            "jobs": int(row["num_jobs_2024"]) if row["num_jobs_2024"] else None,
            "outlook": int(row["outlook_pct"]) if row["outlook_pct"] else None,
            "outlook_desc": row["outlook_desc"],
            "education": row["entry_education"],
            "exposure": score.get("exposure"),
            "exposure_rationale": score.get("rationale"),
            "url": row.get("url", ""),
        })

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(data, f)

    print(f"Wrote {len(data)} occupations to {args.output}")
    total_jobs = sum(d["jobs"] for d in data if d["jobs"])
    print(f"Total jobs represented: {total_jobs:,}")


if __name__ == "__main__":
    main()
