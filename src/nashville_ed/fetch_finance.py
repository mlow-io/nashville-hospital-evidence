"""Fetch CMS HCRIS Hospital Provider Cost Reports (FY 2022-2024) and RY 2025 CERT Public Data."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .fetch_extended import TARGET_FACILITIES, _curl_download, _sha256_file

HCRIS_DATASETS: dict[str, dict[str, str]] = {
    "2022": {
        "dataset_id": "8457c184-a531-40db-8597-2497fec80c7a",
        "title": "Hospital Provider Cost Report : 2022-12-06",
    },
    "2023": {
        "dataset_id": "f08d4c46-c0e4-4bcb-a54a-c62c87d59251",
        "title": "Hospital Provider Cost Report : 2023-12-06",
    },
    "2024": {
        "dataset_id": "44060663-47d8-4ced-a115-b53b4c270acb",
        "title": "Hospital Provider Cost Report : 2024-01-02",
    },
}

HCRIS_DICTIONARY_URL = (
    "https://data.cms.gov/sites/default/files/2024-03/"
    "9756088d-5280-4090-80b9-449d31ef25a3/Cost%20Report%20Data%20Dictionary%20Update.pdf"
)

CERT_2025_DATASET_ID = "6395b458-2f89-4828-8c1a-e1e16b723d48"
CERT_2025_CSV_URL = (
    "https://data.cms.gov/sites/default/files/2026-01/"
    "53600220-96ac-49b3-bee7-83452b2b1df9/2025%20PartAPartB%20Public%20Data.csv"
)


def fetch_hcris_and_cert(raw_dir: Path, out_dir: Path | None = None) -> dict[str, Any]:
    raw_dir = Path(raw_dir)
    fin_dir = raw_dir / "finance"
    fin_dir.mkdir(parents=True, exist_ok=True)
    retrieved_at = datetime.now(timezone.utc).isoformat()

    hcris_rows: list[dict[str, Any]] = []
    hcris_meta: dict[str, Any] = {}
    for report_year, info in HCRIS_DATASETS.items():
        did = info["dataset_id"]
        api_url = f"https://data.cms.gov/data-api/v1/dataset/{did}/data"
        year_count = 0
        per_ccn: dict[str, int] = {}
        for ccn in TARGET_FACILITIES:
            url = f"{api_url}?filter[Provider%20CCN]={ccn}&size=100"
            payload = _curl_download(url, timeout=60)
            batch = json.loads(payload)
            for row in batch:
                row["_hcris_release_year"] = report_year
                row["_hcris_dataset_id"] = did
                hcris_rows.append(row)
            per_ccn[ccn] = len(batch)
            year_count += len(batch)
        hcris_meta[report_year] = {
            "dataset_id": did,
            "title": info["title"],
            "api_url": api_url,
            "row_count": year_count,
            "rows_by_ccn": per_ccn,
        }

    hcris_path = fin_dir / "hcris_nashville_2022_2024.json"
    hcris_bytes = (json.dumps(hcris_rows, indent=2) + "\n").encode("utf-8")
    hcris_path.write_bytes(hcris_bytes)

    dict_path = fin_dir / "Cost_Report_Data_Dictionary.pdf"
    if not dict_path.exists() or dict_path.stat().st_size == 0:
        _curl_download(HCRIS_DICTIONARY_URL, dest=dict_path, timeout=90)

    cert_path = fin_dir / "cert_2025_partA_partB_public_data.csv"
    if not cert_path.exists() or cert_path.stat().st_size == 0:
        _curl_download(CERT_2025_CSV_URL, dest=cert_path, timeout=180)

    receipt: dict[str, Any] = {
        "retrieved_at": retrieved_at,
        "facilities": list(TARGET_FACILITIES),
        "hcris": {
            "releases": hcris_meta,
            "total_rows": len(hcris_rows),
            "filename": str(hcris_path.relative_to(raw_dir)),
            "bytes": len(hcris_bytes),
            "sha256": hashlib.sha256(hcris_bytes).hexdigest(),
            "dictionary": {
                "url": HCRIS_DICTIONARY_URL,
                "filename": str(dict_path.relative_to(raw_dir)),
                "bytes": dict_path.stat().st_size,
                "sha256": _sha256_file(dict_path),
            },
        },
        "cert_2025": {
            "dataset_id": CERT_2025_DATASET_ID,
            "csv_url": CERT_2025_CSV_URL,
            "filename": str(cert_path.relative_to(raw_dir)),
            "bytes": cert_path.stat().st_size,
            "sha256": _sha256_file(cert_path),
        },
    }
    (fin_dir / "finance_manifest.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    if out_dir is not None:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "finance_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main(argv: list[str] | None = None) -> int:
    raw_dir = Path(argv[0]) if argv else Path("data/raw")
    out_dir = Path(argv[1]) if argv and len(argv) > 1 else Path("outputs")
    rec = fetch_hcris_and_cert(raw_dir, out_dir=out_dir)
    print(
        f"Fetched HCRIS rows={rec['hcris']['total_rows']} across {len(rec['hcris']['releases'])} years; "
        f"CERT CSV={rec['cert_2025']['bytes']:,} bytes (sha256={rec['cert_2025']['sha256'][:12]}...)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
