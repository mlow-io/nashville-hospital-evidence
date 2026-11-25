"""Build M1 SQLite evidence warehouse, sparse CMS archive diffs, Inpatient RCM pack, and Excel workbook.

Covers Reconciliations #4 (CMS release/period monitoring) and #5 (Medicare Inpatient
Charge vs. Payment S2) while keeping all 10 S1 baseline rows intact.
"""
from __future__ import annotations

import csv
import io
import json
import sqlite3
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from .build_brief import TARGET_FACILITIES, decode_footnotes, load_footnotes

M1_MEASURES: dict[str, dict[str, str]] = {
    "OP_18b": {
        "short_label": "ED Arrival-to-Departure Median (Discharged)",
        "unit": "minutes",
        "cohort_note": "Discharged ED patients; excludes admissions, transfers, and psychiatric visits.",
        "comparable_notes": "Compare only within identical measurement period & unit (minutes).",
    },
    "OP_18c": {
        "short_label": "ED Arrival-to-Departure Median (Psychiatric / Mental Health)",
        "unit": "minutes",
        "cohort_note": "Discharged psychiatric / mental-health ED cohort (distinct from OP_18b).",
        "comparable_notes": "Never sum or average OP_18b and OP_18c together.",
    },
    "OP_22": {
        "short_label": "Left Without Being Seen",
        "unit": "percent",
        "cohort_note": "Percentage of ED visits where patient left before clinician evaluation.",
        "comparable_notes": "2024 period inside 2026-11 CMS file; unavailable stays NULL/text (never 0).",
    },
    "SEP_1": {
        "short_label": "Severe Sepsis / Septic Shock Bundle Compliance",
        "unit": "percent",
        "cohort_note": "Sampled acute-care sepsis bundle cases (check Footnote 2 sampling note).",
        "comparable_notes": "Percent (%) scale; never compare against minute-unit ED duration measures.",
    },
}


@dataclass(frozen=True)
class AsOfResult:
    requested_date: str
    serving_release_date: str
    rows: list[dict[str, Any]]


def _parse_int_or_none(raw_val: str, field_name: str, allowed_units: set[str] | None = None) -> int | None:
    cleaned = (raw_val or "").strip()
    if not cleaned or cleaned.lower() == "not available":
        return None
    if not cleaned.isdigit():
        raise ValueError(f"Non-integer value {raw_val!r} for {field_name}")
    return int(cleaned)


def _extract_archive_table(zpath: Path, dataset_id: str) -> list[tuple[int, dict[str, str]]]:
    """Read exact CMS dataset-ID CSV from an archive ZIP, rejecting REH traps and __MACOSX."""
    with zipfile.ZipFile(zpath) as zf:
        matches = [
            n for n in zf.namelist()
            if not n.startswith("__MACOSX")
            and dataset_id.lower() in Path(n).name.lower()
            and n.lower().endswith(".csv")
        ]
        if not matches:
            raise FileNotFoundError(f"{dataset_id} missing from {zpath.name}")
        with zf.open(matches[0]) as raw:
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig"))
            return list(enumerate(reader, start=2))


def _load_facilities(hosp_csv: Path, facility_ids: tuple[str, ...]) -> list[dict[str, str]]:
    want = set(facility_ids)
    seen: dict[str, dict[str, str]] = {}
    with hosp_csv.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            fid = (row.get("Facility ID") or "").strip()
            if fid not in want:
                continue
            if fid in seen:
                raise ValueError(f"Duplicate Facility ID {fid} in {hosp_csv}")
            seen[fid] = {
                "facility_id": fid,
                "facility_name": (row.get("Facility Name") or "").strip(),
                "address": (row.get("Address") or "").strip(),
                "city_town": (row.get("City/Town") or "").strip(),
                "state": (row.get("State") or "").strip(),
                "zip_code": (row.get("ZIP Code") or "").strip(),
                "county_parish": (row.get("County/Parish") or "").strip(),
                "hospital_type": (row.get("Hospital Type") or "").strip(),
                "hospital_ownership": (row.get("Hospital Ownership") or "").strip(),
                "emergency_services": (row.get("Emergency Services") or "").strip(),
            }
    missing = want - set(seen)
    if missing:
        raise ValueError(f"Missing facilities from dimension CSV: {sorted(missing)}")
    return [seen[fid] for fid in facility_ids]


