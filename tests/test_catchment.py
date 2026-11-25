"""Tests for M2 2025 CMS Hospital Service Area (Catchment) suppression preservation and Excel tie-out."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from openpyxl import load_workbook

from nashville_ed.build_catchment import (
    normalize_hsa_rows,
    parse_suppressed_int,
    run_catchment_build,
)
from nashville_ed.build_pack import run_extended_build

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"


def test_hsa_preserves_star_suppression_and_leading_zero_zip():
    rows = normalize_hsa_rows([
        {
            "MEDICARE_PROV_NUM": "440039",
            "ZIP_CD_OF_RESIDENCE": "01730",
            "TOTAL_CASES": "*",
            "TOTAL_DAYS_OF_CARE": "*",
            "TOTAL_CHARGES": "*",
        },
        {
            "MEDICARE_PROV_NUM": "440039",
            "ZIP_CD_OF_RESIDENCE": "37064",
            "TOTAL_CASES": "125",
            "TOTAL_DAYS_OF_CARE": "610",
            "TOTAL_CHARGES": "9500000",
        },
    ])
    assert len(rows) == 2
    assert rows[0]["zip_cd_of_residence"] == "01730"
    assert rows[0]["is_suppressed"] == 1
    assert rows[0]["parsed_total_cases"] is None  # Never coerce '*' to 0 or 5
    assert rows[1]["is_suppressed"] == 0
    assert rows[1]["parsed_total_cases"] == 125
    assert parse_suppressed_int("*") is None


def test_live_catchment_build_and_excel_tab(tmp_path):
    c_raw = RAW_DIR / "catchment" / "hsa_2025_nashville.json"
    if not c_raw.exists() or not (RAW_DIR / "extended_manifest.json").exists():
        pytest.skip("HSA 2025 catchment raw JSON not downloaded locally")

    out = tmp_path / "outputs"
    run_extended_build(ROOT, RAW_DIR, out)
    res = run_catchment_build(ROOT, RAW_DIR, out)
    assert res["hsa_rows"] > 100
    assert res["suppressed_rows"] > 0

    db = sqlite3.connect(out / "nashville_hospital_evidence.sqlite3")
    sup_null = db.execute(
        "SELECT COUNT(*) FROM hospital_service_area_2025 WHERE is_suppressed=1 AND parsed_total_cases IS NOT NULL"
    ).fetchone()[0]
    assert sup_null == 0
    vumc_vis = db.execute(
        "SELECT SUM(parsed_total_cases) FROM hospital_service_area_2025 WHERE ccn='440039' AND is_suppressed=0"
    ).fetchone()[0]
    assert vumc_vis > 0
    db.close()

    wb = load_workbook(out / "Nashville_Hospital_Evidence_Pack.xlsx", data_only=True)
    assert "Hospital_Catchment_M2" in wb.sheetnames
    md = (out / "reconciliation_7_hospital_catchment.md").read_text(encoding="utf-8")
    assert "Medicare Fee-for-Service inpatient stays only" in md
    assert "never coerced to `0` or `5`" in md
