#!/usr/bin/env python3
"""Check official ILOSTAT CSVs for changes; never replace reviewed source data."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from employment_data import read_observations


def check(item):
    country = Path(item["path"]).name[:3]
    result = {"country": country, "url": item["source_url"]}
    try:
        with urlopen(item["source_url"], timeout=30) as response:
            content = response.read(25_000_001)
        if len(content) > 25_000_000:
            raise ValueError("Response exceeds expected country CSV size")
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / Path(item["path"]).name).write_bytes(content)
            fresh = read_observations(country, directory)
        old = read_observations(country)
        changed = sum(old.get(k) != fresh.get(k) for k in old.keys() | fresh.keys())
        result.update(status="review_required" if changed else "unchanged",
                      sha256=hashlib.sha256(content).hexdigest(), changed_observations=changed,
                      available_isco08_years=sorted({key[0] for key in fresh}))
    except Exception as error:
        result.update(status="unverified", error=str(error))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((ROOT / "data/employment_sources.json").read_text())
    files = [item for item in manifest["files"] if item["path"].endswith("_oc2_timeseries.csv")]
    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(check, files))
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "results": results,
              "scope": "Six employment CSVs only; check PLFS, model estimates and GenAI releases separately.",
              "next_step": "Review dimensions, definitions, quality flags and coverage before importing changes."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    for result in results:
        print(result["country"], result["status"], result.get("error", result.get("changed_observations")))
    if any(result["status"] == "unverified" for result in results):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
