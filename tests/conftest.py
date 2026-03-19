"""Pytest fixtures providing mock FreeSurfer and QSIRecon directory trees."""

from __future__ import annotations

import json
from pathlib import Path

import nibabel as nib
import nibabel.freesurfer.io as fsio
import numpy as np
import pytest
import scipy.io

# Number of vertices per hemisphere in mock surfaces.
N_VERTICES = 24

# Mock parcellation: 3 real regions + 1 unknown (index 0).
MOCK_REGION_NAMES = ["unknown", "superiorfrontal", "middlefrontal", "precentral"]
MOCK_CTAB = np.array(
    [
        [25, 5, 25, 0, 0],
        [70, 130, 180, 0, 1],
        [245, 245, 245, 0, 2],
        [196, 58, 250, 0, 3],
    ],
    dtype=np.int32,
)
# Distribute vertices: 0=unknown(4), 1=superiorfrontal(6), 2=middlefrontal(7), 3=precentral(7)
MOCK_LABELS = np.array(
    [0] * 4 + [1] * 6 + [2] * 7 + [3] * 7,
    dtype=np.int32,
)

# Mock atlas for QSIRecon: 4 parcels (LH=2, RH=2)
MOCK_QSI_LABELS = {1: "LH_Vis_1", 2: "LH_Vis_2", 3: "RH_Vis_1", 4: "RH_Vis_2"}
MOCK_QSI_ATLAS_SHAPE = (10, 10, 10)  # small 3D volume

# Mock combined Schaefer100+TianS1 atlas: 4 cortical (LH_/RH_) + 2 subcortical (Tian naming)
MOCK_COMBINED_LABELS = {
    1: "LH_Vis_1", 2: "LH_Vis_2", 3: "RH_Vis_1", 4: "RH_Vis_2",
    5: "HIP-lh", 6: "HIP-rh",
}
MOCK_COMBINED_CORTICAL_LABELS = {k: v for k, v in MOCK_COMBINED_LABELS.items() if v.startswith(("LH_", "RH_"))}
MOCK_COMBINED_SUBCORTICAL_LABELS = {k: v for k, v in MOCK_COMBINED_LABELS.items() if not v.startswith(("LH_", "RH_"))}


def _write_annot(path: Path, labels: np.ndarray, ctab: np.ndarray, names: list[str]) -> None:
    fsio.write_annot(str(path), labels, ctab, names)


def _write_morph(path: Path, data: np.ndarray) -> None:
    fsio.write_morph_data(str(path), data)


