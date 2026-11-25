# Five-Minute Explain-Back Guide (`S1 → M1 + Sparse Archives + S2 RCM`)

Review these questions out loud without looking at the code before any healthcare data or analyst interview:

---

### Part 1 — Core S1 Measurement & Reconciliation

1. **Why are there 10 rows in `S1` (and 20 in `M1`) when we only selected 5 hospitals?**
   Because the **grain** of `Timely_and_Effective_Care-Hospital.csv` (`yv7e-xc69`) is **one row per facility + measure + collection period**, not one row per hospital.
2. **Why can’t you compare `OP_18b` and `OP_22` as the same year?**
   Inside the November 2026 CMS release, `OP_18b` (median minutes, discharged cohort) covers **2025**, whereas `OP_22` (% left before being seen) covers **2024**.
3. **Why doesn’t Ascension Saint Thomas show `0%` for `OP_22`?**
   It carries `"Not Available"` with **Footnote 5** (*"Results are not available for this reporting period."*). Turning missing text into `0` invents zero walkouts.
4. **Why reconcile `raw_total == retained + discarded` and test duplicate Facility IDs?**
   To prove 0 rows silently vanished from the 161,313-row CMS release and ensure a `LEFT JOIN` to Hospital General Info cannot multiply rows silently.

---

### Part 2 — Reconciliation #4: Sparse CMS Archives (`2026-08-13` → `2026-09-30` → `2026-11-12`)

5. **Why did the September `2026-09-30` archive show no `OP_18b` update, and why didn't we delete the 5 hospitals?**
   The `2026-09-30` CMS hospital archive (3.15 MB, 10 files) only shipped Complications/Deaths updates and omitted `yv7e-xc69`. Modeling **archive events** separately from **established dataset versions** lets `resolve_as_of_date("2026-09-30")` carry forward `2026-08-13` cleanly instead of erasing hospitals—while failing closed before the first base exists.
6. **Why did we select `yv7e-xc69` by dataset ID and reject `97xg-v3wv`?**
   Both `2026-08-13` and `2026-11-12` include `97xg-v3wv_..._REH_Timely_and_Effective_Care-Hospital.csv` (Rural Emergency Hospitals). Selecting strictly by dataset ID (`yv7e-xc69`) and excluding `__MACOSX/` prevents mixing in the wrong facility cohort.
7. **Williamson Medical Center’s `OP_18b` moved `190 → 193` min (`2026-08-13` → `2026-11-12`). Can we call that worsening ER delays?**
   No—because `2026-08-13` measured `10/01/2024–09/30/2025` while `2026-11-12` measured `01/01/2025–12/31/2025`. Those windows overlap **9 months (`Jan–Sep 2025`)**, so this is a rolling-window refresh, not an independent quarter trend.

---

### Part 3 — Reconciliation #5: Medicare Inpatient Charge vs. Payment (`S2`)

8. **Why is a hospital’s average "submitted charge" never revenue—and not what patients owe?**
   `Avg_Submtd_Cvrd_Chrg` reflects gross chargemaster list prices before contractual discounts. Medicare pays fixed MS-DRG prospective amounts (`Avg_Mdcr_Pymt_Amt`, plus beneficiary deductibles/coinsurance inside `Avg_Tot_Pymt_Amt`), often a fraction of gross charges—and this dataset covers Medicare FFS discharges only.
9. **Why must hospital averages across DRGs be weighted by `Tot_Dschrgs`?**
   Because a DRG with 400 stays carries 40× the volume of a rare DRG with 10 stays; taking `AVG(avg_submtd_cvrd_chrg)` gives equal weight to rare procedures and misstates hospital totals.
