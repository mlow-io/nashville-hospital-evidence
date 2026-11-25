"""Build HCRIS Hospital Cost Report & CMS CERT 2025 Payment Integrity outputs (Plan #4: S5 + A2 Lite)."""
from __future__ import annotations

import csv
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

from .build_pack import _query_rows, _split_named_queries

CERT_CATEGORY_MAP: dict[tuple[str, str], str] = {
    ("Agree", "-"): "no_error_agreed_sample_line",
    ("Agree", "Overturned"): "initial_error_overturned_on_review_appeal",
    ("Disagree", "Insufficient Documentation"): "insufficient_documentation_compliance_not_fraud",
    ("Disagree", "No Documentation"): "missing_documentation_compliance_not_fraud",
    ("Disagree", "Incorrect Coding"): "coding_or_drg_hcpcs_mismatch_not_fraud",
    ("Disagree", "Medical Necessity"): "medical_necessity_coverage_denial_not_fraud",
    ("Disagree", "Other"): "other_administrative_or_eligibility_error_not_fraud",
}


def _parse_int_opt(val: Any) -> int | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    return int(float(s))


def _parse_float_opt(val: Any) -> float | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    return float(s)


def classify_fiscal_alignment(release_year: str, fy_begin: str, fy_end: str) -> str:
    """Distinguish exact calendar-year alignment from offset hospital fiscal years."""
    if fy_begin == f"{release_year}-01-01" and fy_end == f"{release_year}-12-31":
        return "calendar_aligned"
    return "fiscal_year_offset"


def map_cert_category(review_decision: str, error_code: str) -> str:
    """Map CERT PUF review decision & error code while preserving unknown codes visibly."""
    key = (review_decision.strip(), error_code.strip())
    if key in CERT_CATEGORY_MAP:
        return CERT_CATEGORY_MAP[key]
    slug = "_".join(error_code.strip().lower().split()) or "blank"
    dec = review_decision.strip().lower() or "unknown"
    return f"unmapped_{dec}_{slug}"