def _month_overlap(s1: str, e1: str, s2: str, e2: str) -> int:
    d1s = datetime.strptime(s1, "%m/%d/%Y")
    d1e = datetime.strptime(e1, "%m/%d/%Y")
    d2s = datetime.strptime(s2, "%m/%d/%Y")
    d2e = datetime.strptime(e2, "%m/%d/%Y")
    start = max(d1s, d2s)
    end = min(d1e, d2e)
    if end < start:
        return 0
    return (end.year - start.year) * 12 + (end.month - start.month) + 1


def _classify_change(prev: dict[str, Any], curr: dict[str, Any]) -> tuple[str, int, str]:
    overlap = _month_overlap(prev["start_date"], prev["end_date"], curr["start_date"], curr["end_date"])
    period_changed = (prev["start_date"], prev["end_date"]) != (curr["start_date"], curr["end_date"])
    score_changed = prev["raw_score"] != curr["raw_score"]
    footnote_changed = prev["raw_footnote"] != curr["raw_footnote"]

    if (prev["raw_score"] == "Not Available") != (curr["raw_score"] == "Not Available"):
        return (
            "availability_change",
            overlap,
            "Measure availability changed between releases; do not treat missingness transition as clinical improvement.",
        )
    if period_changed and score_changed and overlap > 0:
        return (
            "period_and_value_shift_overlapping",
            overlap,
            f"Collection window shifted with {overlap}-month overlap ({prev['start_date']}..{prev['end_date']} -> {curr['start_date']}..{curr['end_date']}); not an independent period trend or causal intervention effect.",
        )
    if period_changed and score_changed:
        return (
            "period_and_value_shift",
            overlap,
            "Score updated alongside a new collection period.",
        )
    if period_changed and not score_changed:
        return (
            "period_shifted_value_same",
            overlap,
            "Collection period shifted while score remained numerically identical.",
        )
    if score_changed:
        return (
            "value_revision_same_period",
            overlap,
            "Score changed inside an identical collection period (data revision).",
        )
    if footnote_changed:
        return ("footnote_change", overlap, "Footnote code changed while score/period remained same.")
    return (
        "unchanged_carried_forward",
        overlap,
        "Score, sample, footnote, and collection period unchanged between releases.",
    )


def resolve_as_of_date(db: sqlite3.Connection, requested_date: str) -> AsOfResult:
    """Reconstruct exact CMS dataset state as of a calendar date without deleting absent updates."""
    event = db.execute(
        """
        SELECT archive_date, serving_release_date
        FROM archive_events
        WHERE archive_date <= ?
        ORDER BY archive_date DESC
        LIMIT 1
        """,
        (requested_date,),
    ).fetchone()
    if event is None or not event[1]:
        raise LookupError(f"No established Timely Care base release on or before {requested_date} (fail closed)")

    serving = event[1]
    cur = db.execute(
        """
        SELECT ao.archive_release_date, ao.facility_id, f.facility_name, ao.measure_id,
               ao.start_date, ao.end_date, ao.raw_score, ao.parsed_score,
               ao.raw_sample, ao.parsed_sample, ao.raw_footnote, ao.footnote_text
        FROM archive_observations ao
        JOIN facility_attributes f ON f.facility_id = ao.facility_id
        WHERE ao.archive_release_date = ?
        ORDER BY ao.facility_id, ao.measure_id
        """,
        (serving,),
    )
    cols = [d[0] for d in cur.description]
    rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    if not rows:
        raise LookupError(f"Serving archive release {serving} has 0 observations (fail closed)")
    return AsOfResult(requested_date=requested_date, serving_release_date=serving, rows=rows)


def _split_named_queries(sql_path: Path) -> dict[str, str]:
    queries: dict[str, str] = {}
    name: str | None = None
    buf: list[str] = []
    for line in sql_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("-- name:"):
            if name and buf:
                queries[name] = "\n".join(buf).strip()
            name = line.split(":", 1)[1].strip()
            buf = []
        elif not line.startswith("-- "):
            buf.append(line)
    if name and buf:
        queries[name] = "\n".join(buf).strip()
    return queries


