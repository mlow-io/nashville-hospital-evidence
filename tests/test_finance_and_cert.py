"""Tests for Plan #4: HCRIS hospital cost reports, fiscal-year guards, and CMS CERT 2025 error modeling."""
from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

import pytest
from openpyxl import load_workbook

from nashville_ed.build_finance_pack import (
    classify_fiscal_alignment,
    map_cert_category,
    prepare_hcris_rows,
    run_finance_build,
    summarize_cert_csv,
)
from nashville_ed.build_pack import run_extended_build

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"


def test_hcris_preserves_multiple_reports_in_same_year_and_flags_fy_offset():
    raw_rows = [
        {
            "rpt_rec_num": "1001",
            "_hcris_release_year": "2024",
            "_hcris_dataset_id": "test-did",
            "Provider CCN": "440039",
            "Hospital Name": "VANDERBILT UNIVERSITY MEDICAL CENTER",
            "Fiscal Year Begin Date": "2024-07-01",
            "Fiscal Year End Date": "2025-06-30",
            "Total Patient Revenue": "1000",
            "Total Costs": "300",
        },
        {
            "rpt_rec_num": "1002",
            "_hcris_release_year": "2024",
            "_hcris_dataset_id": "test-did",
            "Provider CCN": "440039",
            "Hospital Name": "VANDERBILT UNIVERSITY MEDICAL CENTER",
            "Fiscal Year Begin Date": "2024-01-01",
            "Fiscal Year End Date": "2024-06-30",
            "Total Patient Revenue": "500",
            "Total Costs": "",
        },
        {
            "rpt_rec_num": "2001",
            "_hcris_release_year": "2024",
            "_hcris_dataset_id": "test-did",
            "Provider CCN": "440161",
            "Hospital Name": "TRISTAR CENTENNIAL MEDICAL CENTER",
            "Fiscal Year Begin Date": "2024-01-01",
            "Fiscal Year End Date": "2024-12-31",
            "Total Patient Revenue": "800",
            "Total Costs": "200",
        },
    ]
    prepared = prepare_hcris_rows(raw_rows)
    assert len(prepared) == 3  # Multiple rpt_rec_num in same year never silently dropped
    vumc = [r for r in prepared if r["ccn"] == "440039"]
    assert all(r["report_count_in_year"] == 2 for r in vumc)
    assert all(r["period_alignment_status"] == "fiscal_year_offset" for r in vumc)
    assert vumc[1]["total_costs"] is None  # Blank stays None, never coerced to 0
    tristar = next(r for r in prepared if r["ccn"] == "440161")
    assert tristar["period_alignment_status"] == "calendar_aligned"
    assert classify_fiscal_alignment("2024", "2024-07-01", "2025-06-30") == "fiscal_year_offset"


def test_cert_distinguishes_lines_from_distinct_claims_and_preserves_unknowns(tmp_path):
    cert_csv = tmp_path / "cert_sample.csv"
    with cert_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["claim_control_number", "Part", "DRG", "HCPCS Procedure Code", "Provider Type", "Type of Bill", "Review Decision", "Error Code"])
        w.writerow(["C1", "3. Part A(Excluding Inpatient Hospital PPS)", "", "99284", "Hosp", "131", "Disagree", "Insufficient Documentation"])
        w.writerow(["C1", "3. Part A(Excluding Inpatient Hospital PPS)", "", "80053", "Hosp", "131", "Agree", "-"])
        w.writerow(["C2", "4. Part A(Inpatient Hospital PPS)", "470", "", "Hosp", "111", "Disagree", "Medical Necessity"])
        w.writerow(["C3", "1. Part B", "", "99214", "MD", "", "Disagree", "Future New Code"])

    rows, meta = summarize_cert_csv(cert_csv)
    assert meta["total_claim_lines"] == 4
    assert meta["distinct_claims"] == 3
    assert meta["claims_with_multiple_decisions_across_lines"] == 1
    assert map_cert_category("Disagree", "Future New Code") == "unmapped_disagree_future_new_code"
    assert all("not weighted" in r["measurement_scope_note"].lower() or "not national weighted" in r["measurement_scope_note"].lower() for r in rows)


def test_live_finance_and_cert_build_and_excel_tie_out(tmp_path):
    fin_raw = RAW_DIR / "finance"
    if not (fin_raw / "hcris_nashville_2022_2024.json").exists() or not (RAW_DIR / "extended_manifest.json").exists():
        pytest.skip("Finance / extended raw files not downloaded locally")

    out = tmp_path / "outputs"
    run_extended_build(ROOT, RAW_DIR, out)
    res = run_finance_build(ROOT, RAW_DIR, out)
    assert res["hcris_rows"] == 15
    assert res["cert_total_lines"] > res["cert_distinct_claims"]

    db = sqlite3.connect(out / "nashville_hospital_evidence.sqlite3")
    vumc_24 = db.execute(
        "SELECT fy_begin, fy_end, period_alignment_status, report_count_in_year FROM hcris_cost_reports WHERE hcris_release_year='2024' AND ccn='440039'"
    ).fetchone()
    assert vumc_24 == ("2024-07-01", "2025-06-30", "fiscal_year_offset", 1)

    tristar_24 = db.execute(
        "SELECT fy_begin, fy_end, period_alignment_status FROM hcris_cost_reports WHERE hcris_release_year='2024' AND ccn='440161'"
    ).fetchone()
    assert tristar_24 == ("2024-01-01", "2024-12-31", "calendar_aligned")

    cert_part_a_ip = db.execute(
        "SELECT SUM(unweighted_claim_line_count), MAX(part_total_distinct_claims) FROM cert_2025_summary WHERE part='4. Part A(Inpatient Hospital PPS)'"
    ).fetchone()
    assert cert_part_a_ip == (8750, 8750)
    db.close()

    wb = load_workbook(out / "Nashville_Hospital_Evidence_Pack.xlsx", data_only=True)
    assert {"HCRIS_5_Hospitals", "CERT_Error_Categories"}.issubset(set(wb.sheetnames))

    md = (out / "reconciliation_6_hospital_costs_and_cert.md").read_text(encoding="utf-8")
    assert "ILLUSTRATIVE EXAMPLE — NOT REAL PATIENT DATA" in md
    assert "improper payment ≠ fraud" in md.lower()
