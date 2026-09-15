# ILO / NASK 2025 GenAI occupation reference

This is a factual-field extract from the first author's published dataset for
**Gmyrek et al. (2025), ILO Working Paper 140**, DOI
[10.54394/HETP0387](https://doi.org/10.54394/HETP0387).
The [official ILO paper](https://www.ilo.org/sites/default/files/2025-05/WP140_web.pdf)
links to the author's data visualization on printed page 37 / PDF page 40.

- Upstream repository: https://github.com/pgmyrek/2025_GenAI_scores_ISCO08
- Pinned commit: `ca5de1ad757ea0f41f1ee5162665ddda1b8f9bb7`
- Workbook: `Final_Scores_ISCO08_Gmyrek_et_al_2025.xlsx`, `Sheet1`
- SHA-256: `c1940b87e7293b1eb95b530b6d3da7cd806b61d217c4bff1e69372b2cff5c90a`
- Retrieved: 2026-09-15. Capability reference: **start of 2025**, not 2026.
- 3,265 task rows, deduplicated into 427 scored ISCO-08 four-digit unit groups.

| Extract field | Workbook field |
| --- | --- |
| `code` | `ISCO_08` (string, four digits) |
| `title_en` | `Title` |
| `mean` | `mean_score_2025` (published, already rounded) |
| `sd` | `SD_2025` (published, already rounded) |
| `gradient` | `potential25` (preserve the author's classification) |
| `task_count` | Number of task rows for the occupation |

Do not average the repeated occupation means over all task rows: this would
incorrectly give occupations with more listed tasks greater weight. Do not
reclassify gradients from rounded mean/SD fields: preserve `potential25`.
Gradient counts are 231 Not Exposed, 84 Minimal Exposure, and 17/44/38/13 in
Gradients 1/2/3/4 respectively. Not Exposed does not imply a zero score.

The source's four-digit classification is shown only for individual four-digit
occupations. The map's group-level equal-weight averages, country employment
weights, coverage and composition ranges are **our derived reference values**.
We do not claim they are official national ILO estimates or actual adoption.

To reproduce the extract, download the pinned workbook using `download_url`
in `occupations.json`, then run:

```bash
python scripts/import_ilo_genai.py /path/to/Final_Scores_ISCO08_Gmyrek_et_al_2025.xlsx
python ai_exposure.py
```

The importer uses the Python standard library and verifies the exact source
checksum, repeated fields, scale, category names and record counts. Both the
extract and site enrichment are deterministic and run offline from local inputs.
The full source workbook remains available at its pinned upstream URL.

Attribution: Gmyrek, P., Berg, J., Kamiński, K., Konopczyński, F., Ładna, A.,
Nafradi, B., Rosłaniec, K., Troszyński, M. (2025). *Generative AI and Jobs:
A Refined Global Index of Occupational Exposure.* ILO Working Paper 140.
Geneva: International Labour Office. © ILO. The paper is CC BY 4.0.

This is an adaptation of a copyrighted work of the International Labour
Organization (ILO). This adaptation has not been prepared, reviewed or endorsed
by the ILO and should not be considered an official ILO adaptation. The ILO
disclaims all responsibility for its content and accuracy. Responsibility rests
solely with the author(s) of the adaptation.
