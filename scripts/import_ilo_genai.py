#!/usr/bin/env python3
"""Extract the published occupation-level fields from the authors' pinned XLSX.

No rescoring or task-weighted recomputation: the workbook repeats occupation
means on task rows. Deduplicate those rows before any occupation aggregation.
Uses only Python's standard library; download the source workbook separately.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCE_COMMIT = "ca5de1ad757ea0f41f1ee5162665ddda1b8f9bb7"
SOURCE_FILE = "Final_Scores_ISCO08_Gmyrek_et_al_2025.xlsx"
SOURCE_SHA256 = "c1940b87e7293b1eb95b530b6d3da7cd806b61d217c4bff1e69372b2cff5c90a"
SOURCE_REPO = "https://github.com/pgmyrek/2025_GenAI_scores_ISCO08"
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
GRADIENTS = {"Not Exposed", "Minimal Exposure"} | {
    f"Exposed: Gradient {i}" for i in range(1, 5)
}


def read_rows(path):
    """Read the source's first worksheet, preserving explicit cell coordinates."""
    with zipfile.ZipFile(path) as book:
        shared = []
        if "xl/sharedStrings.xml" in book.namelist():
            root = ET.fromstring(book.read("xl/sharedStrings.xml"))
            shared = ["".join(si.itertext()) for si in root]
        sheet = ET.fromstring(book.read("xl/worksheets/sheet1.xml"))
        header = None
        for row in sheet.findall("s:sheetData/s:row", NS):
            cells = {}
            for cell in row.findall("s:c", NS):
                col = "".join(c for c in cell.attrib["r"] if c.isalpha())
                kind = cell.get("t")
                value = cell.find("s:v", NS)
                value = value.text if value is not None else None
                if kind == "s":
                    value = shared[int(value)]
                elif kind == "inlineStr":
                    value = "".join(t.text or "" for t in cell.findall("s:is//s:t", NS))
                cells[col] = value
            if header is None:
                header = cells
            else:
                yield {name: cells.get(col) for col, name in header.items()}


def extract(path):
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != SOURCE_SHA256:
        raise ValueError("Source checksum mismatch; review a new release before changing the pin")
    occupations, tasks = {}, Counter()
    for row in read_rows(path):
        code = str(row["ISCO_08"]).zfill(4)
        record = {
            "code": code,
            "title_en": row["Title"],
            "mean": float(row["mean_score_2025"]),
            "sd": float(row["SD_2025"]),
            "gradient": row["potential25"],
        }
        if not (len(code) == 4 and code.isdigit()):
            raise ValueError(f"Invalid ISCO-08 unit group: {code}")
        if not (0 <= record["mean"] <= 1 and 0 <= record["sd"] <= 1):
            raise ValueError(f"Invalid score: {code}")
        if record["gradient"] not in GRADIENTS:
            raise ValueError(f"Unknown published gradient: {code}")
        if code in occupations and occupations[code] != record:
            raise ValueError(f"Inconsistent repeated occupation fields: {code}")
        occupations[code] = record
        tasks[code] += 1
    if len(occupations) != 427 or sum(tasks.values()) != 3265:
        raise ValueError("Unexpected source coverage")
    records = [dict(occupations[k], task_count=tasks[k]) for k in sorted(occupations)]
    return {
        "source": {
            "id": "ilo_wp140_2025",
            "title": "Gmyrek et al. (2025), Generative AI and Jobs: A Refined Global Index of Occupational Exposure",
            "publisher": "International Labour Organization, Working Paper 140",
            "reference_year": 2025,
            "technology_reference": "start of 2025",
            "doi": "https://doi.org/10.54394/HETP0387",
            "paper_url": "https://www.ilo.org/sites/default/files/2025-05/WP140_web.pdf",
            "author_repository": SOURCE_REPO,
            "source_commit": SOURCE_COMMIT,
            "workbook_url": f"{SOURCE_REPO}/blob/{SOURCE_COMMIT}/{SOURCE_FILE}",
            "download_url": f"https://raw.githubusercontent.com/pgmyrek/2025_GenAI_scores_ISCO08/{SOURCE_COMMIT}/{SOURCE_FILE}",
            "workbook_sha256": SOURCE_SHA256,
            "worksheet": "Sheet1",
            "fields": ["ISCO_08", "Title", "mean_score_2025", "SD_2025", "potential25"],
            "retrieved_on": "2026-09-15",
            "scale": [0, 1],
            "occupation_count": len(records),
            "task_count": sum(tasks.values()),
            "provenance": "The official paper links to this author's dataset on printed page 37 (PDF page 40).",
            "transformation": "Select published 2025 occupation means, SDs and gradients; deduplicate task rows by ISCO_08. Do not recompute rounded means or gradient assignments.",
        },
        "occupations": records,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "data/ilo_genai_2025/occupations.json")
    args = parser.parse_args()
    result = extract(args.workbook)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Extracted {len(result['occupations'])} occupations from verified source to {args.output}")


if __name__ == "__main__":
    main()
