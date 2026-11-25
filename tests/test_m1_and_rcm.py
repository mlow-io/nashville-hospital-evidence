"""Tests for M1 multi-measure pack, sparse CMS archive reconstruction, SQL-to-Excel tie-outs, and Inpatient S2 RCM."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from openpyxl import load_workbook

from nashville_ed.build_pack import (
    _month_overlap,
    _parse_int_or_none,
    resolve_as_of_date,
    run_extended_build,
)

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "expected_s1_rows.json"


def _have_extended_raw() -> bool:
    return (
        (RAW_DIR / "extended_manifest.json").exists()
        and (RAW_DIR / "inpatient_nashville_2024.json").exists()
        and (RAW_DIR / "archives" / "hospitals_2026-08-13.zip").exists()
    )


def test_extended_pack_archives_inpatient_and_excel_tie_out(tmp_path):
    if not _have_extended_raw():
        pytest.skip("Extended CMS archive / inpatient files not downloaded locally")

    out = tmp_path / "outputs"
    res = run_extended_build(ROOT, RAW_DIR, out)
    assert res["m1_counts"]["retained"] == 20
    assert res["m1_counts"]["raw_total"] == 20 + res["m1_counts"]["discarded"]

    db = sqlite3.connect(out / "nashville_hospital_evidence.sqlite3")

    # 1. All 10 original S1 rows still match exact independent reference fixture
    expected_s1 = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    actual = {
        (r[0], r[1]): (r[2], r[3])
        for r in db.execute("SELECT facility_id, measure_id, raw_score, parsed_score FROM observations").fetchall()
    }
    for exp in expected_s1:
        assert actual[(exp["facility_id"], exp["measure_id"])] == (exp["raw_score"], exp["parsed_score"])

    # 2. Sparse archive reconstruction as-of 2026-09-30 carries forward 2026-08-13 cleanly without deletions
    sept = resolve_as_of_date(db, "2026-09-30")
    assert sept.serving_release_date == "2026-08-13"
    assert len(sept.rows) == 20

    # 3. Missing-base test fails closed before first release
    with pytest.raises(LookupError, match="fail closed"):
        resolve_as_of_date(db, "2026-01-01")

    # 4. Williamson OP_18b 190 -> 193 is classified with 9-month collection overlap, not causal intervention
    wmc_diff = db.execute(
        "SELECT from_score, to_score, overlap_months, change_category FROM archive_diffs WHERE facility_id='440029' AND measure_id='OP_18b'"
    ).fetchone()
    assert wmc_diff == ("190", "193", 9, "period_and_value_shift_overlapping")

    # 5. Excel workbook counts & weighted payment match SQLite SQL queries 1-to-1
    wb = load_workbook(out / "Nashville_Hospital_Evidence_Pack.xlsx", data_only=True)
    assert set(wb.sheetnames) == {
        "Observations_M1",
        "Sparse_Archive_Diffs",
        "Charge_vs_Payment_RCM",
        "Data_Dictionary",
        "Exceptions_and_Caveats",
        "Sources_and_Audit",
    }
    ws_obs = wb["Observations_M1"]
    assert ws_obs.max_row == 21  # header + 20 observations

    ws_rcm = wb["Charge_vs_Payment_RCM"]
    vumc_xl = next(r for r in ws_rcm.iter_rows(min_row=3, max_row=7, values_only=True) if r[0] == "440039")
    sql_vumc = db.execute(
        """
        SELECT SUM(tot_dschrgs),
               ROUND(SUM(tot_dschrgs * avg_submtd_cvrd_chrg) / SUM(tot_dschrgs), 2),
               ROUND(SUM(tot_dschrgs * avg_tot_pymt_amt) / SUM(tot_dschrgs), 2),
               ROUND(AVG(avg_submtd_cvrd_chrg), 2)
        FROM inpatient_drg_2024 WHERE ccn = '440039'
        """
    ).fetchone()
    assert vumc_xl[4] == sql_vumc[0]
    assert vumc_xl[5] == sql_vumc[1]
    assert vumc_xl[6] == sql_vumc[2]
    assert sql_vumc[1] != sql_vumc[3]  # Weighted total differs materially from naive unweighted mean
    db.close()


def test_month_overlap_math_and_missing_preservation():
    assert _month_overlap("10/01/2024", "09/30/2025", "01/01/2025", "12/31/2025") == 9
    assert _month_overlap("01/01/2024", "12/31/2024", "01/01/2025", "12/31/2025") == 0
    assert _parse_int_or_none("Not Available", "Score") is None
