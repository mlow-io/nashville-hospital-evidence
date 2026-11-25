"""Build M2 2025 CMS Hospital Service Area (Catchment) tables, Excel tab, and markdown brief."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill

from .build_pack import _query_rows, _split_named_queries


def parse_suppressed_int(raw_val: Any) -> int | None:
    s = str(raw_val or "").strip()
    if not s or s == "*":
        return None
    return int(float(s))


def parse_suppressed_float(raw_val: Any) -> float | None:
    s = str(raw_val or "").strip()
    if not s or s == "*":
        return None
    return float(s)


def normalize_hsa_rows(raw_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in raw_rows:
        ccn = str(row.get("MEDICARE_PROV_NUM") or "").strip()
        if not ccn:
            continue
        zcd = str(row.get("ZIP_CD_OF_RESIDENCE") or "").strip() or "BLANK_ZIP"
        if (ccn, zcd) in seen:
            raise ValueError(f"Duplicate HSA row for (ccn={ccn}, zip={zcd})")
        seen.add((ccn, zcd))
        r_cases = str(row.get("TOTAL_CASES") or "").strip()
        r_days = str(row.get("TOTAL_DAYS_OF_CARE") or "").strip()
        r_chg = str(row.get("TOTAL_CHARGES") or "").strip()
        p_cases = parse_suppressed_int(r_cases)
        p_days = parse_suppressed_int(r_days)
        p_chg = parse_suppressed_float(r_chg)
        suppressed = int(r_cases == "*" or p_cases is None)
        out.append(
            {
                "ccn": ccn,
                "zip_cd_of_residence": zcd,
                "raw_total_cases": r_cases,
                "parsed_total_cases": p_cases,
                "raw_total_days_of_care": r_days,
                "parsed_total_days_of_care": p_days,
                "raw_total_charges": r_chg,
                "parsed_total_charges": p_chg,
                "is_suppressed": suppressed,
            }
        )
    return out


def _write_catchment_sheet(xlsx_path: Path, db: sqlite3.Connection, queries: dict[str, str]) -> None:
    wb = load_workbook(xlsx_path) if xlsx_path.exists() else Workbook()
    if "Sheet" in wb.sheetnames and len(wb.sheetnames) == 1:
        wb.remove(wb.active)

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    title = "Hospital_Catchment_M2"
    if title in wb.sheetnames:
        del wb[title]
    ws = wb.create_sheet(title=title)
    ws.append(["2025 CMS Hospital Service Area (Medicare FFS Inpatient Catchment Only — Suppressed '<11' ZIP rows kept NULL, NOT all-payer market share)"])
    ws["A1"].font = Font(bold=True, size=11)

    scols, srows = _query_rows(db, queries["hsa_2025_hospital_catchment"])
    ws.append(scols)
    for idx in range(1, len(scols) + 1):
        c = ws.cell(row=2, column=idx)
        c.font = header_font
        c.fill = header_fill
    for r in srows:
        ws.append(list(r))

    ws.append([])
    ws.append(["Top 5 Visible Feeder Patient ZIPs per Hospital (Excludes '*' Suppressed Rows)"])
    ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=11)
    tcols, trows = _query_rows(db, queries["hsa_2025_top_feeder_zips"])
    hdr = ws.max_row + 1
    ws.append(tcols)
    for idx in range(1, len(tcols) + 1):
        c = ws.cell(row=hdr, column=idx)
        c.font = header_font
        c.fill = header_fill
    for r in trows:
        ws.append(list(r))

    ws.column_dimensions["A"].width = 12
    ws.column_dimensions["B"].width = 38
    ws.column_dimensions["D"].width = 18
    ws.freeze_panes = "A3"
    wb.save(xlsx_path)


def run_catchment_build(root: Path, raw_dir: Path, out_dir: Path) -> dict[str, Any]:
    root = Path(root)
    raw_dir = Path(raw_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_rows = json.loads((raw_dir / "catchment" / "hsa_2025_nashville.json").read_text(encoding="utf-8"))
    rows = normalize_hsa_rows(raw_rows)

    db_path = out_dir / "nashville_hospital_evidence.sqlite3"
    db = sqlite3.connect(db_path)
    db.executescript((root / "sql" / "schema.sql").read_text(encoding="utf-8"))
    db.execute("DELETE FROM hospital_service_area_2025")
    for r in rows:
        db.execute(
            "INSERT INTO hospital_service_area_2025 VALUES (?,?,?,?,?,?,?,?,?)",
            (
                r["ccn"], r["zip_cd_of_residence"],
                r["raw_total_cases"], r["parsed_total_cases"],
                r["raw_total_days_of_care"], r["parsed_total_days_of_care"],
                r["raw_total_charges"], r["parsed_total_charges"],
                r["is_suppressed"],
            ),
        )
    db.commit()

    queries = _split_named_queries(root / "sql" / "reporting_queries.sql")
    _, sum_rows = _query_rows(db, queries["hsa_2025_hospital_catchment"])
    _, top_rows = _query_rows(db, queries["hsa_2025_top_feeder_zips"])

    xlsx_path = out_dir / "Nashville_Hospital_Evidence_Pack.xlsx"
    _write_catchment_sheet(xlsx_path, db, queries)

    lines = [
        "# Reconciliation #7: Five-Hospital Medicare Catchment (`M2` CMS Hospital Service Area 2025)",
        "",
        "> [!IMPORTANT]",
        "> **Scope & Suppression Guardrail:** CMS Hospital Service Area (`8708ca8b-8636-44ed-8303-724cbfaf78ad`) covers **Medicare Fee-for-Service inpatient stays only**—not all-payer market share, not outpatient visits, and not driving/travel time. Patient ZIPs with `<11` Medicare cases are masked with `*` by CMS (`is_suppressed=1`); they remain `NULL` in SQLite (never coerced to `0` or `5`) and are counted explicitly.",
        "",
        "## Hospital Patient-Origin Summary",
        "",
        "| CCN | Hospital | Hospital ZIP | Total ZIP Rows | Visible ZIPs (`>=11` Cases) | Suppressed `<11` ZIP Rows (`*`) | Visible Medicare Cases | TN ZIP (`37x/38x`) Cases | % Visible From TN ZIPs |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for ccn, fname, hzip, tot_z, vis_z, sup_z, vis_c, tn_c, tn_pct in sum_rows:
        tp = f"{tn_pct:.1f}%" if tn_pct is not None else "n/a"
        lines.append(
            f"| `{ccn}` | {fname} | `{hzip}` | {tot_z:,} | {vis_z:,} | {sup_z:,} | {vis_c:,} | {tn_c:,} | {tp} |"
        )
    lines.extend([
        "",
        "## Top 5 Visible Feeder Patient ZIPs per Hospital",
        "",
        "| CCN | Hospital | Rank | Patient ZIP5 | Visible Cases | Visible Days of Care | Visible Charges |",
        "|---|---|---:|---|---:|---:|---:|",
    ])
    for ccn, fname, rk, pz, cases, days, chg in top_rows:
        d_s = f"{days:,}" if days is not None else "NULL"
        c_s = f"${chg:,.0f}" if chg is not None else "NULL"
        lines.append(f"| `{ccn}` | {fname} | {rk} | `{pz}` | {cases:,} | {d_s} | {c_s} |")

    md_path = out_dir / "reconciliation_7_hospital_catchment.md"
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    db.close()
    return {
        "hsa_rows": len(rows),
        "suppressed_rows": sum(r["is_suppressed"] for r in rows),
        "visible_rows": sum(1 - r["is_suppressed"] for r in rows),
        "xlsx_path": str(xlsx_path),
        "markdown_path": str(md_path),
    }


def main(argv: list[str] | None = None) -> int:
    root = Path(argv[0]) if argv else Path(".")
    res = run_catchment_build(root, root / "data" / "raw", root / "outputs")
    print(f"Catchment pack built cleanly: {res}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