def prepare_hcris_rows(raw_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize HCRIS rows without silently collapsing multiple reports per CCN/year."""
    counts_by_ccn_year: Counter[tuple[str, str]] = Counter()
    for row in raw_rows:
        ccn = str(row.get("Provider CCN") or "").strip()
        yr = str(row.get("_hcris_release_year") or "").strip()
        counts_by_ccn_year[(ccn, yr)] += 1

    prepared: list[dict[str, Any]] = []
    seen_pks: set[tuple[str, str]] = set()
    for row in raw_rows:
        rpt = str(row.get("rpt_rec_num") or "").strip()
        yr = str(row.get("_hcris_release_year") or "").strip()
        ccn = str(row.get("Provider CCN") or "").strip()
        if not rpt or not yr or not ccn:
            raise ValueError(f"Missing primary key fields in HCRIS row: {row!r}")
        if (rpt, yr) in seen_pks:
            raise ValueError(f"Duplicate HCRIS (rpt_rec_num={rpt}, year={yr})")
        seen_pks.add((rpt, yr))
        fy_begin = str(row.get("Fiscal Year Begin Date") or "").strip()
        fy_end = str(row.get("Fiscal Year End Date") or "").strip()
        prepared.append(
            {
                "rpt_rec_num": rpt,
                "hcris_release_year": yr,
                "dataset_id": str(row.get("_hcris_dataset_id") or "").strip(),
                "ccn": ccn,
                "hospital_name": str(row.get("Hospital Name") or "").strip(),
                "fy_begin": fy_begin,
                "fy_end": fy_end,
                "period_alignment_status": classify_fiscal_alignment(yr, fy_begin, fy_end),
                "report_count_in_year": counts_by_ccn_year[(ccn, yr)],
                "rural_versus_urban": str(row.get("Rural Versus Urban") or "").strip(),
                "provider_type": str(row.get("Provider Type") or "").strip(),
                "type_of_control": str(row.get("Type of Control") or "").strip(),
                "beds": _parse_int_opt(row.get("Number of Beds")),
                "medicare_discharges": _parse_int_opt(row.get("Total Discharges Title XVIII")),
                "medicaid_discharges": _parse_int_opt(row.get("Total Discharges Title XIX")),
                "total_discharges": _parse_int_opt(row.get("Total Discharges (V + XVIII + XIX + Unknown)")),
                "inpatient_charges": _parse_float_opt(row.get("Inpatient Total Charges")),
                "outpatient_charges": _parse_float_opt(row.get("Outpatient Total Charges")),
                "total_patient_revenue": _parse_float_opt(row.get("Total Patient Revenue")),
                "contractual_allowance": _parse_float_opt(
                    row.get("Less Contractual Allowance and Discounts on Patients' Accounts")
                ),
                "net_patient_revenue": _parse_float_opt(row.get("Net Patient Revenue")),
                "total_costs": _parse_float_opt(row.get("Total Costs")),
                "operating_expense": _parse_float_opt(row.get("Less Total Operating Expense")),
                "net_income_patient_service": _parse_float_opt(row.get("Net Income from Service to Patients")),
                "total_other_income": _parse_float_opt(row.get("Total Other Income")),
                "net_income": _parse_float_opt(row.get("Net Income")),
                "cost_to_charge_ratio": _parse_float_opt(row.get("Cost To Charge Ratio")),
                "charity_care_cost": _parse_float_opt(row.get("Cost of Charity Care")),
                "bad_debt_expense": _parse_float_opt(row.get("Total Bad Debt Expense")),
                "uncompensated_care_cost": _parse_float_opt(row.get("Cost of Uncompensated Care")),
                "medicaid_charges": _parse_float_opt(row.get("Medicaid Charges")),
                "medicaid_net_revenue": _parse_float_opt(row.get("Net Revenue from Medicaid")),
            }
        )
    return prepared


def summarize_cert_csv(cert_csv: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Summarize RY 2025 CERT PUF retaining both unweighted line counts and distinct claim counts."""
    total_lines = 0
    all_claims: set[str] = set()
    part_lines: Counter[str] = Counter()
    part_claims: dict[str, set[str]] = defaultdict(set)
    bucket_lines: Counter[tuple[str, str, str]] = Counter()
    bucket_claims: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    claim_buckets: dict[str, set[tuple[str, str]]] = defaultdict(set)

    with cert_csv.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            total_lines += 1
            ccn_id = (row.get("claim_control_number") or "").strip()
            part = (row.get("Part") or "").strip()
            decision = (row.get("Review Decision") or "").strip()
            err = (row.get("Error Code") or "").strip()
            all_claims.add(ccn_id)
            part_lines[part] += 1
            part_claims[part].add(ccn_id)
            key = (part, decision, err)
            bucket_lines[key] += 1
            bucket_claims[key].add(ccn_id)
            claim_buckets[ccn_id].add((decision, err))

    multi_decision_claims = sum(1 for v in claim_buckets.values() if len(v) > 1)
    summary_rows: list[dict[str, Any]] = []
    scope_note = (
        "Unweighted RY 2025 CERT PUF sample counts only; NOT national weighted Medicare dollar improper-payment rates, "
        "and improper payment is a compliance/documentation measure rather than fraud."
    )
    for (part, decision, err), line_cnt in sorted(bucket_lines.items()):
        p_lines = part_lines[part]
        summary_rows.append(
            {
                "part": part,
                "review_decision": decision,
                "error_code": err,
                "error_category": map_cert_category(decision, err),
                "unweighted_claim_line_count": line_cnt,
                "unweighted_distinct_claim_count": len(bucket_claims[(part, decision, err)]),
                "part_total_lines": p_lines,
                "part_total_distinct_claims": len(part_claims[part]),
                "unweighted_line_share_pct": (line_cnt / p_lines * 100.0) if p_lines else 0.0,
                "measurement_scope_note": scope_note,
            }
        )

    meta = {
        "total_claim_lines": total_lines,
        "distinct_claims": len(all_claims),
        "claims_with_multiple_decisions_across_lines": multi_decision_claims,
        "part_distinct_claims": {p: len(c) for p, c in sorted(part_claims.items())},
        "part_claim_lines": dict(sorted(part_lines.items())),
    }
    return summary_rows, meta


def _write_finance_sheets_to_xlsx(
    xlsx_path: Path,
    db: sqlite3.Connection,
    queries: dict[str, str],
) -> None:
    wb = load_workbook(xlsx_path) if xlsx_path.exists() else Workbook()
    if "Sheet" in wb.sheetnames and len(wb.sheetnames) == 1:
        wb.remove(wb.active)

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")

    for sheet_title, banner, q_name, widths in [
        (
            "HCRIS_5_Hospitals",
            "CMS HCRIS Hospital Cost Reports (All-Payer, Inpatient + Outpatient; compare fiscal periods carefully — NEVER divide HCRIS Total Costs by CY 2024 Medicare DRG discharges)",
            "hcris_hospital_summary",
            {2: 10, 3: 36, 4: 12, 5: 12, 6: 12, 7: 20},
        ),
        (
            "CERT_Error_Categories",
            "RY 2025 CMS CERT PUF Breakdown (Unweighted Sample Lines & Distinct Claims — NOT weighted national dollar rates; Improper Payment != Fraud)",
            "cert_2025_error_breakdown",
            {1: 42, 2: 16, 3: 26, 4: 44, 10: 56},
        ),
    ]:
        if sheet_title in wb.sheetnames:
            del wb[sheet_title]
        ws = wb.create_sheet(title=sheet_title)
        ws.append([banner])
        ws["A1"].font = Font(bold=True, size=11)
        cols, rows = _query_rows(db, queries[q_name])
        ws.append(cols)
        for c_idx in range(1, len(cols) + 1):
            cell = ws.cell(row=2, column=c_idx)
            cell.font = header_font
            cell.fill = header_fill
        for r in rows:
            ws.append(list(r))
        for idx, w in widths.items():
            col_letter = chr(64 + idx)
            ws.column_dimensions[col_letter].width = w
        ws.freeze_panes = "A3"

    wb.save(xlsx_path)


def run_finance_build(root: Path, raw_dir: Path, out_dir: Path) -> dict[str, Any]:
    root = Path(root)
    raw_dir = Path(raw_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fin_dir = raw_dir / "finance"

    hcris_raw = json.loads((fin_dir / "hcris_nashville_2022_2024.json").read_text(encoding="utf-8"))
    hcris_rows = prepare_hcris_rows(hcris_raw)
    cert_rows, cert_meta = summarize_cert_csv(fin_dir / "cert_2025_partA_partB_public_data.csv")
    fin_manifest = json.loads((fin_dir / "finance_manifest.json").read_text(encoding="utf-8"))

    db_path = out_dir / "nashville_hospital_evidence.sqlite3"
    db = sqlite3.connect(db_path)
    db.executescript((root / "sql" / "schema.sql").read_text(encoding="utf-8"))
    db.execute("DELETE FROM hcris_cost_reports")
    db.execute("DELETE FROM cert_2025_summary")

    for r in hcris_rows:
        db.execute(
            """
            INSERT INTO hcris_cost_reports VALUES (
                ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
            )
            """,
            (
                r["rpt_rec_num"], r["hcris_release_year"], r["dataset_id"], r["ccn"], r["hospital_name"],
                r["fy_begin"], r["fy_end"], r["period_alignment_status"], r["report_count_in_year"],
                r["rural_versus_urban"], r["provider_type"], r["type_of_control"], r["beds"],
                r["medicare_discharges"], r["medicaid_discharges"], r["total_discharges"],
                r["inpatient_charges"], r["outpatient_charges"], r["total_patient_revenue"],
                r["contractual_allowance"], r["net_patient_revenue"], r["total_costs"],
                r["operating_expense"], r["net_income_patient_service"], r["total_other_income"],
                r["net_income"], r["cost_to_charge_ratio"], r["charity_care_cost"],
                r["bad_debt_expense"], r["uncompensated_care_cost"], r["medicaid_charges"],
                r["medicaid_net_revenue"],
            ),
        )

    for r in cert_rows:
        db.execute(
            "INSERT INTO cert_2025_summary VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                r["part"], r["review_decision"], r["error_code"], r["error_category"],
                r["unweighted_claim_line_count"], r["unweighted_distinct_claim_count"],
                r["part_total_lines"], r["part_total_distinct_claims"],
                r["unweighted_line_share_pct"], r["measurement_scope_note"],
            ),
        )
    db.commit()

    queries = _split_named_queries(root / "sql" / "reporting_queries.sql")
    _, h_rows = _query_rows(db, queries["hcris_hospital_summary"])
    _, c_rows = _query_rows(db, queries["cert_2025_error_breakdown"])

    xlsx_path = out_dir / "Nashville_Hospital_Evidence_Pack.xlsx"
    _write_finance_sheets_to_xlsx(xlsx_path, db, queries)

    # Generate Reconciliation #6 Markdown report
    lines = [
        "# Reconciliation #6: Hospital Cost Reports (`A2` Lite HCRIS) & Payment Integrity (`S5` CMS CERT)",
        "",
        "> [!IMPORTANT]",
        "> **Two-Scope Boundary:** HCRIS Cost Reports measure **all-payer, inpatient + outpatient** hospital finances over each facility's own fiscal year (`Jul 1–Jun 30` for 4 hospitals vs. `Jan 1–Dec 31` for TriStar Centennial). **Never** divide HCRIS `Total Costs` by CY 2024 Medicare Inpatient DRG discharges. Separately, RY 2025 CMS CERT PUF counts below are **unweighted sample claim lines and distinct claims**—never national weighted dollar improper-payment rates, and **improper payment ≠ fraud**.",
        "",
        "## Part A — 5 Nashville Hospitals in CMS HCRIS (`FY 2022–2024` Releases)",
        "",
        "Each release shows **Chargemaster Gross Patient Revenue** vs. **Contractual Allowances** vs. **Net Patient Revenue** vs. **Total Operating Expense / Patient Service Income** vs. **Other Non-Patient Income**.",
        "",
        "| Release | CCN | Hospital | Fiscal Period | Alignment vs. CY | Gross Charges | Contractual Adj. (%) | Net Patient Rev | Patient Service Income (Op Margin) | Non-Patient Other Income | Total Net Income | CCR |",
        "|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in h_rows:
        (
            yr, ccn, name, _rpt, fyb, fye, align, _cnt, _rvu, _beds, _td, _m18, _m19,
            gross, adj, net_rev, _tcost, _opex, pat_inc, other_inc, net_inc, ccr, _ucc,
            adj_pct, _n2g, pat_margin,
        ) = r
        def _b(v: float | None) -> str:
            return f"${v/1e6:,.1f}M" if v is not None else "NULL"
        ccr_str = f"{ccr:.3f}" if ccr is not None else "NULL"
        pm_str = f"{pat_margin:.1f}%" if pat_margin is not None else "n/a"
        ap_str = f"{adj_pct:.1f}%" if adj_pct is not None else "n/a"
        lines.append(
            f"| `{yr}` | `{ccn}` | {name} | `{fyb}..{fye}` | `{align}` | {_b(gross)} | {_b(adj)} ({ap_str}) | {_b(net_rev)} | {_b(pat_inc)} ({pm_str}) | {_b(other_inc)} | {_b(net_inc)} | {ccr_str} |"
        )

    latest_yr = max((r[0] for r in h_rows), default="2024")
    latest_adj_pcts = [r[23] for r in h_rows if r[0] == latest_yr and r[23] is not None]
    min_adj = min(latest_adj_pcts) if latest_adj_pcts else 0.0
    max_adj = max(latest_adj_pcts) if latest_adj_pcts else 0.0
    vumc_24 = next((r for r in h_rows if r[0] == latest_yr and r[1] == "440039"), None)
    vumc_line = (
        f"For example, Vanderbilt (`{latest_yr}`) shows `${vumc_24[18]/1e6:,.1f}M` patient-service loss alongside "
        f"`+${vumc_24[19]/1e6:,.1f}M` non-patient other income (`+${vumc_24[20]/1e6:,.1f}M` total net income)—do **not** conflate the two."
        if vumc_24 and vumc_24[18] is not None and vumc_24[19] is not None and vumc_24[20] is not None
        else "Hospital patient-service margin differs sharply from bottom-line total net income—do **not** conflate the two."
    )

    lines.extend([
        "",
        f"### HCRIS Key Operational Takeaways (Latest {latest_yr} Release)",
        "- **Fiscal-year mismatch across the same Nashville street grid:** TriStar Centennial (`440161`) reports on calendar year `2024-01-01..2024-12-31`, while Williamson (`440029`), Vanderbilt (`440039`), Maury (`440073`), and Saint Thomas (`440082`) report on `2024-07-01..2025-06-30`.",
        f"- **Gross Charges vs. Net Patient Revenue:** Across all 5 hospitals in `{latest_yr}`, `{min_adj:.1f}%` to `{max_adj:.1f}%` of gross chargemaster bills are written off immediately as contractual allowances (`Total Patient Revenue - Contractual Allowance = Net Patient Revenue`).",
        f"- **Operating Patient Income vs. Total Net Income:** {vumc_line}",
        "",
        "---",
        "",
        "## Part B — CMS CERT RY 2025 Improper Payment Categories (`S5`)",
        "",
        f"- **Dataset & Grain Trap Caught:** PUF `{fin_manifest['cert_2025']['dataset_id']}` contains **{cert_meta['total_claim_lines']:,} claim-line rows** across **{cert_meta['distinct_claims']:,} distinct sampled claims** (`{cert_meta['claims_with_multiple_decisions_across_lines']:,}` claims carry multiple decision/error lines—mainly outpatient/institutional Part A Non-IPPS).",
        "- **Compliance ≠ Fraud:** `Insufficient Documentation`, `No Documentation`, `Incorrect Coding`, and `Medical Necessity` measure documentation and Medicare coverage compliance, **not** provider fraud. Notice `Overturned` (`Agree`) lines reflect initial errors successfully resolved on appeal.",
        "",
        "| Medicare Part | Review Decision | Error Code | Category | Unweighted Lines | Distinct Claims | % of Part Lines |",
        "|---|---|---|---|---:|---:|---:|",
    ])
    for part, dec, err, cat, l_cnt, c_cnt, _pt_l, _pt_c, pct, _note in c_rows:
        lines.append(f"| `{part}` | `{dec}` | `{err}` | `{cat}` | {l_cnt:,} | {c_cnt:,} | {pct:.2f}% |")

    lines.extend([
        "",
        "---",
        "",
        "## Part C — Illustrative `837 → 835 / EFT / EOB` Revenue-Cycle Math Appendix",
        "",
        "> [!NOTE]",
        "> **`ILLUSTRATIVE EXAMPLE — NOT REAL PATIENT DATA`:** Because live clearinghouse EDI files (`837` submitted claims / `835` ERA remittances) are private under HIPAA, the bounded example below demonstrates the exact accounting vocabulary absent from aggregate public files.",
        "",
        "| Step / Transaction | Amount / Math | Operational Meaning |",
        "|---|---:|---|",
        "| Billed Charge (`X12 837` Claim) | **$200.00** | Provider's chargemaster fee submitted to payer (like HCRIS Gross Charge) |",
        "| Contracted Allowed Amount (Fee Schedule) | **$120.00** | Maximum payable amount under in-network contract |",
        "| Contractual Adjustment (`X12 835` CO-45) | **-$80.00** | `$200 - $120` mandatory write-off; patient is **never** billed this for in-network care |",
        "| Insurer Payment (`X12 835` + `EFT`) | **$96.00** | `80%` plan share paid to provider via Electronic Funds Transfer (`EFT`) alongside `835` ERA |",
        "| Patient Responsibility (`EOB` / PR-1/2/3) | **$24.00** | `20%` coinsurance/deductible shifted to patient statement (`EOB`) |",
        "| Point-of-Service Collection | **-$10.00** | Amount already collected at check-in |",
        "| **Remaining Patient AR Balance** | **$14.00** | `$24.00 - $10.00` remaining collectible patient balance (never `$200 - $96 - $10 = $94`) |",
    ])

    md_path = out_dir / "reconciliation_6_hospital_costs_and_cert.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    db.close()
    return {
        "hcris_rows": len(hcris_rows),
        "cert_summary_rows": len(cert_rows),
        "cert_total_lines": cert_meta["total_claim_lines"],
        "cert_distinct_claims": cert_meta["distinct_claims"],
        "xlsx_path": str(xlsx_path),
        "markdown_path": str(md_path),
    }


def main(argv: list[str] | None = None) -> int:
    root = Path(argv[0]) if argv else Path(".")
    res = run_finance_build(root, root / "data" / "raw", root / "outputs")
    print(f"Finance & CERT pack built cleanly: {res}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
