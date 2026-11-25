# Reconciliation #6: Hospital Cost Reports (`A2` Lite HCRIS) & Payment Integrity (`S5` CMS CERT)

> [!IMPORTANT]
> **Two-Scope Boundary:** HCRIS Cost Reports measure **all-payer, inpatient + outpatient** hospital finances over each facility's own fiscal year (`Jul 1–Jun 30` for 4 hospitals vs. `Jan 1–Dec 31` for TriStar Centennial). **Never** divide HCRIS `Total Costs` by CY 2024 Medicare Inpatient DRG discharges. Separately, RY 2025 CMS CERT PUF counts below are **unweighted sample claim lines and distinct claims**—never national weighted dollar improper-payment rates, and **improper payment ≠ fraud**.

## Part A — 5 Nashville Hospitals in CMS HCRIS (`FY 2022–2024` Releases)

Each release shows **Chargemaster Gross Patient Revenue** vs. **Contractual Allowances** vs. **Net Patient Revenue** vs. **Total Operating Expense / Patient Service Income** vs. **Other Non-Patient Income**.

| Release | CCN | Hospital | Fiscal Period | Alignment vs. CY | Gross Charges | Contractual Adj. (%) | Net Patient Rev | Patient Service Income (Op Margin) | Non-Patient Other Income | Total Net Income | CCR |
|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| `2024` | `440029` | WILLIAMSON HEALTH | `2024-07-01..2025-06-30` | `fiscal_year_offset` | $1,125.7M | $818.7M (72.7%) | $307.0M | $-15.1M (-4.9%) | $36.0M | $20.9M | 0.225 |
| `2024` | `440039` | VANDERBILT UNIVERSITY MEDICAL CENTER | `2024-07-01..2025-06-30` | `fiscal_year_offset` | $22,858.7M | $15,955.1M (69.8%) | $6,903.6M | $-813.7M (-11.8%) | $1,243.4M | $429.7M | 0.206 |
| `2024` | `440073` | MAURY REGIONAL HOSPITAL | `2024-07-01..2025-06-30` | `fiscal_year_offset` | $1,618.7M | $1,256.0M (77.6%) | $362.7M | $-42.8M (-11.8%) | $84.9M | $42.0M | 0.214 |
| `2024` | `440082` | SAINT THOMAS WEST HOSPITAL | `2024-07-01..2025-06-30` | `fiscal_year_offset` | $6,310.2M | $5,078.6M (80.5%) | $1,231.6M | $69.0M (5.6%) | $24.6M | $86.5M | 0.163 |
| `2024` | `440161` | TRISTAR CENTENNIAL MEDICAL CENTER | `2024-01-01..2024-12-31` | `calendar_aligned` | $8,506.8M | $7,358.8M (86.5%) | $1,148.0M | $383.1M (33.4%) | $12.6M | $395.7M | 0.088 |
| `2023` | `440029` | WILLIAMSON HEALTH | `2023-07-01..2024-06-30` | `fiscal_year_offset` | $1,028.9M | $743.3M (72.2%) | $285.6M | $-8.1M (-2.8%) | $24.9M | $16.9M | 0.228 |
| `2023` | `440039` | VANDERBILT UNIVERSITY MEDICAL CENTER | `2023-07-01..2024-06-30` | `fiscal_year_offset` | $20,533.0M | $14,453.1M (70.4%) | $6,079.9M | $-856.0M (-14.1%) | $1,194.7M | $338.8M | 0.209 |
| `2023` | `440073` | MAURY REGIONAL HOSPITAL | `2023-07-01..2024-06-30` | `fiscal_year_offset` | $1,498.4M | $1,156.7M (77.2%) | $341.6M | $-29.3M (-8.6%) | $55.5M | $26.2M | 0.222 |
| `2023` | `440082` | SAINT THOMAS WEST HOSPITAL | `2023-07-01..2024-06-30` | `fiscal_year_offset` | $5,583.5M | $4,451.2M (79.7%) | $1,132.3M | $-25.1M (-2.2%) | $114.6M | $85.2M | 0.184 |
| `2023` | `440161` | TRISTAR CENTENNIAL MEDICAL CENTER | `2023-01-01..2023-12-31` | `calendar_aligned` | $7,543.6M | $6,486.4M (86.0%) | $1,057.2M | $320.5M (30.3%) | $13.5M | $334.0M | 0.097 |
| `2022` | `440029` | WILLIAMSON HEALTH | `2022-07-01..2023-06-30` | `fiscal_year_offset` | $961.1M | $689.7M (71.8%) | $271.4M | $-8.9M (-3.3%) | $38.7M | $29.8M | 0.232 |
| `2022` | `440039` | VANDERBILT UNIVERSITY MEDICAL CENTER | `2022-07-01..2023-06-30` | `fiscal_year_offset` | $18,278.6M | $12,836.9M (70.2%) | $5,441.7M | $-864.3M (-15.9%) | $1,047.0M | $174.2M | 0.215 |
| `2022` | `440073` | MAURY REGIONAL HOSPITAL | `2022-07-01..2023-06-30` | `fiscal_year_offset` | $1,474.9M | $1,140.9M (77.4%) | $334.0M | $-32.5M (-9.7%) | $42.6M | $10.1M | 0.223 |
| `2022` | `440082` | SAINT THOMAS WEST HOSPITAL | `2022-07-01..2023-06-30` | `fiscal_year_offset` | $5,264.3M | $4,208.6M (79.9%) | $1,055.6M | $2.4M (0.2%) | $58.7M | $57.9M | 0.177 |
| `2022` | `440161` | TRISTAR CENTENNIAL MEDICAL CENTER | `2022-01-01..2022-12-31` | `calendar_aligned` | $6,894.5M | $5,902.7M (85.6%) | $991.8M | $228.0M (23.0%) | $3.2M | $231.2M | 0.104 |

