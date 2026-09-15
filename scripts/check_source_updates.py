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
from urllib.error import HTTPError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from employment_data import read_observations


def compare_observations(old, fresh):
    old_years = {key[0] for key in old}
    new_years = {key[0] for key in fresh}
    added = len(fresh.keys() - old.keys())
    removed = len(old.keys() - fresh.keys())
    modified = sum(old[k] != fresh[k] for k in old.keys() & fresh.keys())
    return {
        "changed_observations": added + removed + modified,
        "added_observations": added, "removed_observations": removed,
        "modified_observations": modified,
        "available_isco08_years": sorted(new_years),
        "previous_available_isco08_years": sorted(old_years),
        "added_years": sorted(new_years - old_years),
        "removed_years": sorted(old_years - new_years),
    }


def check(item, input_dir=None):
    country = Path(item["path"]).name[:3]
    result = {"country": country, "url": item["source_url"]}
    try:
        if input_dir is None:
            with urlopen(item["source_url"], timeout=30) as response:
                content = response.read(25_000_001)
        else:
            candidates = [input_dir / f"OC2_{country}.csv", input_dir / Path(item["path"]).name]
            candidates = [path for path in candidates if path.is_file()]
            if len(candidates) != 1:
                raise ValueError(f"Expected exactly one source CSV for {country}")
            with candidates[0].open("rb") as f:
                content = f.read(25_000_001)
            result["supplied_file"] = candidates[0].name
        if len(content) > 25_000_000:
            raise ValueError("Response exceeds expected country CSV size")
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / Path(item["path"]).name).write_bytes(content)
            fresh = read_observations(country, directory)
        old = read_observations(country)
        comparison = compare_observations(old, fresh)
        result.update(status="review_required" if comparison["changed_observations"] else "unchanged",
                      sha256=hashlib.sha256(content).hexdigest(), **comparison)
    except HTTPError as error:
        preview = error.read(2048).decode("utf-8", errors="replace")
        result.update(status="unverified", error=str(error), http_status=error.code)
        if "error code: 1010" in preview and "cloudflare" in error.headers.get("Server", "").lower():
            result["access_issue"] = "Cloudflare 1010: client access blocked; data availability unknown."
        error.close()
    except Exception as error:
        result.update(status="unverified", error=str(error))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--input-dir", type=Path,
                        help="Compare supplied OC2_COUNTRY.csv files offline; makes no network requests")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "data/employment_sources.json").read_text())
    files = [item for item in manifest["files"] if item["path"].endswith("_oc2_timeseries.csv")]
    with ThreadPoolExecutor(max_workers=6) as executor:
        results = list(executor.map(lambda item: check(item, args.input_dir), files))
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "results": results,
              "input_mode": "user_supplied_files" if args.input_dir else "official_http",
              "scope": "Six employment CSVs only; check PLFS, model estimates and GenAI releases separately.",
              "next_step": "Review definitions, quality and coverage. Missing years do not prove prior labels were wrong or that the publisher withdrew them."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    for result in results:
        print(result["country"], result["status"], result.get("error", result.get("changed_observations")))
    if any(result["status"] == "unverified" for result in results):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
