"""Fetch CMS Hospital Archive snapshots (M1/A1) and 2024 Medicare Inpatient DRG data (RCM S2)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TARGET_FACILITIES: tuple[str, ...] = ("440029", "440039", "440073", "440082", "440161")

ARCHIVE_URLS: dict[str, str] = {
    "2026-08-13": "https://data.cms.gov/provider-data/sites/default/files/dataset-archives/theme/hospitals/hospitals_2026-08-13.zip",
    "2026-09-30": "https://data.cms.gov/provider-data/sites/default/files/dataset-archives/theme/hospitals/hospitals_2026-09-30.zip",
    "2026-11-12": "https://data.cms.gov/provider-data/sites/default/files/dataset-archives/theme/hospitals/hospitals_2026-11-12.zip",
}

INPATIENT_2024_API = (
    "https://data.cms.gov/data-api/v1/dataset/"
    "690ddc6c-2767-4618-b277-420ffb2bf27c/data"
)


def _curl_download(url: str, dest: Path | None = None, timeout: int = 120) -> bytes:
    cmd = ["curl", "-g", "-fsSL", "--max-time", str(timeout)]
    if dest is not None:
        cmd.extend(["-o", str(dest), url])
        proc = subprocess.run(cmd, capture_output=True)
        if proc.returncode != 0 or not dest.exists() or dest.stat().st_size == 0:
            raise RuntimeError(f"Download failed for {url}: {proc.stderr.decode('utf-8', errors='replace')}")
        return dest.read_bytes()
    proc = subprocess.run([*cmd, url], capture_output=True)
    if proc.returncode != 0 or not proc.stdout:
        raise RuntimeError(f"Download failed for {url}: {proc.stderr.decode('utf-8', errors='replace')}")
    return proc.stdout


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_archives_and_inpatient(raw_dir: Path) -> dict[str, Any]:
    raw_dir = Path(raw_dir)
    arch_dir = raw_dir / "archives"
    arch_dir.mkdir(parents=True, exist_ok=True)
    retrieved_at = datetime.now(timezone.utc).isoformat()

    archives_meta: dict[str, Any] = {}
    for release_date, url in ARCHIVE_URLS.items():
        zpath = arch_dir / f"hospitals_{release_date}.zip"
        if not zpath.exists() or zpath.stat().st_size == 0:
            _curl_download(url, dest=zpath, timeout=180)
        with zipfile.ZipFile(zpath) as zf:
            names = sorted(zf.namelist())
        timely_matches = [
            n for n in names
            if not n.startswith("__MACOSX")
            and "yv7e-xc69" in Path(n).name.lower()
            and n.lower().endswith(".csv")
        ]
        hosp_matches = [
            n for n in names
            if not n.startswith("__MACOSX")
            and "xubh-q36u" in Path(n).name.lower()
            and n.lower().endswith(".csv")
        ]
        foot_matches = [
            n for n in names
            if not n.startswith("__MACOSX")
            and "y9us-9xdf" in Path(n).name.lower()
            and n.lower().endswith(".csv")
        ]
        archives_meta[release_date] = {
            "release_date": release_date,
            "download_url": url,
            "filename": zpath.name,
            "bytes": zpath.stat().st_size,
            "sha256": _sha256_file(zpath),
            "file_count": len([n for n in names if not n.startswith("__MACOSX")]),
            "timely_care_entry": timely_matches[0] if timely_matches else None,
            "hospital_info_entry": hosp_matches[0] if hosp_matches else None,
            "footnotes_entry": foot_matches[0] if foot_matches else None,
            "has_timely_care": bool(timely_matches),
            "rural_emergency_entries": [
                n for n in names
                if not n.startswith("__MACOSX") and ("97xg-v3wv" in n.lower() or "reh_timely" in n.lower())
            ],
        }

    inpatient_rows: list[dict[str, Any]] = []
    for fid in TARGET_FACILITIES:
        offset = 0
        while True:
            url = f"{INPATIENT_2024_API}?filter[Rndrng_Prvdr_CCN]={fid}&size=5000&offset={offset}"
            payload = _curl_download(url, timeout=60)
            batch = json.loads(payload)
            if not batch:
                break
            inpatient_rows.extend(batch)
            if len(batch) < 5000:
                break
            offset += 5000

    inp_path = raw_dir / "inpatient_nashville_2024.json"
    inp_bytes = (json.dumps(inpatient_rows, indent=2) + "\n").encode("utf-8")
    inp_path.write_bytes(inp_bytes)

    manifest = {
        "retrieved_at": retrieved_at,
        "archives": archives_meta,
        "inpatient_2024": {
            "dataset_id": "690ddc6c-2767-4618-b277-420ffb2bf27c",
            "api_url": INPATIENT_2024_API,
            "facilities": list(TARGET_FACILITIES),
            "row_count": len(inpatient_rows),
            "bytes": len(inp_bytes),
            "sha256": hashlib.sha256(inp_bytes).hexdigest(),
        },
    }
    (raw_dir / "extended_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    raw_dir = Path(argv[0]) if argv else Path("data/raw")
    manifest = fetch_archives_and_inpatient(raw_dir)
    for d, info in manifest["archives"].items():
        print(f"archive {d}: {info['bytes']:,}B, files={info['file_count']}, timely_care={info['timely_care_entry']}")
    inp = manifest["inpatient_2024"]
    print(f"inpatient_2024: {inp['row_count']:,} rows across {len(inp['facilities'])} facilities")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
