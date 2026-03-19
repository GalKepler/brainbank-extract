"""One-time script: copy and normalize QSIRecon dseg.tsv files into the package data dir.

Run from the repo root:
    uv run python scripts/generate_dseg_tsvs.py

Source: /media/storage/yalab-dev/snbb_scheduler/derivatives/qsirecon/atlases/
Dest:   src/brainbank_extract/data/atlases/
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd

SRC_ROOT = Path("/media/storage/yalab-dev/snbb_scheduler/derivatives/qsirecon/atlases")
DEST_DIR = Path(__file__).parent.parent / "src" / "brainbank_extract" / "data" / "atlases"


def copy_tsv(src: Path, dest_name: str) -> None:
    """Copy a QSIRecon dseg.tsv, keeping only index+label columns."""
    df = pd.read_csv(src, sep="\t", dtype=str)
    # Normalize column names: accept 'index'/'label' or positional
    if "index" in df.columns and "label" in df.columns:
        df = df[["index", "label"]].copy()
    else:
        # Fallback: first two columns
        df = df.iloc[:, :2].copy()
        df.columns = ["index", "label"]

    dest_path = DEST_DIR / dest_name
    df.to_csv(dest_path, sep="\t", index=False)
    print(f"  wrote {dest_path.name} ({len(df)} rows)")


def main() -> None:
    DEST_DIR.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # 1. Schaefer+Tian combined atlases (all 40)
    # -------------------------------------------------------------------------
    print("Schaefer+Tian combined atlases...")
    for n in range(100, 1100, 100):
        for s in range(1, 5):
            atlas_dir = SRC_ROOT / f"atlas-Schaefer2018N{n}n7Tian2020S{s}"
            src = atlas_dir / f"atlas-Schaefer2018N{n}n7Tian2020S{s}_dseg.tsv"
            dest_name = f"schaefer{n}x7_tian_s{s}_dseg.tsv"
            if (DEST_DIR / dest_name).exists():
                print(f"  skip {dest_name} (already exists)")
                continue
            if not src.exists():
                print(f"  MISSING: {src}")
                continue
            copy_tsv(src, dest_name)

    # -------------------------------------------------------------------------
    # 2. 4S combined atlases (all 10)
    # -------------------------------------------------------------------------
    print("4S combined atlases...")
    subcortical = 56
    for n in range(100, 1100, 100):
        total = n + subcortical
        atlas_dir = SRC_ROOT / f"atlas-4S{total}Parcels"
        src = atlas_dir / f"atlas-4S{total}Parcels_dseg.tsv"
        dest_name = f"4S{total}Parcels_dseg.tsv"
        if (DEST_DIR / dest_name).exists():
            print(f"  skip {dest_name} (already exists)")
            continue
        if not src.exists():
            print(f"  MISSING: {src}")
            continue
        copy_tsv(src, dest_name)

    # -------------------------------------------------------------------------
    # 3. Ext combined atlases
    # -------------------------------------------------------------------------
    print("Ext combined atlases...")
    ext_map = {
        "gordon333ext": "atlas-Gordon333Ext/atlas-Gordon333Ext_dseg.tsv",
        "brainnetome246ext": "atlas-Brainnetome246Ext/atlas-Brainnetome246Ext_dseg.tsv",
        "aicha384ext": "atlas-AICHA384Ext/atlas-AICHA384Ext_dseg.tsv",
        "HCPex": "atlas-HCPex/atlas-HCPex_dseg.tsv",
    }
    for dest_key, rel_src in ext_map.items():
        src = SRC_ROOT / rel_src
        dest_name = f"{dest_key}_dseg.tsv"
        if (DEST_DIR / dest_name).exists():
            print(f"  skip {dest_name} (already exists)")
            continue
        if not src.exists():
            print(f"  MISSING: {src}")
            continue
        copy_tsv(src, dest_name)

    print("Done.")


if __name__ == "__main__":
    main()
