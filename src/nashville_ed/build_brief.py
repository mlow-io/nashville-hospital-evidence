"""Parse, reconcile, and build the S1 five-hospital Nashville ED measurement brief.

Preserves Facility ID and ZIP Code as strings, keeps raw Score/Sample/Footnote/Date
fields alongside parsed nullable values (never converting "Not Available" to 0),
reconciles 100% of raw input rows (raw == retained_in_scope + discarded_out_of_scope),
joins Hospital General Information by exact Facility ID (failing if duplicates exist),
and renders CSV, Markdown, HTML, and audit receipt artifacts.
"""
from __future__ import annotations

import csv
import html
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TARGET_FACILITIES: tuple[str, ...] = ("440029", "440039", "440073", "440082", "440161")
TARGET_MEASURES: tuple[str, ...] = ("OP_18b", "OP_22")

MEASURE_LABELS: dict[str, dict[str, str]] = {
    "OP_18b": {
        "short_label": "ED Arrival to Departure (OP_18b)",
        "unit": "minutes",
        "period_label": "2025 (01/01/2025 - 12/31/2025)",
        "expected_year": "2025",
    },
    "OP_22": {
        "short_label": "Left Without Being Seen (OP_22)",
        "unit": "percent",
        "period_label": "2024 (01/01/2024 - 12/31/2024)",
        "expected_year": "2024",
    },
}


@dataclass(frozen=True)
class ObservationRow:
    facility_id: str
    facility_name: str
    city_town: str
    state: str
    zip_code: str
    hospital_type: str
    hospital_ownership: str
    measure_id: str
    measure_name: str
    unit: str
    period_label: str
    raw_score: str
    parsed_score: int | None
    raw_sample: str
    parsed_sample: int | None
    raw_footnote: str
    footnote_text: str
    start_date: str
    end_date: str
    source_row_number: int


def _parse_optional_int(raw_value: str, field_name: str) -> int | None:
    cleaned = raw_value.strip()
    if not cleaned or cleaned.lower() == "not available":
        return None
    if not cleaned.isdigit():
        raise ValueError(f"Unexpected non-integer value for {field_name}: {raw_value!r}")
    return int(cleaned)


def load_footnotes(footnotes_csv: Path) -> dict[str, str]:
    """Load footnote code -> text mapping while preserving all codes as trimmed strings."""
    mapping: dict[str, str] = {}
    with footnotes_csv.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or len(reader.fieldnames) < 2:
            raise ValueError(f"Malformed footnotes CSV: {footnotes_csv}")
        code_col, text_col = reader.fieldnames[0], reader.fieldnames[1]
        for row in reader:
            code = (row.get(code_col) or "").strip()
            text = (row.get(text_col) or "").strip()
            if code:
                mapping[code] = text
    return mapping


def decode_footnotes(raw_footnote: str, crosswalk: dict[str, str]) -> str:
    """Decode comma-separated footnote codes and label unknown codes visibly."""
    cleaned = raw_footnote.strip()
    if not cleaned:
        return ""
    parts = [part.strip() for part in cleaned.split(",") if part.strip()]
    decoded: list[str] = []
    for code in parts:
        text = crosswalk.get(code)
        decoded.append(f"[{code}] {text}" if text else f"[{code}] Unknown footnote code")
    return "; ".join(decoded)


def load_hospital_attributes(hosp_csv: Path, facility_ids: set[str]) -> dict[str, dict[str, str]]:
    """Index Hospital General Information by string Facility ID; fail on duplicate dimension keys."""
    by_id: dict[str, dict[str, str]] = {}
    with hosp_csv.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            fid = (row.get("Facility ID") or "").strip()
            if fid not in facility_ids:
                continue
            if fid in by_id:
                raise ValueError(f"Duplicate Facility ID {fid} in hospital dimension {hosp_csv}")
            by_id[fid] = {
                "facility_name": (row.get("Facility Name") or "").strip(),
                "city_town": (row.get("City/Town") or "").strip(),
                "state": (row.get("State") or "").strip(),
                "zip_code": (row.get("ZIP Code") or "").strip(),
                "hospital_type": (row.get("Hospital Type") or "").strip(),
                "hospital_ownership": (row.get("Hospital Ownership") or "").strip(),
            }
    return by_id


