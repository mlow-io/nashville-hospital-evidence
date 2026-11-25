# Nashville Hospital Evidence & Reconciliation Pack (`S1 → M1 + Sparse Archives + S2 RCM`)

An auditable SQLite, SQL, Python, and Excel reporting package using live pinned CMS Hospital Compare datasets (`yv7e-xc69`, `xubh-q36u`, `y9us-9xdf`), three historical CMS Hospital Archive releases (`2026-08-13`, `2026-09-30`, `2026-11-12`), and 2024 CMS Medicare Inpatient Hospitals by Provider and Service across five Middle Tennessee acute-care hospitals (`440029`, `440039`, `440073`, `440082`, `440161`).

## Reconciliations Included

1. **`S1` Core ED Measurement Guardrail:** Flags mixed reporting years (`2025` `OP_18b` minutes vs. `2024` `OP_22` %) inside the same CMS release and preserves `Not Available` (`Footnote 5` on `440082`) without coercing missingness to zero.
2. **Reconciliation #4 — `M1` & Sparse CMS Archive Monitor (`2026-08-13 → 2026-09-30 → 2026-11-12`):** Rejects the similarly named Rural Emergency Hospital CSV (`97xg-v3wv`), preserves hospitals across sparse `2026-09-30` updates by carrying forward `2026-08-13`, classifies 9-month collection-window overlaps cleanly (`190 → 193` min at Williamson Medical Center), and exports SQL-tied workbook tabs.
3. **Reconciliation #5 — Charge vs. Payment RCM (`S2`, 2024 Medicare Inpatient DRGs):** Computes discharge-weighted hospital averages across `709` Nashville DRG rows (`SUM(Tot_Dschrgs * Avg) / SUM(Tot_Dschrgs)`), exposes why unweighted averages distort totals, and separates chargemaster list prices from actual Medicare FFS payments.
4. **Reconciliation #6 — Hospital Cost Reports (`A2` Lite HCRIS `2022–2024`) & CMS CERT Payment Integrity (`S5` RY 2025):** Adds 15 all-payer hospital cost-report rows (`calendar_aligned` vs. `fiscal_year_offset` guardrails, gross charges vs. contractual allowances vs. net patient revenue vs. patient-service income vs. total net income) alongside RY 2025 CERT unweighted sample claim lines vs. distinct claims (`163,940` lines across `37,581` claims) and an explicit illustrative `837 → 835 / EFT / EOB` ledger.

## Quickstart

```sh
python3 -m venv .venv && source .venv/bin/activate
python3 -m pip install -e ".[dev]"

# 1. Fetch live CMS Timely Care, archives, footnotes, 2024 Inpatient DRG, HCRIS, and CERT data
PYTHONPATH=src python3 -m nashville_ed.fetch data/raw
PYTHONPATH=src python3 -m nashville_ed.fetch_extended data/raw
PYTHONPATH=src python3 -m nashville_ed.fetch_finance data/raw outputs

# 2. Build S1 brief + M1 SQLite warehouse + Excel workbook + Reconciliations #4/#5/#6
PYTHONPATH=src python3 -m nashville_ed.build_brief data/raw outputs
PYTHONPATH=src python3 -m nashville_ed.build_pack .
PYTHONPATH=src python3 -m nashville_ed.build_finance_pack .

# 3. Verify reference rows, sparse archives, HCRIS/CERT guards, SQL-to-Excel parity, and mutation tests
PYTHONPATH=src python3 -m pytest -v
```

## Outputs

- [`outputs/Nashville_Hospital_Evidence_Pack.xlsx`](outputs/Nashville_Hospital_Evidence_Pack.xlsx) — 8-tab Excel workbook (`Observations_M1`, `Sparse_Archive_Diffs`, `Charge_vs_Payment_RCM`, `Data_Dictionary`, `Exceptions_and_Caveats`, `Sources_and_Audit`, `HCRIS_5_Hospitals`, `CERT_Error_Categories`)
- [`outputs/reconciliation_4_hospital_releases.md`](outputs/reconciliation_4_hospital_releases.md) — Sparse archive & 9-month period-overlap reconciliation
- [`outputs/reconciliation_5_charge_vs_payment.md`](outputs/reconciliation_5_charge_vs_payment.md) — Discharge-weighted Inpatient Charge vs. Payment report
- [`outputs/reconciliation_6_hospital_costs_and_cert.md`](outputs/reconciliation_6_hospital_costs_and_cert.md) — HCRIS all-payer hospital finance (`2022–2024`), RY 2025 CERT error categories, & illustrative `837/835` math
- [`outputs/nashville_ed_brief.md`](outputs/nashville_ed_brief.md) · [`sql/reporting_queries.sql`](sql/reporting_queries.sql) · [`EXPLAIN_BACK.md`](EXPLAIN_BACK.md)