### HCRIS Key Operational Takeaways (Latest 2024 Release)
- **Fiscal-year mismatch across the same Nashville street grid:** TriStar Centennial (`440161`) reports on calendar year `2024-01-01..2024-12-31`, while Williamson (`440029`), Vanderbilt (`440039`), Maury (`440073`), and Saint Thomas (`440082`) report on `2024-07-01..2025-06-30`.
- **Gross Charges vs. Net Patient Revenue:** Across all 5 hospitals in `2024`, `69.8%` to `86.5%` of gross chargemaster bills are written off immediately as contractual allowances (`Total Patient Revenue - Contractual Allowance = Net Patient Revenue`).
- **Operating Patient Income vs. Total Net Income:** For example, Vanderbilt (`2024`) shows `$-813.7M` patient-service loss alongside `+$1,243.4M` non-patient other income (`+$429.7M` total net income)—do **not** conflate the two.

---

## Part B — CMS CERT RY 2025 Improper Payment Categories (`S5`)

- **Dataset & Grain Trap Caught:** PUF `6395b458-2f89-4828-8c1a-e1e16b723d48` contains **163,940 claim-line rows** across **37,581 distinct sampled claims** (`1,400` claims carry multiple decision/error lines—mainly outpatient/institutional Part A Non-IPPS).
- **Compliance ≠ Fraud:** `Insufficient Documentation`, `No Documentation`, `Incorrect Coding`, and `Medical Necessity` measure documentation and Medicare coverage compliance, **not** provider fraud. Notice `Overturned` (`Agree`) lines reflect initial errors successfully resolved on appeal.

