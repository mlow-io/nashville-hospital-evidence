"""Download and hash pinned CMS Hospital Compare / Provider Data inputs for S1.

Resolves current distribution download URLs via the CMS metastore API, downloads
the CSV/PDF artifacts under ``data/raw/``, verifies non-empty bytes and expected
extensions, and writes ``data/raw/manifest.json`` with SHA-256 digests and
release metadata. Never silently falls back to synthetic data.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

METASTORE_ITEMS: dict[str, dict[str, str]] = {
    "timely_care": {
        "dataset_id": "yv7e-xc69",
        "metastore_url": "https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items/yv7e-xc69",
        "filename": "Timely_and_Effective_Care-Hospital.csv",
    },
    "hospital_info": {
        "dataset_id": "xubh-q36u",
        "metastore_url": "https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items/xubh-q36u",
        "filename": "Hospital_General_Information.csv",
    },
    "footnotes": {
        "dataset_id": "y9us-9xdf",
        "metastore_url": "https://data.cms.gov/provider-data/api/1/metastore/schemas/dataset/items/y9us-9xdf",
        "filename": "Footnote_Crosswalk.csv",
    },
}

DATA_DICTIONARY_URL = (
    "https://data.cms.gov/provider-data/sites/default/files/data_dictionaries/hospital/"
    "HOSPITAL_Data_Dictionary.pdf"
)

USER_AGENT = "nashville-hospital-evidence/0.1"


def _http_get(url: str, timeout: int = 90) -> bytes:
    proc = subprocess.run(
        ["curl", "-fsSL", "--max-time", str(timeout), url],
        capture_output=True,
    )
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Download failed for {url} (curl exit {proc.returncode}): {err}")
    if not proc.stdout:
        raise RuntimeError(f"Empty payload downloaded from {url}")
    return proc.stdout


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def fetch_all(raw_dir: Path, fetcher=_http_get) -> dict[str, Any]:
    """Resolve CMS metastore URLs, download immutable raw inputs, and save manifest.json."""
    raw_dir = Path(raw_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    retrieved_at = datetime.now(timezone.utc).isoformat()
    artifacts: dict[str, Any] = {}

    for key, spec in METASTORE_ITEMS.items():
        meta_bytes = fetcher(spec["metastore_url"])
        meta = json.loads(meta_bytes.decode("utf-8"))
        dist = meta.get("distribution") or []
        if not dist or not dist[0].get("downloadURL"):
            raise RuntimeError(f"Missing distribution[0].downloadURL for {spec['dataset_id']}")
        download_url = str(dist[0]["downloadURL"])
        csv_bytes = fetcher(download_url)
        if b"," not in csv_bytes[:4096]:
            raise RuntimeError(f"Expected CSV content from {download_url}")
        target = raw_dir / spec["filename"]
        target.write_bytes(csv_bytes)
        artifacts[key] = {
            "dataset_id": spec["dataset_id"],
            "title": meta.get("title"),
            "modified": meta.get("modified"),
            "metastore_url": spec["metastore_url"],
            "download_url": download_url,
            "filename": spec["filename"],
            "bytes": len(csv_bytes),
            "sha256": _sha256_bytes(csv_bytes),
            "retrieved_at": retrieved_at,
        }

    pdf_bytes = fetcher(DATA_DICTIONARY_URL)
    if not pdf_bytes.startswith(b"%PDF"):
        raise RuntimeError(f"Expected PDF header from {DATA_DICTIONARY_URL}")
    pdf_path = raw_dir / "HOSPITAL_Data_Dictionary.pdf"
    pdf_path.write_bytes(pdf_bytes)
    artifacts["data_dictionary"] = {
        "dataset_id": "HOSPITAL_Data_Dictionary",
        "download_url": DATA_DICTIONARY_URL,
        "filename": "HOSPITAL_Data_Dictionary.pdf",
        "bytes": len(pdf_bytes),
        "sha256": _sha256_bytes(pdf_bytes),
        "retrieved_at": retrieved_at,
    }

    manifest = {
        "retrieved_at": retrieved_at,
        "artifacts": artifacts,
    }
    (raw_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    raw_dir = Path(args[0]) if args else Path("data/raw")
    manifest = fetch_all(raw_dir)
    for key, info in manifest["artifacts"].items():
        print(f"{key}: {info['filename']} ({info['bytes']:,} bytes, sha256={info['sha256'][:12]}...)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
