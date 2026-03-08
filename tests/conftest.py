"""Pytest fixtures providing mock FreeSurfer and QSIRecon directory trees."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest


@pytest.fixture
def mock_freesurfer_dir(tmp_path: Path) -> Path:
    """Create a minimal mock FreeSurfer subject directory.

    Structure::

        freesurfer/
        ├── surf/
        │   ├── lh.thickness
        │   ├── rh.thickness
        │   ├── lh.area
        │   └── rh.area
        ├── label/
        │   ├── lh.aparc.annot
        │   └── rh.aparc.annot
        └── stats/
            ├── aseg.stats
            ├── lh.aparc.stats
            └── rh.aparc.stats
    """
    fs_dir = tmp_path / "freesurfer"

    # Create directory structure
    (fs_dir / "surf").mkdir(parents=True)
    (fs_dir / "label").mkdir(parents=True)
    (fs_dir / "stats").mkdir(parents=True)

    # Minimal aseg.stats content
    aseg_stats = """\
# Title Segmentation Statistics
#
# Measure BrainSeg, BrainSegVol, Brain Segmentation Volume, 1234567.0, mm^3
# Measure BrainSegNotVent, BrainSegVolNotVent, Brain Segmentation Volume Without Ventricles, 1200000.0, mm^3
# Measure lhCortex, lhCortexVol, Left hemisphere cortical gray matter volume, 250000.0, mm^3
# Measure rhCortex, rhCortexVol, Right hemisphere cortical gray matter volume, 248000.0, mm^3
# Measure SubCortGray, SubCortGrayVol, Subcortical gray matter volume, 60000.0, mm^3
# Measure WM, WMVol, White matter volume, 480000.0, mm^3
# Measure Mask, MaskVol, Mask Volume, 1500000.0, mm^3
# Measure EstimatedTotalIntraCranialVol, eTIV, Estimated Total Intracranial Volume, 1600000.0, mm^3
# ColHeaders  Index SegId NVoxels Volume_mm3 StructName normMean normStdDev normMin normMax normRange
  1  4     5234  5234.0  Left-Lateral-Ventricle       26.5218   9.4558   0.0000  86.0000  86.0000
  2 28     3517  3517.0  Left-Accumbens-area          91.2141   6.1234  59.0000 107.0000  48.0000
"""
    (fs_dir / "stats" / "aseg.stats").write_text(aseg_stats)

    # Empty placeholder files for surface data
    (fs_dir / "surf" / "lh.thickness").write_bytes(b"")
    (fs_dir / "surf" / "rh.thickness").write_bytes(b"")
    (fs_dir / "label" / "lh.aparc.annot").write_bytes(b"")
    (fs_dir / "label" / "rh.aparc.annot").write_bytes(b"")

    return fs_dir


@pytest.fixture
def mock_qsirecon_dir(tmp_path: Path) -> Path:
    """Create a minimal mock QSIRecon session directory.

    Structure::

        qsirecon/
        └── dwi/
            ├── sub-001_ses-test_space-T1w_atlas-Schaefer400x7_model-DTI_param-FA_desc-preproc_parc.tsv
            ├── sub-001_ses-test_space-T1w_atlas-Schaefer400x7_desc-sift2_connectivity.csv
            └── (no pyAFQ outputs)
    """
    qsi_dir = tmp_path / "qsirecon"
    dwi_dir = qsi_dir / "dwi"
    dwi_dir.mkdir(parents=True)

    # Minimal parcellated scalar TSV
    parc_content = "label\tregion_label\tmean\tstd\tmedian\tn_voxels\n"
    parc_content += "1\tLH_Vis_1\t0.45\t0.05\t0.44\t120\n"
    parc_content += "2\tLH_Vis_2\t0.47\t0.04\t0.46\t115\n"
    (dwi_dir / "sub-001_ses-test_space-T1w_atlas-Schaefer400x7_model-DTI_param-FA_desc-preproc_parc.tsv").write_text(
        parc_content
    )

    # Minimal connectivity CSV (2x2 for simplicity)
    conn_content = "LH_Vis_1,LH_Vis_2\n0,150\n150,0\n"
    (dwi_dir / "sub-001_ses-test_space-T1w_atlas-Schaefer400x7_desc-sift2_connectivity.csv").write_text(
        conn_content
    )

    return qsi_dir


@pytest.fixture
def mock_extract_dir(tmp_path: Path) -> Path:
    """Create a mock brainbank-extract output directory with two sessions."""
    extract_dir = tmp_path / "brainbank-extract"

    sessions = [
        ("sub-001", "ses-20240101"),
        ("sub-001", "ses-20240601"),
        ("sub-002", "ses-20240101"),
    ]

    for subject, session in sessions:
        session_dir = extract_dir / subject / session
        (session_dir / "anat").mkdir(parents=True)
        (session_dir / "dwi" / "scalars").mkdir(parents=True)
        (session_dir / "dwi" / "connectivity").mkdir(parents=True)

        # Write a minimal status JSON
        status = {
            "subject": subject,
            "session": session,
            "extraction_date": "2026-03-08T12:00:00",
            "brainbank_extract_version": "0.1.0",
            "atlases_extracted": ["schaefer400x7"],
            "atlases_skipped": [],
            "modalities": {
                "anat": {"status": "complete", "n_files": 2},
                "dwi_scalars": {"status": "complete", "n_files": 1},
                "dwi_connectivity": {"status": "complete", "n_files": 1},
                "dwi_tractprofiles": {"status": "skipped", "reason": "no pyAFQ outputs"},
            },
            "warnings": [],
        }
        (session_dir / "_status.json").write_text(json.dumps(status, indent=2))

    return extract_dir
