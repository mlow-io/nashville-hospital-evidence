# Nashville ED Measurement Brief (`S1`)

A compact, auditable reporting package comparing two Emergency Department measures (`OP_18b` and `OP_22`) across five Middle Tennessee hospitals using live pinned CMS Provider Data releases (`yv7e-xc69`, `xubh-q36u`, `y9us-9xdf`).

## Key Finding

Within the same CMS Hospital Compare release file, **`OP_18b`** (median ED duration, discharged cohort, minutes) covers **calendar year 2025**, while **`OP_22`** (left without being seen, %) covers **calendar year 2024**—and Ascension Saint Thomas (`440082`) carries `Not Available` (`Footnote 5`) rather than zero.

## Quickstart

```sh
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e ".[dev]"

# 1. Fetch and hash immutable raw CMS inputs into data/raw/
PYTHONPATH=src python3 -m nashville_ed.fetch data/raw

# 2. Build CSV, Markdown, HTML brief, and SHA-256 reconciliation receipt into outputs/
PYTHONPATH=src python3 -m nashville_ed.build_brief data/raw outputs

# 3. Verify reference rows + deliberate mutation failure checks
pytest -v
```

## Outputs

- [`outputs/nashville_ed_brief.md`](outputs/nashville_ed_brief.md) & `outputs/nashville_ed_brief.html` — One-page manager brief with period labels, Footnote 5 decoded, and Limitations box
- [`outputs/nashville_ed_observations.csv`](outputs/nashville_ed_observations.csv) — 10-row extract preserving raw strings, source row numbers, text IDs/ZIPs, and nullable parsed scores
- [`outputs/receipt.json`](outputs/receipt.json) & [`outputs/receipt.md`](outputs/receipt.md) — Pinned CMS release metadata, SHA-256 digests, and `raw = retained + discarded` row accounting
- [`EXPLAIN_BACK.md`](EXPLAIN_BACK.md) — 5-minute plain-English interview walkthrough