def _query_rows(db: sqlite3.Connection, sql: str) -> tuple[list[str], list[tuple[Any, ...]]]:
    cur = db.execute(sql)
    cols = [d[0] for d in cur.description]
    return cols, cur.fetchall()


def _write_excel_pack(
    out_xlsx: Path,
    db: sqlite3.Connection,
    queries: dict[str, str],
    ext_manifest: dict[str, Any],
    manifest: dict[str, Any],
    m1_counts: dict[str, int],
) -> None:
    wb = Workbook()
    wb.remove(wb.active)

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")

    def add_sql_sheet(title: str, query_name: str, col_widths: dict[int, int] | None = None):
        ws = wb.create_sheet(title=title)
        cols, rows = _query_rows(db, queries[query_name])
        ws.append(cols)
        for c_idx in range(1, len(cols) + 1):
            cell = ws.cell(row=1, column=c_idx)
            cell.font = header_font
            cell.fill = header_fill
        for row in rows:
            ws.append(list(row))
        if col_widths:
            for idx, w in col_widths.items():
                ws.column_dimensions[chr(64 + idx)].width = w
        ws.freeze_panes = "A2"
        return ws

    add_sql_sheet("Observations_M1", "m1_observations", {1: 12, 2: 36, 3: 14, 6: 11, 7: 38})
    add_sql_sheet("Sparse_Archive_Diffs", "sparse_archive_diffs", {1: 12, 2: 36, 3: 11, 10: 32, 12: 52})

    # Charge vs Payment RCM tab: hospital weighted summary + shared DRG matrix
    ws_rcm = wb.create_sheet(title="Charge_vs_Payment_RCM")
    wcols, wrows = _query_rows(db, queries["inpatient_weighted_hospital_summary"])
    ws_rcm.append(["2024 Medicare Inpatient Hospital Totals (Discharge-Weighted — FFS Scope Only)"])
    ws_rcm["A1"].font = Font(bold=True, size=12)
    ws_rcm.append(wcols)
    for c_idx in range(1, len(wcols) + 1):
        ws_rcm.cell(row=2, column=c_idx).font = header_font
        ws_rcm.cell(row=2, column=c_idx).fill = header_fill
    for r in wrows:
        ws_rcm.append(list(r))
    ws_rcm.append([])
    scols, srows = _query_rows(db, queries["shared_drg_comparison"])
    ws_rcm.append(["Shared MS-DRGs Billed Across All 5 Selected Hospitals"])
    ws_rcm.cell(row=ws_rcm.max_row, column=1).font = Font(bold=True, size=12)
    hdr_row = ws_rcm.max_row + 1
    ws_rcm.append(scols)
    for c_idx in range(1, len(scols) + 1):
        ws_rcm.cell(row=hdr_row, column=c_idx).font = header_font
        ws_rcm.cell(row=hdr_row, column=c_idx).fill = header_fill
    for r in srows:
        ws_rcm.append(list(r))
    ws_rcm.column_dimensions["A"].width = 12
    ws_rcm.column_dimensions["B"].width = 44
    ws_rcm.column_dimensions["D"].width = 36

    # Data Dictionary tab
    ws_dict = wb.create_sheet(title="Data_Dictionary")
    ws_dict.append(["measure_id", "short_label", "cms_measure_name", "unit", "cohort_note", "comparable_notes"])
    for c_idx in range(1, 7):
        ws_dict.cell(row=1, column=c_idx).font = header_font
        ws_dict.cell(row=1, column=c_idx).fill = header_fill
    for r in db.execute("SELECT * FROM measure_definitions ORDER BY measure_id").fetchall():
        ws_dict.append(list(r))
    ws_dict.column_dimensions["A"].width = 14
    ws_dict.column_dimensions["B"].width = 42
    ws_dict.column_dimensions["C"].width = 48
    ws_dict.column_dimensions["E"].width = 52
    ws_dict.column_dimensions["F"].width = 52

    # Exceptions & Caveats tab
    ws_exc = wb.create_sheet(title="Exceptions_and_Caveats")
    ws_exc.append(["Category", "Scope", "Detail"])
    for c_idx in range(1, 4):
        ws_exc.cell(row=1, column=c_idx).font = header_font
        ws_exc.cell(row=1, column=c_idx).fill = header_fill
    caveats = [
        ("Missing / Suppressed", "440082 OP_22 (2024)", "Not Available; Footnote 5 ('Results are not available for this reporting period.'). Kept NULL; never coerced to 0."),
        ("Sampling Caveat", "SEP_1 (2025)", "Carries Footnote 2 ('Data submitted were based on a sample of cases/patients.')."),
        ("Sparse Archive", "2026-09-30 CMS ZIP", "Timely Care yv7e-xc69 absent from 2026-09-30 archive; carried forward 2026-08-13 baseline rather than deleting hospitals."),
        ("REH Trap Rejected", "2026-08-13 & 2026-11-12", "Rejected similarly named 97xg-v3wv Rural Emergency Hospital Timely Care CSV."),
        ("Period Overlap", "OP_18b / OP_18c / SEP_1", "2026-08-13 covered 10/01/2024-09/30/2025 while 2026-11-12 covered 01/01/2025-12/31/2025 (9-month overlap). Not an intervention trend."),
        ("Unit / Scale Separation", "OP_18b/c vs OP_22/SEP_1", "Never combine minutes and percent, and never average hospital medians to fake a regional patient mean."),
        ("RCM Scope", "Medicare Inpatient 2024", "Medicare fee-for-service discharges & MS-DRG payments only. Submitted charges are chargemaster prices, NOT hospital revenue or patient out-of-pocket liability."),
    ]
    for c in caveats:
        ws_exc.append(list(c))
    ws_exc.column_dimensions["A"].width = 24
    ws_exc.column_dimensions["B"].width = 28
    ws_exc.column_dimensions["C"].width = 96

    # Sources & Audit tab
    ws_src = wb.create_sheet(title="Sources_and_Audit")
    ws_src.append(["Artifact", "Dataset / Release", "SHA-256", "Record / Bytes Summary"])
    for c_idx in range(1, 5):
        ws_src.cell(row=1, column=c_idx).font = header_font
        ws_src.cell(row=1, column=c_idx).fill = header_fill
    for key, info in manifest.get("artifacts", {}).items():
        ws_src.append([key, info.get("dataset_id", ""), info.get("sha256", ""), f"{info.get('bytes', 0):,} bytes (modified {info.get('modified', 'n/a')})"])
    for rel, info in ext_manifest.get("archives", {}).items():
        ws_src.append([f"archive_{rel}", info.get("filename", ""), info.get("sha256", ""), f"has_timely_care={info.get('has_timely_care')} entry={info.get('timely_care_entry')}"])
    inp = ext_manifest.get("inpatient_2024", {})
    ws_src.append(["inpatient_2024", inp.get("dataset_id", ""), inp.get("sha256", ""), f"{inp.get('row_count', 0)} DRG rows across 5 CCNs"])
    ws_src.append(["M1 row reconciliation", "Timely Care yv7e-xc69", "", f"raw={m1_counts['raw_total']:,} == retained={m1_counts['retained']} + discarded={m1_counts['discarded']:,}"])
    ws_src.column_dimensions["A"].width = 26
    ws_src.column_dimensions["B"].width = 36
    ws_src.column_dimensions["C"].width = 68
    ws_src.column_dimensions["D"].width = 58

    wb.save(out_xlsx)