def _make_atlas_nii(shape: tuple, labels: dict[int, str]) -> nib.Nifti1Image:
    """Create a small NIfTI atlas image with one voxel per label."""
    data = np.zeros(shape, dtype=np.int16)
    n = len(labels)
    for i, idx in enumerate(sorted(labels)):
        # Place each label in a distinct voxel
        x = i % shape[0]
        y = (i // shape[0]) % shape[1]
        z = (i // (shape[0] * shape[1])) % shape[2]
        data[x, y, z] = idx
    affine = np.eye(4)
    return nib.Nifti1Image(data, affine)


def _make_scalar_nii(shape: tuple, seed: int = 0) -> nib.Nifti1Image:
    """Create a small NIfTI scalar map with random float data."""
    rng = np.random.default_rng(seed)
    data = rng.uniform(0.1, 1.0, shape).astype(np.float32)
    affine = np.eye(4)
    return nib.Nifti1Image(data, affine)


def _write_dseg_txt(path: Path, labels: dict[int, str]) -> None:
    """Write a dseg.txt label file (tab-separated index→label)."""
    with open(path, "w") as f:
        for idx in sorted(labels):
            f.write(f"{idx}\t{labels[idx]}\n")


@pytest.fixture
def mock_freesurfer_dir(tmp_path: Path) -> Path:
    """Create a minimal mock FreeSurfer subject directory with valid binary files."""
    fs_dir = tmp_path / "freesurfer"
    (fs_dir / "surf").mkdir(parents=True)
    (fs_dir / "label").mkdir(parents=True)
    (fs_dir / "stats").mkdir(parents=True)

    rng = np.random.default_rng(42)

    # --- stats/aseg.stats ---
    aseg_stats = (
        "# Title Segmentation Statistics\n"
        "#\n"
        "# Measure BrainSeg, BrainSegVol, Brain Segmentation Volume, 1234567.0, mm^3\n"
        "# Measure BrainSegNotVent, BrainSegVolNotVent, Brain Segmentation Volume Without Ventricles, 1200000.0, mm^3\n"
        "# Measure lhCortex, lhCortexVol, Left hemisphere cortical gray matter volume, 250000.0, mm^3\n"
        "# Measure rhCortex, rhCortexVol, Right hemisphere cortical gray matter volume, 248000.0, mm^3\n"
        "# Measure SubCortGray, SubCortGrayVol, Subcortical gray matter volume, 60000.0, mm^3\n"
        "# Measure WM, WMVol, White matter volume, 480000.0, mm^3\n"
        "# Measure Mask, MaskVol, Mask Volume, 1500000.0, mm^3\n"
        "# Measure EstimatedTotalIntraCranialVol, eTIV, Estimated Total Intracranial Volume, 1600000.0, mm^3\n"
        "# ColHeaders  Index SegId NVoxels Volume_mm3 StructName normMean normStdDev normMin normMax normRange\n"
        "  1  4     5234  5234.0  Left-Lateral-Ventricle       26.52   9.46   0.00  86.00  86.00\n"
        "  2 28     3517  3517.0  Left-Accumbens-area          91.21   6.12  59.00 107.00  48.00\n"
        "  3  5     3100  3100.0  Right-Lateral-Ventricle      25.80   9.10   0.00  84.00  84.00\n"
    )
    (fs_dir / "stats" / "aseg.stats").write_text(aseg_stats)

    # --- stats/lh.aparc.stats and rh.aparc.stats (Desikan) ---
    # Real format: # ColHeaders StructName NumVert SurfArea GrayVol ThickAvg ThickStd MeanCurv ...
    for hemi in ("lh", "rh"):
        aparc_stats = (
            "# Table of FreeSurfer cortical parcellation anatomical statistics\n"
            "#\n"
            "# ColHeaders StructName NumVert SurfArea GrayVol ThickAvg ThickStd MeanCurv GausCurv FoldInd CurvInd\n"
            "superiorfrontal                         12139   8429  26217  2.862  0.518  0.116  0.021  111  10.9\n"
            "middlefrontal                            5432   3210  12000  2.650  0.490  0.110  0.020   80   8.0\n"
            "precentral                               8100   5500  18000  2.750  0.510  0.115  0.022   95   9.5\n"
        )
        (fs_dir / "stats" / f"{hemi}.aparc.stats").write_text(aparc_stats)

    # --- surface annotation files (Desikan = aparc) ---
    for hemi in ("lh", "rh"):
        _write_annot(
            fs_dir / "label" / f"{hemi}.aparc.annot",
            MOCK_LABELS.copy(),
            MOCK_CTAB.copy(),
            MOCK_REGION_NAMES,
        )

    # --- per-vertex metric files ---
    surf_files = {
        "thickness": rng.uniform(1.5, 4.5, N_VERTICES).astype(np.float32),
        "area": rng.uniform(0.5, 3.0, N_VERTICES).astype(np.float32),
        "curv": rng.uniform(-0.5, 0.5, N_VERTICES).astype(np.float32),
        "sulc": rng.uniform(-5.0, 5.0, N_VERTICES).astype(np.float32),
    }
    for hemi in ("lh", "rh"):
        for surf_name, data in surf_files.items():
            _write_morph(fs_dir / "surf" / f"{hemi}.{surf_name}", data)

    # --- stats/tian-s1.subcortical.stats (volumetric atlas with proper names) ---
    tian_stats = (
        "# Title Segmentation Statistics\n"
        "#\n"
        "# generating_program mri_segstats\n"
        "# Measure EstimatedTotalIntraCranialVol, eTIV, Estimated Total Intracranial Volume, 1600000.0, mm^3\n"
        "# ColHeaders  Index SegId NVoxels Volume_mm3 StructName Mean StdDev Min Max Range\n"
        "  1   1      5974     5974.0  HIP-rh    87.82   16.47    9.00   110.00   101.00\n"
        "  2   2      3238     3238.0  AMY-rh    80.35   25.16   17.00   108.00    91.00\n"
        "  3   3      6042     6042.0  HIP-lh    84.53   18.16   13.00   108.00    95.00\n"
        "  4   4      3228     3228.0  AMY-lh    79.40   20.74   18.00   110.00    92.00\n"
    )
    (fs_dir / "stats" / "tian-s1.subcortical.stats").write_text(tian_stats)

    # --- stats/badatlas.subcortical.stats (generic Seg names — no ctab) ---
    bad_stats = (
        "# Title Segmentation Statistics\n"
        "#\n"
        "# ColHeaders  Index SegId NVoxels Volume_mm3 StructName Mean StdDev Min Max Range\n"
        "  1   1      5974     5974.0  Seg0001    87.82   16.47    9.00   110.00   101.00\n"
        "  2   2      3238     3238.0  Seg0002    80.35   25.16   17.00   108.00    91.00\n"
    )
    (fs_dir / "stats" / "badatlas.subcortical.stats").write_text(bad_stats)

    return fs_dir


@pytest.fixture
def mock_freesurfer_dir_with_schaefer(mock_freesurfer_dir: Path) -> Path:
    """Extend mock FreeSurfer dir with Schaefer stats files (schaefer100-7 format)."""
    stats_dir = mock_freesurfer_dir / "stats"
    for hemi in ("lh", "rh"):
        hemi_prefix = "LH" if hemi == "lh" else "RH"
        schaefer_stats = (
            "# Table of FreeSurfer cortical parcellation anatomical statistics\n"
            "#\n"
            f"# ColHeaders StructName NumVert SurfArea GrayVol ThickAvg ThickStd MeanCurv GausCurv FoldInd CurvInd\n"
            f"7Networks_{hemi_prefix}_Vis_1   713   471  1527  2.925  0.457  0.118  0.030   9  0.7\n"
            f"7Networks_{hemi_prefix}_Vis_2  1082   705  1774  2.696  0.453  0.097  0.015   7  0.7\n"
            f"7Networks_{hemi_prefix}_SomMot_1   900   600  1800  2.800  0.470  0.112  0.025   8  0.8\n"
        )
        (stats_dir / f"{hemi}.schaefer100-7.stats").write_text(schaefer_stats)
    return mock_freesurfer_dir


@pytest.fixture
def mock_qsirecon_root_dir(tmp_path: Path) -> Path:
    """Create a mock QSIRecon root directory with proper layout.

    Layout mirrors real QSIRecon derivatives:
      qsirecon/
        sub-001/ses-test/dwi/
          *_seg-4S156Parcels_dseg.nii.gz   ← atlas segmentation
          *_seg-4S156Parcels_dseg.txt       ← label file
        derivatives/
          qsirecon-DIPYDKI/sub-001/ses-test/dwi/
            *_model-dkimicro_param-fa_dwimap.nii.gz
            *_model-dkimicro_param-md_dwimap.nii.gz
          qsirecon-MRtrix3_act-HSVS/sub-001/ses-test/dwi/
            *_connectivity.mat
    """
    qsi_root = tmp_path / "qsirecon"
    subject = "sub-001"
    session = "ses-test"
    prefix = f"{subject}_{session}"

    # Atlas segmentation in main subject dir
    seg_dwi = qsi_root / subject / session / "dwi"
    seg_dwi.mkdir(parents=True)

    atlas_img = _make_atlas_nii(MOCK_QSI_ATLAS_SHAPE, MOCK_QSI_LABELS)
    nib.save(atlas_img, str(seg_dwi / f"{prefix}_space-ACPC_seg-4S156Parcels_dseg.nii.gz"))
    _write_dseg_txt(seg_dwi / f"{prefix}_space-ACPC_seg-4S156Parcels_dseg.txt", MOCK_QSI_LABELS)

    # DKI scalar maps
    dki_dwi = qsi_root / "derivatives" / "qsirecon-DIPYDKI" / subject / session / "dwi"
    dki_dwi.mkdir(parents=True)

    for param in ("fa", "md"):
        scalar_img = _make_scalar_nii(MOCK_QSI_ATLAS_SHAPE, seed=hash(param) % 100)
        nib.save(
            scalar_img,
            str(dki_dwi / f"{prefix}_space-ACPC_model-dkimicro_param-{param}_dwimap.nii.gz"),
        )

    # MRtrix3 connectivity .mat file
    mrtrix_dwi = (
        qsi_root / "derivatives" / "qsirecon-MRtrix3_act-HSVS" / subject / session / "dwi"
    )
    mrtrix_dwi.mkdir(parents=True)

    n_parcels = len(MOCK_QSI_LABELS)
    rng = np.random.default_rng(99)
    raw_conn = rng.integers(0, 100, size=(n_parcels, n_parcels)).astype(np.float64)
    # Make symmetric
    sift2_matrix = (raw_conn + raw_conn.T) / 2.0
    np.fill_diagonal(sift2_matrix, 0)

    scipy.io.savemat(
        str(mrtrix_dwi / f"{prefix}_space-ACPC_connectivity.mat"),
        {"sift2": sift2_matrix},
    )

    return qsi_root


@pytest.fixture
def mock_qsirecon_combined_dir(tmp_path: Path) -> Path:
    """Create a mock QSIRecon root with a combined Schaefer100+TianS1 atlas.

    Layout mirrors real QSIRecon derivatives for the schaefer100x7_tian_s1
    combined atlas (seg name: Schaefer2018N100n7Tian2020S1):
      qsirecon/
        sub-001/ses-test/dwi/
          *_seg-Schaefer2018N100n7Tian2020S1_dseg.nii.gz
          *_seg-Schaefer2018N100n7Tian2020S1_dseg.txt
        derivatives/
          qsirecon-DIPYDKI/sub-001/ses-test/dwi/
            *_model-dkimicro_param-fa_dwimap.nii.gz
          qsirecon-MRtrix3_act-HSVS/sub-001/ses-test/dwi/
            *_connectivity.mat   (6×6 matrix for 6 combined labels)
    """
    qsi_root = tmp_path / "qsirecon_combined"
    subject = "sub-001"
    session = "ses-test"
    prefix = f"{subject}_{session}"
    seg_name = "Schaefer2018N100n7Tian2020S1"

    seg_dwi = qsi_root / subject / session / "dwi"
    seg_dwi.mkdir(parents=True)

    atlas_img = _make_atlas_nii(MOCK_QSI_ATLAS_SHAPE, MOCK_COMBINED_LABELS)
    nib.save(atlas_img, str(seg_dwi / f"{prefix}_space-ACPC_seg-{seg_name}_dseg.nii.gz"))
    _write_dseg_txt(seg_dwi / f"{prefix}_space-ACPC_seg-{seg_name}_dseg.txt", MOCK_COMBINED_LABELS)

    # DKI scalar maps
    dki_dwi = qsi_root / "derivatives" / "qsirecon-DIPYDKI" / subject / session / "dwi"
    dki_dwi.mkdir(parents=True)
    scalar_img = _make_scalar_nii(MOCK_QSI_ATLAS_SHAPE, seed=7)
    nib.save(scalar_img, str(dki_dwi / f"{prefix}_space-ACPC_model-dkimicro_param-fa_dwimap.nii.gz"))

    # MRtrix3 connectivity .mat file — 6×6 (all combined labels)
    mrtrix_dwi = (
        qsi_root / "derivatives" / "qsirecon-MRtrix3_act-HSVS" / subject / session / "dwi"
    )
    mrtrix_dwi.mkdir(parents=True)
    n = len(MOCK_COMBINED_LABELS)
    rng = np.random.default_rng(42)
    raw = rng.integers(0, 100, size=(n, n)).astype(np.float64)
    sift2 = (raw + raw.T) / 2.0
    np.fill_diagonal(sift2, 0)
    scipy.io.savemat(str(mrtrix_dwi / f"{prefix}_space-ACPC_connectivity.mat"), {"sift2": sift2})

    return qsi_root


@pytest.fixture
def mock_qsirecon_dir(tmp_path: Path) -> Path:
    """Create a minimal mock QSIRecon session directory (legacy fixture for old tests)."""
    qsi_dir = tmp_path / "qsirecon"
    dwi_dir = qsi_dir / "dwi"
    dwi_dir.mkdir(parents=True)

    parc_content = (
        "label\tregion_label\tmean\tstd\tmedian\tn_voxels\n"
        "1\tLH_Vis_1\t0.45\t0.05\t0.44\t120\n"
        "2\tLH_Vis_2\t0.47\t0.04\t0.46\t115\n"
    )
    (
        dwi_dir
        / "sub-001_ses-test_space-T1w_atlas-Schaefer400x7_model-DTI_param-FA_desc-preproc_parc.tsv"
    ).write_text(parc_content)

    conn_content = "LH_Vis_1,LH_Vis_2\n0,150\n150,0\n"
    (
        dwi_dir
        / "sub-001_ses-test_space-T1w_atlas-Schaefer400x7_desc-sift2_connectivity.csv"
    ).write_text(conn_content)

    return qsi_dir


@pytest.fixture
def mock_extract_dir(tmp_path: Path) -> Path:
    """Create a mock brainbank-extract output directory with three sessions."""
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

        status = {
            "subject": subject,
            "session": session,
            "extraction_date": "2026-03-08T12:00:00",
            "brainbank_extract_version": "0.1.0",
            "atlases_extracted": ["desikan"],
            "atlases_skipped": [],
            "modalities": {
                "anat": {"status": "complete", "n_files": 5},
                "dwi_scalars": {"status": "complete", "n_files": 1},
                "dwi_connectivity": {"status": "complete", "n_files": 1},
                "dwi_tractprofiles": {"status": "skipped", "reason": "no pyAFQ outputs"},
            },
            "warnings": [],
        }
        (session_dir / "_status.json").write_text(json.dumps(status, indent=2))

    return extract_dir


# ---------------------------------------------------------------------------
# Aggregator fixtures: extract dirs populated with real output files
# ---------------------------------------------------------------------------

_SESSIONS = [
    ("sub-001", "ses-20240101"),
    ("sub-001", "ses-20240601"),
    ("sub-002", "ses-20240101"),
]

_ANAT_REGIONS = [
    {"region_index": 1, "region_label": "superiorfrontal", "hemisphere": "L"},
    {"region_index": 2, "region_label": "middlefrontal", "hemisphere": "L"},
    {"region_index": 3, "region_label": "precentral", "hemisphere": "R"},
]

_SCALAR_REGIONS = [
    {"region_index": 1, "region_label": "LH_Vis_1", "hemisphere": "L"},
    {"region_index": 2, "region_label": "LH_Vis_2", "hemisphere": "L"},
    {"region_index": 3, "region_label": "RH_Vis_1", "hemisphere": "R"},
    {"region_index": 4, "region_label": "RH_Vis_2", "hemisphere": "R"},
]

_CONN_LABELS = ["LH_Vis_1", "LH_Vis_2", "RH_Vis_1", "RH_Vis_2", "HIP-lh", "HIP-rh"]


def _write_session_status(session_dir: Path, subject: str, session: str) -> None:
    session_dir.mkdir(parents=True, exist_ok=True)
    status = {
        "subject": subject,
        "session": session,
        "extraction_date": "2026-03-08T12:00:00",
        "brainbank_extract_version": "0.1.0",
        "atlases_extracted": ["desikan"],
        "atlases_skipped": [],
        "modalities": {"anat": {"status": "complete", "n_files": 5}},
        "warnings": [],
    }
    (session_dir / "_status.json").write_text(json.dumps(status, indent=2))


@pytest.fixture
def mock_extract_dir_with_anat(tmp_path: Path) -> Path:
    """Extract dir with populated anat TSV files for 3 sessions."""
    extract_dir = tmp_path / "brainbank-extract"
    rng = np.random.default_rng(0)

    for subject, session in _SESSIONS:
        prefix = f"{subject}_{session}"
        session_dir = extract_dir / subject / session
        anat_dir = session_dir / "anat"
        anat_dir.mkdir(parents=True)
        _write_session_status(session_dir, subject, session)

        # Global metrics
        global_rows = [
            {"metric": "eTIV", "value": float(rng.uniform(1.4e6, 1.6e6)), "source": "freesurfer"},
            {"metric": "BrainSegVol", "value": float(rng.uniform(1.1e6, 1.3e6)), "source": "freesurfer"},
            {"metric": "lhCortexVol", "value": float(rng.uniform(2.4e5, 2.6e5)), "source": "freesurfer"},
        ]
        import pandas as pd
        pd.DataFrame(global_rows).to_csv(
            anat_dir / f"{prefix}_desc-globalmetrics_morph.tsv", sep="\t", index=False
        )

        # Desikan thickness + area
        atlas_dir = anat_dir / "atlas-desikan"
        atlas_dir.mkdir(parents=True)
        for metric in ("thickness", "area"):
            rows = [
                {**r, "value": float(rng.uniform(1.5, 4.0)), "metric": metric}
                for r in _ANAT_REGIONS
            ]
            pd.DataFrame(rows).to_csv(
                atlas_dir / f"{prefix}_atlas-desikan_desc-{metric}_morph.tsv",
                sep="\t", index=False,
            )

    return extract_dir


@pytest.fixture
def mock_extract_dir_with_dwi_scalars(tmp_path: Path) -> Path:
    """Extract dir with populated scalar TSV files for 3 sessions."""
    extract_dir = tmp_path / "brainbank-extract"
    rng = np.random.default_rng(1)

    for subject, session in _SESSIONS:
        prefix = f"{subject}_{session}"
        session_dir = extract_dir / subject / session
        _write_session_status(session_dir, subject, session)

        out_dir = (
            session_dir / "dwi" / "scalars"
            / "pipeline-DIPYDKI" / "atlas-schaefer100x7"
        )
        out_dir.mkdir(parents=True)

        import pandas as pd
        rows = [
            {
                **r,
                "mean": float(rng.uniform(0.3, 0.7)),
                "std": float(rng.uniform(0.01, 0.1)),
                "median": float(rng.uniform(0.3, 0.7)),
                "n_voxels": int(rng.integers(50, 200)),
                "model": "dkimicro",
                "param": "fa",
                "pipeline": "DIPYDKI",
            }
            for r in _SCALAR_REGIONS
        ]
        fname = (
            f"{prefix}_atlas-schaefer100x7_pipeline-DIPYDKI"
            f"_model-dkimicro_param-fa_desc-parcellated_diffmetrics.tsv"
        )
        pd.DataFrame(rows).to_csv(out_dir / fname, sep="\t", index=False)

    return extract_dir


@pytest.fixture
def mock_extract_dir_with_connectivity(tmp_path: Path) -> Path:
    """Extract dir with populated connectivity .npy + labels JSON for 3 sessions."""
    extract_dir = tmp_path / "brainbank-extract"
    rng = np.random.default_rng(2)
    n = len(_CONN_LABELS)

    for subject, session in _SESSIONS:
        prefix = f"{subject}_{session}"
        session_dir = extract_dir / subject / session
        _write_session_status(session_dir, subject, session)

        out_dir = (
            session_dir / "dwi" / "connectivity"
            / "pipeline-MRtrix3_act-HSVS" / "atlas-schaefer100x7_tian_s1"
        )
        out_dir.mkdir(parents=True)

        raw = rng.integers(0, 100, size=(n, n)).astype(np.float64)
        matrix = (raw + raw.T) / 2.0
        np.fill_diagonal(matrix, 0)

        base = (
            f"{prefix}_atlas-schaefer100x7_tian_s1"
            f"_pipeline-MRtrix3_act-HSVS_desc-sift2_connmatrix"
        )
        np.save(str(out_dir / f"{base}.npy"), matrix)
        (out_dir / f"{base}-labels.json").write_text(json.dumps(_CONN_LABELS, indent=2))

    return extract_dir
