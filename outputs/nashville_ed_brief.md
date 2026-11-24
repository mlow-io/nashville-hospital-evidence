# Nashville-Area Emergency Department Measurement Brief (CMS Release Comparison Guardrail)

**Scope:** Five selected Middle Tennessee acute-care hospitals · **CMS Releases:** Timely Care (`yv7e-xc69`, modified `2026-10-19`), Hospital General Info (`xubh-q36u`, modified `2026-10-26`), Footnotes (`y9us-9xdf`, modified `2025-09-18`).

## Headline Finding

One single CMS Hospital Compare release (`yv7e-xc69`) publishes **two different measurement years side by side**:
- **`OP_18b` (Median ED time before departure, discharged patients, in minutes):** measured across **calendar year 2025 (`01/01/2025`–`12/31/2025`)**.
- **`OP_22` (Left before being seen by a healthcare professional, percentage):** measured across **calendar year 2024 (`01/01/2024`–`12/31/2024`)**.

Treating both columns as the same reporting year—or replacing `Not Available` with `0%`—produces false hospital comparisons.

## Selected Five-Hospital Evidence Table

| Facility ID | Hospital Name (CMS Source) | City / ZIP | `OP_18b` Median Minutes (**2025**) | `OP_18b` Cases | `OP_22` Left Before Seen (**2024**) | `OP_22` Sample | Source Rows |
|---|---|---|---:|---:|---:|---:|---|
| `440029` | WILLIAMSON MEDICAL CENTER | FRANKLIN, TN `37067` | 193 min | 373 | 1% | 58,003 | rows 129310, 129313 |
| `440039` | VANDERBILT UNIVERSITY MEDICAL CENTER | NASHVILLE, TN `37232` | 267 min | 355 | 1% | 140,484 | rows 129555, 129558 |
| `440073` | MAURY REGIONAL HOSPITAL | COLUMBIA, TN `38401` | 204 min | 366 | 2% | 49,044 | rows 130115, 130118 |
| `440082` | ASCENSION SAINT THOMAS HOSPITAL | NASHVILLE, TN `37205` | 192 min | 764 | Not Available; Footnote 5 ([5] Results are not available for this reporting period.) | Not Available | rows 130185, 130188 |
| `440161` | TRISTAR CENTENNIAL MEDICAL CENTER | NASHVILLE, TN `37203` | 118 min | 418 | 1% | 77,093 | rows 130949, 130952 |

## Mandatory Limitations & Misinterpretation Guardrails

1. **Not today's live ER wait time:** `OP_18b` is a historical annual median (`01/01/2025`–`12/31/2025`) for discharged ED patients, excluding patients admitted to the hospital, transfers, and psychiatric/mental-health visits per CMS measure definitions.
2. **Mismatched reporting periods inside one file:** `OP_18b` covers **2025**, whereas `OP_22` covers **2024**. Never chart or compare them as simultaneous same-year performance.
3. **Unavailable values stay unavailable:** Ascension Saint Thomas Hospital (`440082`) reports `OP_22 = Not Available` with **Footnote 5** (*"Results are not available for this reporting period."*). Footnote 5 does not state an underlying operational cause and must never be coerced to `0%`.
4. **Deliberate nearby cohort, not a ranking:** These five facilities are a purposefully selected Middle Tennessee comparison set, not a census of all Tennessee hospitals and not a "best hospital" ranking.
5. **CMS publication is not Medicare-only:** Published Hospital Compare timely-care metrics reflect all eligible cases defined in the measure specification rather than Medicare fee-for-service alone.

## Audit Reconciliation & Source Links

- **Row reconciliation:** `161,313` raw rows scanned in `Timely_and_Effective_Care-Hospital.csv` = `10` retained in-scope observations + `161,303` out-of-scope rows discarded (0 silent drops).
- **Measures CSV (`yv7e-xc69`):** https://data.cms.gov/provider-data/sites/default/files/resources/0437b5494ac61507ad90f2af6b8085a7_1792599910/Timely_and_Effective_Care-Hospital.csv (`sha256: 473241c09b40010b...`)
- **Hospital Info CSV (`xubh-q36u`):** https://data.cms.gov/provider-data/sites/default/files/resources/d3bf87c5505155f549d603688414f3c6_1793059553/Hospital_General_Information_2.csv (`sha256: ff2a82a7149975fb...`)
- **Footnote Crosswalk (`y9us-9xdf`):** https://data.cms.gov/provider-data/sites/default/files/resources/f29bb7c812e242f6edfef0a4b7d0eaca_1760630713/Footnote_Crosswalk.csv (`sha256: 5214e1468fb04c5c...`)