def build_observations(
    timely_csv: Path,
    hosp_csv: Path,
    footnotes_csv: Path,
    *,
    facilities: tuple[str, ...] = TARGET_FACILITIES,
    measures: tuple[str, ...] = TARGET_MEASURES,
) -> tuple[list[ObservationRow], dict[str, int]]:
    """Extract target S1 rows, enforce row reconciliation, and join hospital/footnote metadata."""
    facility_set = set(facilities)
    measure_set = set(measures)
    crosswalk = load_footnotes(footnotes_csv)
    hosp_dim = load_hospital_attributes(hosp_csv, facility_set)

    raw_total = 0
    discarded_out_of_scope = 0
    rows: list[ObservationRow] = []

    with timely_csv.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row_num, rec in enumerate(reader, start=2):
            raw_total += 1
            fid = (rec.get("Facility ID") or "").strip()
            mid = (rec.get("Measure ID") or "").strip()
            if fid not in facility_set or mid not in measure_set:
                discarded_out_of_scope += 1
                continue

            if fid not in hosp_dim:
                raise ValueError(f"Missing hospital dimension row for Facility ID {fid}")
            dim = hosp_dim[fid]
            spec = MEASURE_LABELS[mid]

            end_date = (rec.get("End Date") or "").strip()
            if spec["expected_year"] not in end_date:
                raise ValueError(
                    f"Unexpected collection window {rec.get('Start Date')}..{end_date} for {mid} "
                    f"(expected {spec['expected_year']})"
                )

            raw_score = (rec.get("Score") or "").strip()
            raw_sample = (rec.get("Sample") or "").strip()
            raw_footnote = (rec.get("Footnote") or "").strip()

            rows.append(
                ObservationRow(
                    facility_id=fid,
                    facility_name=dim["facility_name"] or (rec.get("Facility Name") or "").strip(),
                    city_town=dim["city_town"] or (rec.get("City/Town") or "").strip(),
                    state=dim["state"] or (rec.get("State") or "").strip(),
                    zip_code=dim["zip_code"] or (rec.get("ZIP Code") or "").strip(),
                    hospital_type=dim["hospital_type"],
                    hospital_ownership=dim["hospital_ownership"],
                    measure_id=mid,
                    measure_name=(rec.get("Measure Name") or "").strip(),
                    unit=spec["unit"],
                    period_label=spec["period_label"],
                    raw_score=raw_score,
                    parsed_score=_parse_optional_int(raw_score, "Score"),
                    raw_sample=raw_sample,
                    parsed_sample=_parse_optional_int(raw_sample, "Sample"),
                    raw_footnote=raw_footnote,
                    footnote_text=decode_footnotes(raw_footnote, crosswalk),
                    start_date=(rec.get("Start Date") or "").strip(),
                    end_date=end_date,
                    source_row_number=row_num,
                )
            )

    expected_count = len(facilities) * len(measures)
    if len(rows) != expected_count:
        raise ValueError(
            f"Expected {expected_count} retained S1 rows ({len(facilities)} facilities x "
            f"{len(measures)} measures), found {len(rows)}"
        )
    if raw_total != len(rows) + discarded_out_of_scope:
        raise AssertionError("Row reconciliation failed: raw != retained + discarded")

    order_fac = {fid: i for i, fid in enumerate(facilities)}
    order_meas = {mid: i for i, mid in enumerate(measures)}
    rows.sort(key=lambda r: (order_fac[r.facility_id], order_meas[r.measure_id]))

    counts = {
        "raw_total": raw_total,
        "retained_in_scope": len(rows),
        "discarded_out_of_scope": discarded_out_of_scope,
    }
    return rows, counts


