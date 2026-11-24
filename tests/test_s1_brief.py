"""Independent reference and deliberate-mutation tests for S1 Nashville ED brief."""
from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

import pytest

from nashville_ed.build_brief import (
    _parse_optional_int,
    build_observations,
    render_brief_markdown,
    run_build,
)
from nashville_ed.fetch import fetch_all

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "expected_s1_rows.json"


def _make_mini_raw(tmp_path: Path, *, drop_last: bool = False, mislabel_op22_year: bool = False, dup_hospital: bool = False) -> Path:
    raw = tmp_path / "raw"
    raw.mkdir()
    expected = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    if drop_last:
        expected = expected[:-1]

    fieldnames = [
        "Facility ID", "Facility Name", "Address", "City/Town", "State", "ZIP Code",
        "County/Parish", "Telephone Number", "Condition", "Measure ID", "Measure Name",
        "Score", "Sample", "Footnote", "Start Date", "End Date",
    ]
    with (raw / "Timely_and_Effective_Care-Hospital.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for item in expected:
            end_date = "12/31/2025" if (mislabel_op22_year and item["measure_id"] == "OP_22") else item["end_date"]
            w.writerow({
                "Facility ID": item["facility_id"],
                "Facility Name": f"Hospital {item['facility_id']}",
                "Address": "100 Main St",
                "City/Town": "NASHVILLE",
                "State": "TN",
                "ZIP Code": "37203",
                "County/Parish": "DAVIDSON",
                "Telephone Number": "(615) 555-0100",
                "Condition": "Emergency Department",
                "Measure ID": item["measure_id"],
                "Measure Name": item["measure_id"],
                "Score": item["raw_score"],
                "Sample": item["raw_sample"],
                "Footnote": item["raw_footnote"],
                "Start Date": item["start_date"],
                "End Date": end_date,
            })
        # Out-of-scope row to verify reconciliation accounting
        w.writerow({
            "Facility ID": "999999",
            "Facility Name": "Out of Scope Hospital",
            "Address": "999 Other St",
            "City/Town": "MEMPHIS",
            "State": "TN",
            "ZIP Code": "38103",
            "County/Parish": "SHELBY",
            "Telephone Number": "(901) 555-0100",
            "Condition": "Emergency Department",
            "Measure ID": "OP_18b",
            "Measure Name": "OP_18b",
            "Score": "140",
            "Sample": "200",
            "Footnote": "",
            "Start Date": "01/01/2025",
            "End Date": "12/31/2025",
        })

    hosp_fields = ["Facility ID", "Facility Name", "City/Town", "State", "ZIP Code", "Hospital Type", "Hospital Ownership"]
    with (raw / "Hospital_General_Information.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=hosp_fields)
        w.writeheader()
        for fid in ["440029", "440039", "440073", "440082", "440161"]:
            row = {
                "Facility ID": fid,
                "Facility Name": f"Hospital {fid}",
                "City/Town": "NASHVILLE",
                "State": "TN",
                "ZIP Code": "07203" if fid == "440029" else "37203",
                "Hospital Type": "Acute Care Hospitals",
                "Hospital Ownership": "Voluntary",
            }
            w.writerow(row)
            if dup_hospital and fid == "440029":
                w.writerow(row)

    with (raw / "Footnote_Crosswalk.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["Footnote", "Footnote Text"])
        w.writeheader()
        w.writerow({"Footnote": "5", "Footnote Text": "Results are not available for this reporting period."})

    (raw / "manifest.json").write_text(json.dumps({"artifacts": {}}), encoding="utf-8")
    return raw


def test_live_cms_rows_match_independent_reference_fixture(tmp_path):
    if not (RAW_DIR / "Timely_and_Effective_Care-Hospital.csv").exists():
        pytest.skip("Raw CMS files not present locally")

    out_dir = tmp_path / "outputs"
    receipt = run_build(RAW_DIR, out_dir)
    expected = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    assert receipt["reconciliation"]["retained_in_scope"] == 10
    assert receipt["reconciliation"]["raw_total"] == (
        receipt["reconciliation"]["retained_in_scope"] + receipt["reconciliation"]["discarded_out_of_scope"]
    )

    actual_by_key = {(r["facility_id"], r["measure_id"]): r for r in receipt["retained_rows"]}
    for exp in expected:
        act = actual_by_key[(exp["facility_id"], exp["measure_id"])]
        assert act["raw_score"] == exp["raw_score"]
        assert act["parsed_score"] == exp["parsed_score"]
        assert act["raw_sample"] == exp["raw_sample"]
        assert act["parsed_sample"] == exp["parsed_sample"]
        assert act["raw_footnote"] == exp["raw_footnote"]
        assert act["start_date"] == exp["start_date"]
        assert act["end_date"] == exp["end_date"]

    # Saint Thomas OP_22 remains None (never coerced to 0) with Footnote 5 decoded
    st_op22 = actual_by_key[("440082", "OP_22")]
    assert st_op22["parsed_score"] is None
    assert "Results are not available for this reporting period." in st_op22["footnote_text"]

    brief_md = (out_dir / "nashville_ed_brief.md").read_text(encoding="utf-8")
    assert "2025" in brief_md and "2024" in brief_md
    assert "best hospital" in brief_md.lower()  # explicit guardrail disclaimer present
    assert "Results are not available for this reporting period." in brief_md


def test_preserves_leading_zero_zip_as_text_and_reconciles(tmp_path):
    raw = _make_mini_raw(tmp_path)
    rows, counts = build_observations(
        raw / "Timely_and_Effective_Care-Hospital.csv",
        raw / "Hospital_General_Information.csv",
        raw / "Footnote_Crosswalk.csv",
    )
    assert counts == {"raw_total": 11, "retained_in_scope": 10, "discarded_out_of_scope": 1}
    assert rows[0].zip_code == "07203"
    assert isinstance(rows[0].facility_id, str)
    md = render_brief_markdown(rows, {"artifacts": {}}, counts)
    assert "`07203`" in md


def test_mutation_fails_when_selected_row_dropped(tmp_path):
    raw = _make_mini_raw(tmp_path, drop_last=True)
    with pytest.raises(ValueError, match="Expected 10 retained S1 rows"):
        build_observations(
            raw / "Timely_and_Effective_Care-Hospital.csv",
            raw / "Hospital_General_Information.csv",
            raw / "Footnote_Crosswalk.csv",
        )


def test_mutation_fails_when_op22_mislabeled_as_2025(tmp_path):
    raw = _make_mini_raw(tmp_path, mislabel_op22_year=True)
    with pytest.raises(ValueError, match="expected 2024"):
        build_observations(
            raw / "Timely_and_Effective_Care-Hospital.csv",
            raw / "Hospital_General_Information.csv",
            raw / "Footnote_Crosswalk.csv",
        )


def test_mutation_fails_on_duplicate_hospital_dimension_key(tmp_path):
    raw = _make_mini_raw(tmp_path, dup_hospital=True)
    with pytest.raises(ValueError, match="Duplicate Facility ID"):
        build_observations(
            raw / "Timely_and_Effective_Care-Hospital.csv",
            raw / "Hospital_General_Information.csv",
            raw / "Footnote_Crosswalk.csv",
        )


def test_not_available_never_coerces_to_zero():
    assert _parse_optional_int("Not Available", "Score") is None
    assert _parse_optional_int("", "Score") is None
    with pytest.raises(ValueError):
        _parse_optional_int("abc", "Score")


def test_fetch_fails_visibly_on_empty_or_failed_download(tmp_path):
    def empty_fetcher(_url: str) -> bytes:
        raise RuntimeError("Empty payload downloaded")

    with pytest.raises(RuntimeError, match="Empty payload"):
        fetch_all(tmp_path / "raw", fetcher=empty_fetcher)