| Medicare Part | Review Decision | Error Code | Category | Unweighted Lines | Distinct Claims | % of Part Lines |
|---|---|---|---|---:|---:|---:|
| `1. Part B` | `Agree` | `-` | `no_error_agreed_sample_line` | 20,282 | 9,712 | 81.41% |
| `1. Part B` | `Disagree` | `Insufficient Documentation` | `insufficient_documentation_compliance_not_fraud` | 2,528 | 1,275 | 10.15% |
| `1. Part B` | `Disagree` | `Incorrect Coding` | `coding_or_drg_hcpcs_mismatch_not_fraud` | 806 | 702 | 3.24% |
| `1. Part B` | `Disagree` | `No Documentation` | `missing_documentation_compliance_not_fraud` | 614 | 237 | 2.46% |
| `1. Part B` | `Agree` | `Overturned` | `initial_error_overturned_on_review_appeal` | 406 | 234 | 1.63% |
| `1. Part B` | `Disagree` | `Other` | `other_administrative_or_eligibility_error_not_fraud` | 182 | 136 | 0.73% |
| `1. Part B` | `Disagree` | `Medical Necessity` | `medical_necessity_coverage_denial_not_fraud` | 94 | 29 | 0.38% |
| `2. DME MAC` | `Agree` | `-` | `no_error_agreed_sample_line` | 15,212 | 6,990 | 78.63% |
| `2. DME MAC` | `Disagree` | `Insufficient Documentation` | `insufficient_documentation_compliance_not_fraud` | 1,476 | 1,001 | 7.63% |
| `2. DME MAC` | `Disagree` | `Other` | `other_administrative_or_eligibility_error_not_fraud` | 701 | 430 | 3.62% |
| `2. DME MAC` | `Disagree` | `No Documentation` | `missing_documentation_compliance_not_fraud` | 677 | 190 | 3.50% |
| `2. DME MAC` | `Disagree` | `Medical Necessity` | `medical_necessity_coverage_denial_not_fraud` | 616 | 350 | 3.18% |
| `2. DME MAC` | `Agree` | `Overturned` | `initial_error_overturned_on_review_appeal` | 587 | 292 | 3.03% |
| `2. DME MAC` | `Disagree` | `Incorrect Coding` | `coding_or_drg_hcpcs_mismatch_not_fraud` | 77 | 71 | 0.40% |
| `3. Part A(Excluding Inpatient Hospital PPS)` | `Agree` | `-` | `no_error_agreed_sample_line` | 94,977 | 7,163 | 85.62% |
| `3. Part A(Excluding Inpatient Hospital PPS)` | `Disagree` | `Insufficient Documentation` | `insufficient_documentation_compliance_not_fraud` | 4,589 | 448 | 4.14% |
| `3. Part A(Excluding Inpatient Hospital PPS)` | `Disagree` | `Other` | `other_administrative_or_eligibility_error_not_fraud` | 3,726 | 453 | 3.36% |
| `3. Part A(Excluding Inpatient Hospital PPS)` | `Disagree` | `Medical Necessity` | `medical_necessity_coverage_denial_not_fraud` | 2,823 | 223 | 2.54% |
| `3. Part A(Excluding Inpatient Hospital PPS)` | `Disagree` | `Incorrect Coding` | `coding_or_drg_hcpcs_mismatch_not_fraud` | 2,348 | 133 | 2.12% |
| `3. Part A(Excluding Inpatient Hospital PPS)` | `Agree` | `Overturned` | `initial_error_overturned_on_review_appeal` | 2,121 | 190 | 1.91% |
| `3. Part A(Excluding Inpatient Hospital PPS)` | `Disagree` | `No Documentation` | `missing_documentation_compliance_not_fraud` | 348 | 41 | 0.31% |
| `4. Part A(Inpatient Hospital PPS)` | `Agree` | `-` | `no_error_agreed_sample_line` | 6,988 | 6,988 | 79.86% |
| `4. Part A(Inpatient Hospital PPS)` | `Disagree` | `Incorrect Coding` | `coding_or_drg_hcpcs_mismatch_not_fraud` | 798 | 798 | 9.12% |
| `4. Part A(Inpatient Hospital PPS)` | `Disagree` | `Medical Necessity` | `medical_necessity_coverage_denial_not_fraud` | 463 | 463 | 5.29% |
| `4. Part A(Inpatient Hospital PPS)` | `Agree` | `Overturned` | `initial_error_overturned_on_review_appeal` | 248 | 248 | 2.83% |
| `4. Part A(Inpatient Hospital PPS)` | `Disagree` | `Insufficient Documentation` | `insufficient_documentation_compliance_not_fraud` | 220 | 220 | 2.51% |
| `4. Part A(Inpatient Hospital PPS)` | `Disagree` | `No Documentation` | `missing_documentation_compliance_not_fraud` | 26 | 26 | 0.30% |
| `4. Part A(Inpatient Hospital PPS)` | `Disagree` | `Other` | `other_administrative_or_eligibility_error_not_fraud` | 7 | 7 | 0.08% |

---

## Part C — Illustrative `837 → 835 / EFT / EOB` Revenue-Cycle Math Appendix

> [!NOTE]
> **`ILLUSTRATIVE EXAMPLE — NOT REAL PATIENT DATA`:** Because live clearinghouse EDI files (`837` submitted claims / `835` ERA remittances) are private under HIPAA, the bounded example below demonstrates the exact accounting vocabulary absent from aggregate public files.

| Step / Transaction | Amount / Math | Operational Meaning |
|---|---:|---|
| Billed Charge (`X12 837` Claim) | **$200.00** | Provider's chargemaster fee submitted to payer (like HCRIS Gross Charge) |
| Contracted Allowed Amount (Fee Schedule) | **$120.00** | Maximum payable amount under in-network contract |
| Contractual Adjustment (`X12 835` CO-45) | **-$80.00** | `$200 - $120` mandatory write-off; patient is **never** billed this for in-network care |
| Insurer Payment (`X12 835` + `EFT`) | **$96.00** | `80%` plan share paid to provider via Electronic Funds Transfer (`EFT`) alongside `835` ERA |
| Patient Responsibility (`EOB` / PR-1/2/3) | **$24.00** | `20%` coinsurance/deductible shifted to patient statement (`EOB`) |
| Point-of-Service Collection | **-$10.00** | Amount already collected at check-in |
| **Remaining Patient AR Balance** | **$14.00** | `$24.00 - $10.00` remaining collectible patient balance (never `$200 - $96 - $10 = $94`) |