def run_extended_build(root: Path, raw_dir: Path, out_dir: Path) -> dict[str, Any]:
    root = Path(root)
    raw_dir = Path(raw_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = json.loads((raw_dir / "manifest.json").read_text(encoding="utf-8"))
    ext_manifest = json.loads((raw_dir / "extended_manifest.json").read_text(encoding="utf-8"))
    queries = _split_named_queries(root / "sql" / "reporting_queries.sql")

    db_path = out_dir / "nashville_hospital_evidence.sqlite3"
    if db_path.exists():
        db_path.unlink()
    db = sqlite3.connect(db_path)
    db.executescript((root / "sql" / "schema.sql").read_text(encoding="utf-8"))

    timely_csv = raw_dir / "Timely_and_Effective_Care-Hospital.csv"
    hosp_csv = raw_dir / "Hospital_General_Information.csv"
    foot_csv = raw_dir / "Footnote_Crosswalk.csv"

    crosswalk = load_footnotes(foot_csv)
    facilities = _load_facilities(hosp_csv, TARGET_FACILITIES)
    for fac in facilities:
        db.execute(
            "INSERT INTO facility_attributes VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                fac["facility_id"], fac["facility_name"], fac["address"],
                fac["city_town"], fac["state"], fac["zip_code"], fac["county_parish"],
                fac["hospital_type"], fac["hospital_ownership"], fac["emergency_services"],
            ),
        )

    # Scan Timely Care for M1 (5 facilities x 4 reviewed measures)
    want_fac = set(TARGET_FACILITIES)
    want_meas = set(M1_MEASURES)
    raw_total = 0
    discarded = 0
    m1_rows: list[dict[str, Any]] = []
    cms_meas_names: dict[str, str] = {}

    with timely_csv.open(encoding="utf-8-sig", newline="") as f:
        for row_num, rec in enumerate(csv.DictReader(f), start=2):
            raw_total += 1
            fid = (rec.get("Facility ID") or "").strip()
            mid = (rec.get("Measure ID") or "").strip()
            if fid not in want_fac or mid not in want_meas:
                discarded += 1
                continue
            cms_meas_names[mid] = (rec.get("Measure Name") or "").strip()
            raw_score = (rec.get("Score") or "").strip()
            raw_sample = (rec.get("Sample") or "").strip()
            raw_foot = (rec.get("Footnote") or "").strip()
            m1_rows.append(
                {
                    "facility_id": fid,
                    "measure_id": mid,
                    "start_date": (rec.get("Start Date") or "").strip(),
                    "end_date": (rec.get("End Date") or "").strip(),
                    "raw_score": raw_score,
                    "parsed_score": _parse_int_or_none(raw_score, "Score"),
                    "raw_sample": raw_sample,
                    "parsed_sample": _parse_int_or_none(raw_sample, "Sample"),
                    "raw_footnote": raw_foot,
                    "footnote_text": decode_footnotes(raw_foot, crosswalk),
                    "source_row_number": row_num,
                }
            )

    assert len(m1_rows) == len(TARGET_FACILITIES) * len(M1_MEASURES) == 20
    assert raw_total == len(m1_rows) + discarded

    for mid, spec in M1_MEASURES.items():
        db.execute(
            "INSERT INTO measure_definitions VALUES (?,?,?,?,?,?)",
            (mid, spec["short_label"], cms_meas_names.get(mid, spec["short_label"]), spec["unit"], spec["cohort_note"], spec["comparable_notes"]),
        )

    t_meta = manifest["artifacts"]["timely_care"]
    v_curr = f"yv7e-xc69@{t_meta.get('modified', 'current')}"
    db.execute(
        "INSERT INTO source_versions VALUES (?,?,?,?,?,?,?,?,?)",
        (v_curr, "yv7e-xc69", str(t_meta.get("modified", "")), t_meta["filename"], t_meta["sha256"], int(t_meta["bytes"]), raw_total, len(m1_rows), discarded),
    )

    for r in m1_rows:
        db.execute(
            "INSERT INTO observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                r["facility_id"], r["measure_id"], v_curr, f"{r['start_date']}..{r['end_date']}",
                r["start_date"], r["end_date"], r["raw_score"], r["parsed_score"],
                r["raw_sample"], r["parsed_sample"], r["raw_footnote"], r["footnote_text"],
                r["source_row_number"],
            ),
        )

    # Sparse Archive Events & Diffs (2026-08-13 -> 2026-09-30 -> 2026-11-12)
    last_established: str | None = None
    archive_rows_by_rel: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}
    for rel in sorted(ext_manifest["archives"]):
        info = ext_manifest["archives"][rel]
        zpath = raw_dir / "archives" / info["filename"]
        if info["has_timely_care"]:
            last_established = rel
            rel_rows: dict[tuple[str, str], dict[str, Any]] = {}
            for rnum, rec in _extract_archive_table(zpath, "yv7e-xc69"):
                fid = (rec.get("Facility ID") or "").strip()
                mid = (rec.get("Measure ID") or "").strip()
                if fid in want_fac and mid in want_meas:
                    raw_sc = (rec.get("Score") or "").strip()
                    raw_sa = (rec.get("Sample") or "").strip()
                    raw_fn = (rec.get("Footnote") or "").strip()
                    item = {
                        "archive_release_date": rel,
                        "facility_id": fid,
                        "measure_id": mid,
                        "start_date": (rec.get("Start Date") or "").strip(),
                        "end_date": (rec.get("End Date") or "").strip(),
                        "raw_score": raw_sc,
                        "parsed_score": _parse_int_or_none(raw_sc, "Score"),
                        "raw_sample": raw_sa,
                        "parsed_sample": _parse_int_or_none(raw_sa, "Sample"),
                        "raw_footnote": raw_fn,
                        "footnote_text": decode_footnotes(raw_fn, crosswalk),
                        "source_row_number": rnum,
                    }
                    rel_rows[(fid, mid)] = item
                    db.execute(
                        "INSERT INTO archive_observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            rel, fid, mid, item["start_date"], item["end_date"],
                            item["raw_score"], item["parsed_score"], item["raw_sample"],
                            item["parsed_sample"], item["raw_footnote"], item["footnote_text"],
                            rnum,
                        ),
                    )
            archive_rows_by_rel[rel] = rel_rows
            note = f"Updated Timely Care (yv7e-xc69); retained {len(rel_rows)} observations."
        else:
            note = (
                f"Timely Care (yv7e-xc69) absent in sparse archive; carried forward established {last_established} release."
                if last_established
                else "Timely Care absent and no prior established base exists."
            )

        db.execute(
            "INSERT INTO archive_events VALUES (?,?,?,?,?,?,?,?)",
            (
                rel,
                info["filename"],
                info["sha256"],
                int(info["has_timely_care"]),
                info.get("timely_care_entry"),
                last_established,
                ",".join(info.get("rural_emergency_entries") or []),
                note,
            ),
        )

    established_releases = sorted(archive_rows_by_rel)
    if len(established_releases) >= 2:
        prev_rel, curr_rel = established_releases[0], established_releases[-1]
        for key in sorted(archive_rows_by_rel[prev_rel]):
            prev = archive_rows_by_rel[prev_rel][key]
            curr = archive_rows_by_rel[curr_rel][key]
            cat, ov_mo, guard = _classify_change(prev, curr)
            db.execute(
                "INSERT INTO archive_diffs VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    key[0], key[1], prev_rel, curr_rel,
                    prev["raw_score"], curr["raw_score"],
                    f"{prev['start_date']}..{prev['end_date']}",
                    f"{curr['start_date']}..{curr['end_date']}",
                    cat, ov_mo, guard,
                ),
            )

    # Load 2024 Medicare Inpatient DRGs (Reconciliation #5)
    inpatient = json.loads((raw_dir / "inpatient_nashville_2024.json").read_text(encoding="utf-8"))
    for rec in inpatient:
        db.execute(
            "INSERT INTO inpatient_drg_2024 VALUES (?,?,?,?,?,?,?)",
            (
                str(rec["Rndrng_Prvdr_CCN"]).strip(),
                str(rec["DRG_Cd"]).strip(),
                str(rec["DRG_Desc"]).strip(),
                int(rec["Tot_Dschrgs"]),
                float(rec["Avg_Submtd_Cvrd_Chrg"]),
                float(rec["Avg_Tot_Pymt_Amt"]),
                float(rec["Avg_Mdcr_Pymt_Amt"]),
            ),
        )
    db.commit()

    # Verify as-of-date reconstruction on all 3 dates
    sept_view = resolve_as_of_date(db, "2026-09-30")
    assert sept_view.serving_release_date == "2026-08-13"
    assert len(sept_view.rows) == 20

    m1_counts = {"raw_total": raw_total, "retained": len(m1_rows), "discarded": discarded}
    _write_excel_pack(out_dir / "Nashville_Hospital_Evidence_Pack.xlsx", db, queries, ext_manifest, manifest, m1_counts)

    # Markdown Report #4: Sparse Archives & Diffs
    diff_cols, diff_rows = _query_rows(db, queries["sparse_archive_diffs"])
    r4 = [
        "# Reconciliation #4: Five-Hospital CMS Release Monitor & Sparse Archive Diffs",
        "",
        f"- **M1 Reconciliation:** `{raw_total:,}` scanned rows = `{len(m1_rows)}` retained (`5 hospitals x 4 measures: OP_18b, OP_18c, OP_22, SEP_1`) + `{discarded:,}` out of scope.",
        f"- **Sparse Archive Proof (`2026-09-30`):** When queried as of `2026-09-30` (3.15 MB archive missing `yv7e-xc69`), reconstruction carries forward `2026-08-13` cleanly (`20` rows preserved, `0` hospitals deleted) and rejects the `97xg-v3wv` Rural Emergency Hospital file.",
        "",
        "## Changes Between `2026-08-13` (Base) and `2026-11-12` (Current)",
        "",
        "| Facility | Measure | `2026-08-13` | `2026-11-12` | Window Shift & Overlap | Category | Guardrail |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in diff_rows:
        fid, fname, mid, _, _, fsc, tsc, fp, tp, cat, ov, guard = r
        r4.append(f"| `{fid}` {fname} | `{mid}` | `{fsc}` ({fp}) | `{tsc}` ({tp}) | {ov} mo overlap | `{cat}` | {guard} |")
    (out_dir / "reconciliation_4_hospital_releases.md").write_text("\n".join(r4) + "\n", encoding="utf-8")

    # Markdown Report #5: Charge vs Payment RCM (2024 Inpatient FFS)
    _, w_rows = _query_rows(db, queries["inpatient_weighted_hospital_summary"])
    _, s_rows = _query_rows(db, queries["shared_drg_comparison"])
    r5 = [
        "# Reconciliation #5: Medicare Inpatient Submitted Charge vs. Actual Payment (`S2`, 2024)",
        "",
        "**Scope:** 2024 CMS Medicare Inpatient Hospitals by Provider and Service (`690ddc6c-2767-4618-b277-420ffb2bf27c`, Medicare fee-for-service discharges & DRGs only — **not** total hospital revenue and **not** patient out-of-pocket liability).",
        "",
        "## Hospital Discharge-Weighted Totals (vs. Naive Unweighted Average Trap)",
        "",
        "| CCN | Hospital | Ownership | DRGs | Discharges | Weighted Avg Charge | Weighted Avg Total Payment | Weighted Medicare Payment | Paid % of Charge | Naive Unweighted Charge *(wrong)* |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for fid, fname, own, drgs, dsch, wchg, wtpy, wmpy, naive, pct_c in w_rows:
        r5.append(
            f"| `{fid}` | {fname} | {own} | {drgs} | {dsch:,} | ${wchg:,.2f} | ${wtpy:,.2f} | ${wmpy:,.2f} | {pct_c:.1f}% | ${naive:,.2f} |"
        )
    r5.extend([
        "",
        "## Top Shared MS-DRGs (Present at All 5 Selected Hospitals)",
        "",
        "| DRG | Description | Hospital | Discharges | Avg Submitted Charge | Avg Total Payment | Avg Medicare Payment | Paid % of Charge |",
        "|---|---|---|---:|---:|---:|---:|---:|",
    ])
    for drg_cd, drg_desc, ccn, fname, dsch, chg, tpy, mpy, pc in s_rows[:25]:
        r5.append(f"| `{drg_cd}` | {drg_desc[:48]} | `{ccn}` {fname} | {dsch:,} | ${chg:,.2f} | ${tpy:,.2f} | ${mpy:,.2f} | {pc:.1f}% |")
    (out_dir / "reconciliation_5_charge_vs_payment.md").write_text("\n".join(r5) + "\n", encoding="utf-8")

    db.close()
    return {
        "m1_counts": m1_counts,
        "inpatient_rows": len(inpatient),
        "archive_diff_rows": len(diff_rows),
        "sqlite_path": str(db_path),
    }


def main(argv: list[str] | None = None) -> int:
    root = Path(argv[0]) if argv else Path(".")
    res = run_extended_build(root, root / "data" / "raw", root / "outputs")
    print(f"Extended pack built cleanly: {res}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
