"""Fetch 2025 CMS Hospital Service Area (M2) rows for the 5 configured Nashville CCNs."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .fetch_extended import TARGET_FACILITIES, _curl_download

HSA_2025_DATASET_ID = "8708ca8b-8636-44ed-8303-724cbfaf78ad"
HSA_2025_API = f"https://data.cms.gov/data-api/v1/dataset/{HSA_2025_DATASET_ID}/data"


def fetch_hsa_catchment(raw_dir: Path, out_dir: Path | None = None) -> dict[str, Any]:
    raw_dir = Path(raw_dir)
    cdir = raw_dir / "catchment"
    cdir.mkdir(parents=True, exist_ok=True)
    retrieved_at = datetime.now(timezone.utc).isoformat()

    rows: list[dict[str, Any]] = []
    counts_by_ccn: dict[str, int] = {}
    for ccn in TARGET_FACILITIES:
        offset = 0
        fac_rows: list[dict[str, Any]] = []
        while True:
            url = f"{HSA_2025_API}?filter[MEDICARE_PROV_NUM]={ccn}&size=5000&offset={offset}"
            batch = json.loads(_curl_download(url, timeout=60))
            if not batch:
                break
            fac_rows.extend(batch)
            if len(batch) < 5000:
                break
            offset += 5000
        rows.extend(fac_rows)
        counts_by_ccn[ccn] = len(fac_rows)

    dest = cdir / "hsa_2025_nashville.json"
    raw_bytes = (json.dumps(rows, indent=2) + "\n").encode("utf-8")
    dest.write_bytes(raw_bytes)

    receipt = {
        "retrieved_at": retrieved_at,
        "dataset_id": HSA_2025_DATASET_ID,
        "api_url": HSA_2025_API,
        "facilities": list(TARGET_FACILITIES),
        "total_rows": len(rows),
        "rows_by_ccn": counts_by_ccn,
        "filename": str(dest.relative_to(raw_dir)),
        "bytes": len(raw_bytes),
        "sha256": hashlib.sha256(raw_bytes).hexdigest(),
    }
    (cdir / "catchment_manifest.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    if out_dir is not None:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "catchment_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main(argv: list[str] | None = None) -> int:
    raw_dir = Path(argv[0]) if argv else Path("data/raw")
    out_dir = Path(argv[1]) if argv and len(argv) > 1 else Path("outputs")
    rec = fetch_hsa_catchment(raw_dir, out_dir=out_dir)
    print(f"Fetched HSA 2025 rows={rec['total_rows']:,} by_ccn={rec['rows_by_ccn']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