def write_observations_csv(path: Path, rows: list[ObservationRow]) -> None:
    fields = list(ObservationRow.__dataclass_fields__.keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            data = asdict(row)
            writer.writerow({k: ("" if v is None else v) for k, v in data.items()})


def _facility_summary(rows: list[ObservationRow]) -> list[dict[str, Any]]:
    by_fac: dict[str, dict[str, Any]] = {}
    for row in rows:
        entry = by_id = by_fac.setdefault(
            row.facility_id,
            {
                "facility_id": row.facility_id,
                "facility_name": row.facility_name,
                "city_town": row.city_town,
                "zip_code": row.zip_code,
                "hospital_ownership": row.hospital_ownership,
            },
        )
        entry[row.measure_id] = row
        _ = by_id
    return list(by_fac.values())


def render_brief_markdown(rows: list[ObservationRow], manifest: dict[str, Any], counts: dict[str, int]) -> str:
    summary = _facility_summary(rows)
    timely_meta = manifest.get("artifacts", {}).get("timely_care", {})
    hosp_meta = manifest.get("artifacts", {}).get("hospital_info", {})
    foot_meta = manifest.get("artifacts", {}).get("footnotes", {})

    lines = [
        "# Nashville-Area Emergency Department Measurement Brief (CMS Release Comparison Guardrail)",
        "",
        f"**Scope:** Five selected Middle Tennessee acute-care hospitals · **CMS Releases:** Timely Care (`yv7e-xc69`, modified `{timely_meta.get('modified', 'unknown')}`), Hospital General Info (`xubh-q36u`, modified `{hosp_meta.get('modified', 'unknown')}`), Footnotes (`y9us-9xdf`, modified `{foot_meta.get('modified', 'unknown')}`).",
        "",
        "## Headline Finding",
        "",
        "One single CMS Hospital Compare release (`yv7e-xc69`) publishes **two different measurement years side by side**:",
        "- **`OP_18b` (Median ED time before departure, discharged patients, in minutes):** measured across **calendar year 2025 (`01/01/2025`–`12/31/2025`)**.",
        "- **`OP_22` (Left before being seen by a healthcare professional, percentage):** measured across **calendar year 2024 (`01/01/2024`–`12/31/2024`)**.",
        "",
        "Treating both columns as the same reporting year—or replacing `Not Available` with `0%`—produces false hospital comparisons.",
        "",
        "## Selected Five-Hospital Evidence Table",
        "",
        "| Facility ID | Hospital Name (CMS Source) | City / ZIP | `OP_18b` Median Minutes (**2025**) | `OP_18b` Cases | `OP_22` Left Before Seen (**2024**) | `OP_22` Sample | Source Rows |",
        "|---|---|---|---:|---:|---:|---:|---|",
    ]

    for item in summary:
        m18: ObservationRow = item["OP_18b"]
        m22: ObservationRow = item["OP_22"]
        op18_disp = f"{m18.parsed_score} min" if m18.parsed_score is not None else f"{m18.raw_score} (Footnote {m18.raw_footnote})"
        op22_disp = (
            f"{m22.parsed_score}%"
            if m22.parsed_score is not None
            else f"{m22.raw_score}; Footnote {m22.raw_footnote} ({m22.footnote_text})"
        )
        op22_sample = f"{m22.parsed_sample:,}" if m22.parsed_sample is not None else m22.raw_sample
        op18_sample = f"{m18.parsed_sample:,}" if m18.parsed_sample is not None else m18.raw_sample
        lines.append(
            f"| `{item['facility_id']}` | {item['facility_name']} | {item['city_town']}, TN `{item['zip_code']}` | "
            f"{op18_disp} | {op18_sample} | {op22_disp} | {op22_sample} | rows {m18.source_row_number}, {m22.source_row_number} |"
        )

    lines.extend([
        "",
        "## Mandatory Limitations & Misinterpretation Guardrails",
        "",
        "1. **Not today's live ER wait time:** `OP_18b` is a historical annual median (`01/01/2025`–`12/31/2025`) for discharged ED patients, excluding patients admitted to the hospital, transfers, and psychiatric/mental-health visits per CMS measure definitions.",
        "2. **Mismatched reporting periods inside one file:** `OP_18b` covers **2025**, whereas `OP_22` covers **2024**. Never chart or compare them as simultaneous same-year performance.",
        "3. **Unavailable values stay unavailable:** Ascension Saint Thomas Hospital (`440082`) reports `OP_22 = Not Available` with **Footnote 5** (*\"Results are not available for this reporting period.\"*). Footnote 5 does not state an underlying operational cause and must never be coerced to `0%`.",
        "4. **Deliberate nearby cohort, not a ranking:** These five facilities are a purposefully selected Middle Tennessee comparison set, not a census of all Tennessee hospitals and not a \"best hospital\" ranking.",
        "5. **CMS publication is not Medicare-only:** Published Hospital Compare timely-care metrics reflect all eligible cases defined in the measure specification rather than Medicare fee-for-service alone.",
        "",
        "## Audit Reconciliation & Source Links",
        "",
        f"- **Row reconciliation:** `{counts['raw_total']:,}` raw rows scanned in `Timely_and_Effective_Care-Hospital.csv` = `{counts['retained_in_scope']}` retained in-scope observations + `{counts['discarded_out_of_scope']:,}` out-of-scope rows discarded (0 silent drops).",
        f"- **Measures CSV (`yv7e-xc69`):** {timely_meta.get('download_url', '')} (`sha256: {timely_meta.get('sha256', '')[:16]}...`)",
        f"- **Hospital Info CSV (`xubh-q36u`):** {hosp_meta.get('download_url', '')} (`sha256: {hosp_meta.get('sha256', '')[:16]}...`)",
        f"- **Footnote Crosswalk (`y9us-9xdf`):** {foot_meta.get('download_url', '')} (`sha256: {foot_meta.get('sha256', '')[:16]}...`)",
    ])
    return "\n".join(lines) + "\n"


def render_brief_html(rows: list[ObservationRow], manifest: dict[str, Any], counts: dict[str, int]) -> str:
    summary = _facility_summary(rows)
    timely_meta = manifest.get("artifacts", {}).get("timely_care", {})
    hosp_meta = manifest.get("artifacts", {}).get("hospital_info", {})
    foot_meta = manifest.get("artifacts", {}).get("footnotes", {})
    dict_meta = manifest.get("artifacts", {}).get("data_dictionary", {})

    table_rows = []
    for item in summary:
        m18: ObservationRow = item["OP_18b"]
        m22: ObservationRow = item["OP_22"]
        op18 = f"{m18.parsed_score} min" if m18.parsed_score is not None else html.escape(m18.raw_score)
        op22 = (
            f"{m22.parsed_score}%"
            if m22.parsed_score is not None
            else f'<span class="na">Not Available (Footnote {html.escape(m22.raw_footnote)})</span>'
        )
        s18 = f"{m18.parsed_sample:,}" if m18.parsed_sample is not None else html.escape(m18.raw_sample)
        s22 = f"{m22.parsed_sample:,}" if m22.parsed_sample is not None else html.escape(m22.raw_sample)
        table_rows.append(
            f"<tr>"
            f"<td><code>{html.escape(item['facility_id'])}</code></td>"
            f"<td><strong>{html.escape(item['facility_name'])}</strong><br><small>{html.escape(item['city_town'])}, TN {html.escape(item['zip_code'])}</small></td>"
            f"<td class='num'>{op18}<br><small>n={s18}</small></td>"
            f"<td class='num'>{op22}<br><small>n={s22}</small></td>"
            f"<td><code>rows {m18.source_row_number}, {m22.source_row_number}</code></td>"
            f"</tr>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Nashville ED Measurement Brief (S1)</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #0f172a; background: #f8fafc; margin: 0; padding: 2rem; line-height: 1.5; }}
    main {{ max-width: 960px; margin: 0 auto; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 2rem; }}
    h1 {{ font-size: 1.5rem; margin-top: 0; }}
    .subtitle {{ color: #475569; font-size: 0.9rem; margin-bottom: 1.5rem; }}
    .callout {{ background: #eff6ff; border-left: 4px solid #2563eb; padding: 0.9rem 1rem; border-radius: 6px; margin-bottom: 1.5rem; font-size: 0.92rem; }}
    .limits {{ background: #fffbeb; border: 1px solid #fde68a; padding: 1rem 1.25rem; border-radius: 8px; margin-top: 1.5rem; }}
    .limits h2 {{ margin-top: 0; font-size: 1rem; color: #92400e; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.9rem; }}
    th, td {{ border-bottom: 1px solid #e2e8f0; padding: 0.7rem 0.6rem; text-align: left; vertical-align: top; }}
    th {{ background: #f1f5f9; font-weight: 600; font-size: 0.82rem; color: #334155; }}
    td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .na {{ color: #b45309; font-weight: 600; }}
    code {{ background: #f1f5f9; padding: 0.1rem 0.35rem; border-radius: 4px; font-size: 0.85em; }}
    .sources {{ margin-top: 1.5rem; font-size: 0.84rem; color: #475569; }}
  </style>
</head>
<body>
<main>
  <h1>Nashville-Area ED Measurement Brief</h1>
  <div class="subtitle">
    CMS Provider Data · Timely &amp; Effective Care (<code>yv7e-xc69</code>, modified {html.escape(str(timely_meta.get('modified', '')))}) ·
    Row reconciliation: {counts['raw_total']:,} scanned = {counts['retained_in_scope']} retained + {counts['discarded_out_of_scope']:,} out of scope
  </div>
  <div class="callout">
    <strong>Why one release still requires period checking:</strong> <code>OP_18b</code> reports <strong>2025</strong> median ED arrival-to-departure duration (discharged cohort, minutes), while <code>OP_22</code> in the very same CSV file reports <strong>2024</strong> left-before-being-seen rates (%).
  </div>
  <table>
    <thead>
      <tr>
        <th>Facility ID</th>
        <th>Hospital Name &amp; Location</th>
        <th style="text-align:right">OP_18b Median Min (<strong>2025</strong>)</th>
        <th style="text-align:right">OP_22 Left Before Seen (<strong>2024</strong>)</th>
        <th>Source CSV Rows</th>
      </tr>
    </thead>
    <tbody>
      {"".join(table_rows)}
    </tbody>
  </table>
  <section class="limits">
    <h2>Limitations &amp; Interpretation Guardrails</h2>
    <ul>
      <li><strong>Not today's live wait time:</strong> <code>OP_18b</code> is a calendar-year 2025 median for discharged ED visits only (excludes admissions, transfers, and psychiatric visits).</li>
      <li><strong>Never coerce unavailable to zero:</strong> Ascension Saint Thomas (<code>440082</code>) carries Footnote 5 (<em>"Results are not available for this reporting period."</em>), which does not identify a cause.</li>
      <li><strong>Selected local comparison only:</strong> Five chosen Middle Tennessee hospitals—not a ranking of best hospital care and not all Tennessee facilities.</li>
    </ul>
  </section>
  <section class="sources">
    <strong>Pinned Sources:</strong>
    <a href="{html.escape(str(timely_meta.get('download_url', '#')))}">Measures CSV (yv7e-xc69)</a> ·
    <a href="{html.escape(str(hosp_meta.get('download_url', '#')))}">Hospital Info CSV (xubh-q36u)</a> ·
    <a href="{html.escape(str(foot_meta.get('download_url', '#')))}">Footnote Crosswalk (y9us-9xdf)</a> ·
    <a href="{html.escape(str(dict_meta.get('download_url', '#')))}">Hospital Data Dictionary PDF</a>
  </section>
</main>
</body>
</html>
"""


def run_build(raw_dir: Path, out_dir: Path) -> dict[str, Any]:
    raw_dir = Path(raw_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = raw_dir / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing raw manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    rows, counts = build_observations(
        raw_dir / "Timely_and_Effective_Care-Hospital.csv",
        raw_dir / "Hospital_General_Information.csv",
        raw_dir / "Footnote_Crosswalk.csv",
    )

    write_observations_csv(out_dir / "nashville_ed_observations.csv", rows)
    (out_dir / "nashville_ed_brief.md").write_text(
        render_brief_markdown(rows, manifest, counts), encoding="utf-8"
    )
    (out_dir / "nashville_ed_brief.html").write_text(
        render_brief_html(rows, manifest, counts), encoding="utf-8"
    )

    receipt = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": manifest.get("artifacts", {}),
        "reconciliation": counts,
        "retained_rows": [asdict(r) for r in rows],
    }
    (out_dir / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    receipt_md = [
        "# S1 Build Receipt",
        "",
        f"- Generated UTC: `{receipt['generated_at']}`",
        f"- Raw rows scanned: `{counts['raw_total']:,}`",
        f"- Retained in scope: `{counts['retained_in_scope']}`",
        f"- Discarded out of scope: `{counts['discarded_out_of_scope']:,}`",
        "",
        "| Key | Dataset ID | Modified | SHA-256 (prefix) | Bytes |",
        "|---|---|---|---|---:|",
    ]
    for key, info in receipt["inputs"].items():
        receipt_md.append(
            f"| `{key}` | `{info.get('dataset_id', '')}` | `{info.get('modified', 'n/a')}` | `{str(info.get('sha256', ''))[:16]}` | {info.get('bytes', 0):,} |"
        )
    (out_dir / "receipt.md").write_text("\n".join(receipt_md) + "\n", encoding="utf-8")
    return receipt


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    raw_dir = Path(args[0]) if len(args) > 0 else Path("data/raw")
    out_dir = Path(args[1]) if len(args) > 1 else Path("outputs")
    receipt = run_build(raw_dir, out_dir)
    c = receipt["reconciliation"]
    print(f"S1 built cleanly: raw={c['raw_total']:,}, retained={c['retained_in_scope']}, discarded={c['discarded_out_of_scope']:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
