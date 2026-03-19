"""Tests for the QSIRecon extractor."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from brainbank_extract.extractors.qsirecon import QSIReconExtractor
from tests.conftest import (
    MOCK_COMBINED_CORTICAL_LABELS,
    MOCK_COMBINED_LABELS,
    MOCK_COMBINED_SUBCORTICAL_LABELS,
    MOCK_QSI_LABELS,
)


def _make_extractor(
    qsi_root: Path,
    out_dir: Path,
    atlases: list[str] | None = None,
    subject: str = "sub-001",
    session: str = "ses-test",
) -> QSIReconExtractor:
    return QSIReconExtractor(
        qsirecon_dir=qsi_root,
        output_dir=out_dir,
        subject=subject,
        session=session,
        atlases=atlases or ["4S156Parcels"],
    )


# ---------------------------------------------------------------------------
# Scalar extraction
# ---------------------------------------------------------------------------

def test_extract_scalars_returns_list(mock_qsirecon_root_dir: Path, tmp_path: Path) -> None:
    """extract_scalars() returns a non-empty list of DataFrames."""
    ext = _make_extractor(mock_qsirecon_root_dir, tmp_path / "out")
    dfs = ext.extract_scalars(atlas="4S156Parcels")
    assert isinstance(dfs, list)
    assert len(dfs) > 0


def test_extract_scalars_columns(mock_qsirecon_root_dir: Path, tmp_path: Path) -> None:
    """Scalar DataFrames have expected output columns."""
    ext = _make_extractor(mock_qsirecon_root_dir, tmp_path / "out")
    dfs = ext.extract_scalars(atlas="4S156Parcels")
    for df in dfs:
        for col in ("region_index", "region_label", "hemisphere", "mean", "std", "median", "n_voxels"):
            assert col in df.columns, f"Column {col!r} missing"


def test_extract_scalars_parcels_match_atlas(mock_qsirecon_root_dir: Path, tmp_path: Path) -> None:
    """Scalar extraction returns one row per non-empty parcel."""
    ext = _make_extractor(mock_qsirecon_root_dir, tmp_path / "out")
    dfs = ext.extract_scalars(atlas="4S156Parcels")
    assert len(dfs) > 0
    df = dfs[0]
    # Should have entries for atlas parcels that have voxels
    assert len(df) > 0
    assert set(df["region_label"]).issubset(set(MOCK_QSI_LABELS.values()))


def test_extract_scalars_hemisphere_assigned(mock_qsirecon_root_dir: Path, tmp_path: Path) -> None:
    """Hemisphere labels are assigned correctly from region label names."""
    ext = _make_extractor(mock_qsirecon_root_dir, tmp_path / "out")
    dfs = ext.extract_scalars(atlas="4S156Parcels")
    df = dfs[0]
    lh_rows = df[df["hemisphere"] == "L"]
    rh_rows = df[df["hemisphere"] == "R"]
    assert len(lh_rows) > 0
    assert len(rh_rows) > 0
    assert all("LH_" in r for r in lh_rows["region_label"])
    assert all("RH_" in r for r in rh_rows["region_label"])


def test_extract_scalars_two_params(mock_qsirecon_root_dir: Path, tmp_path: Path) -> None:
    """extract_scalars() returns separate DataFrames for FA and MD."""
    ext = _make_extractor(mock_qsirecon_root_dir, tmp_path / "out")
    dfs = ext.extract_scalars(atlas="4S156Parcels")
    params = {df["param"].iloc[0] for df in dfs}
    assert "fa" in params
    assert "md" in params


def test_extract_scalars_missing_atlas_raises(mock_qsirecon_root_dir: Path, tmp_path: Path) -> None:
    """FileNotFoundError when atlas segmentation NII is missing."""
    ext = _make_extractor(mock_qsirecon_root_dir, tmp_path / "out", atlases=["4S456Parcels"])
    with pytest.raises(FileNotFoundError):
        ext.extract_scalars(atlas="4S456Parcels")


# ---------------------------------------------------------------------------
# Connectivity extraction
# ---------------------------------------------------------------------------

def test_extract_connectivity_returns_matrix_and_labels(
    mock_qsirecon_root_dir: Path, tmp_path: Path
) -> None:
    """extract_connectivity() returns a 2D numpy array and list of labels."""
    ext = _make_extractor(mock_qsirecon_root_dir, tmp_path / "out")
    matrix, labels, combined_key, pipeline = ext.extract_connectivity(atlas="4S156Parcels", measure="sift2")

    assert isinstance(matrix, np.ndarray)
    assert matrix.ndim == 2
    assert matrix.shape[0] == matrix.shape[1]
    assert isinstance(labels, list)
    assert len(labels) == matrix.shape[0]
    assert combined_key == "4S156Parcels"
    assert pipeline == "MRtrix3_act-HSVS"


def test_extract_connectivity_symmetric(mock_qsirecon_root_dir: Path, tmp_path: Path) -> None:
    """Connectivity matrix is symmetric."""
    ext = _make_extractor(mock_qsirecon_root_dir, tmp_path / "out")
    matrix, _, _key, _pipeline = ext.extract_connectivity(atlas="4S156Parcels", measure="sift2")
    assert np.allclose(matrix, matrix.T)


def test_extract_connectivity_labels_match_atlas(
    mock_qsirecon_root_dir: Path, tmp_path: Path
) -> None:
    """Connectivity labels match the atlas label file."""
    ext = _make_extractor(mock_qsirecon_root_dir, tmp_path / "out")
    matrix, labels, _key, _pipeline = ext.extract_connectivity(atlas="4S156Parcels", measure="sift2")
    expected_labels = [MOCK_QSI_LABELS[i] for i in sorted(MOCK_QSI_LABELS)]
    assert labels == expected_labels


def test_extract_connectivity_no_mat_raises(tmp_path: Path) -> None:
    """FileNotFoundError when no connectivity .mat file is found."""
    qsi_root = tmp_path / "qsirecon"
    (qsi_root / "sub-001" / "ses-test" / "dwi").mkdir(parents=True)
    ext = _make_extractor(qsi_root, tmp_path / "out")
    with pytest.raises(FileNotFoundError):
        ext.extract_connectivity(atlas="4S156Parcels", measure="sift2")


# ---------------------------------------------------------------------------
# Tract profiles
# ---------------------------------------------------------------------------

def test_extract_tract_profiles_absent(
    mock_qsirecon_root_dir: Path, tmp_path: Path
) -> None:
    """Tract profile extraction returns empty list when pyAFQ outputs absent."""
    ext = _make_extractor(mock_qsirecon_root_dir, tmp_path / "out")
    profiles = ext.extract_tract_profiles()
    assert profiles == []


# ---------------------------------------------------------------------------
# Full extract() orchestration
# ---------------------------------------------------------------------------

def test_extract_creates_output_structure(mock_qsirecon_root_dir: Path, tmp_path: Path) -> None:
    """extract() creates dwi/scalars/ and dwi/connectivity/ directories."""
    out_dir = tmp_path / "out"
    ext = _make_extractor(mock_qsirecon_root_dir, out_dir)
    status = ext.extract()

    assert (out_dir / "dwi" / "scalars").exists()
    assert (out_dir / "dwi" / "connectivity").exists()
    assert (out_dir / "_status.json").exists()


def test_extract_writes_scalar_tsvs(mock_qsirecon_root_dir: Path, tmp_path: Path) -> None:
    """extract() writes parcellated scalar TSV files."""
    out_dir = tmp_path / "out"
    ext = _make_extractor(mock_qsirecon_root_dir, out_dir)
    status = ext.extract()

    scalar_files = list((out_dir / "dwi" / "scalars").rglob("*.tsv"))
    assert len(scalar_files) > 0
    assert status["modalities"]["dwi_scalars"]["n_files"] > 0
    # Verify pipeline entity appears in filenames
    assert all("pipeline-" in f.name for f in scalar_files)


def test_extract_writes_connectivity_npy(mock_qsirecon_root_dir: Path, tmp_path: Path) -> None:
    """extract() writes connectivity .npy files."""
    out_dir = tmp_path / "out"
    ext = _make_extractor(mock_qsirecon_root_dir, out_dir)
    status = ext.extract()

    conn_files = list((out_dir / "dwi" / "connectivity").rglob("*.npy"))
    assert len(conn_files) > 0
    assert status["modalities"]["dwi_connectivity"]["n_files"] > 0
    # Verify pipeline entity appears in filenames
    assert all("pipeline-" in f.name for f in conn_files)


def test_extract_writes_connectivity_labels_json(mock_qsirecon_root_dir: Path, tmp_path: Path) -> None:
    """extract() writes companion labels JSON for connectivity matrices."""
    import json

    out_dir = tmp_path / "out"
    ext = _make_extractor(mock_qsirecon_root_dir, out_dir)
    ext.extract()

    label_files = list((out_dir / "dwi" / "connectivity").rglob("*-labels.json"))
    assert len(label_files) > 0
    labels = json.loads(label_files[0].read_text())
    assert isinstance(labels, list)
    assert len(labels) == len(MOCK_QSI_LABELS)


def test_extract_status_json_content(mock_qsirecon_root_dir: Path, tmp_path: Path) -> None:
    """_status.json contains expected fields."""
    import json

    out_dir = tmp_path / "out"
    ext = _make_extractor(mock_qsirecon_root_dir, out_dir)
    status = ext.extract()

    status_file = out_dir / "_status.json"
    loaded = json.loads(status_file.read_text())
    assert loaded["subject"] == "sub-001"
    assert loaded["session"] == "ses-test"
    assert "atlases_extracted" in loaded
    assert "4S156Parcels" in loaded["atlases_extracted"]


def test_extract_missing_qsirecon_dir(tmp_path: Path) -> None:
    """extract() returns error status when QSIRecon root dir does not exist."""
    out_dir = tmp_path / "out"
    ext = _make_extractor(tmp_path / "nonexistent", out_dir)
    status = ext.extract()

    assert status["modalities"]["dwi_scalars"]["status"] == "error"
    assert len(status["warnings"]) > 0


# ---------------------------------------------------------------------------
# Combined atlas: component atlas extraction (Schaefer100 + TianS1)
# ---------------------------------------------------------------------------

def _make_combined_extractor(
    qsi_root: Path,
    out_dir: Path,
    atlases: list[str],
) -> QSIReconExtractor:
    return QSIReconExtractor(
        qsirecon_dir=qsi_root,
        output_dir=out_dir,
        subject="sub-001",
        session="ses-test",
        atlases=atlases,
    )


def test_schaefer_scalars_filtered_to_cortical(
    mock_qsirecon_combined_dir: Path, tmp_path: Path
) -> None:
    """extract_scalars for schaefer100x7 returns only LH_/RH_ labeled parcels."""
    ext = _make_combined_extractor(mock_qsirecon_combined_dir, tmp_path / "out", ["schaefer100x7"])
    dfs = ext.extract_scalars(atlas="schaefer100x7")

    assert len(dfs) > 0
    df = dfs[0]
    returned_labels = set(df["region_label"])
    expected_cortical = set(MOCK_COMBINED_CORTICAL_LABELS.values())
    assert returned_labels == expected_cortical
    assert returned_labels.isdisjoint(set(MOCK_COMBINED_SUBCORTICAL_LABELS.values()))


def test_tian_s1_scalars_filtered_to_subcortical(
    mock_qsirecon_combined_dir: Path, tmp_path: Path
) -> None:
    """extract_scalars for tian_s1 returns only subcortical (non-LH_/RH_) labeled parcels."""
    ext = _make_combined_extractor(mock_qsirecon_combined_dir, tmp_path / "out", ["tian_s1"])
    dfs = ext.extract_scalars(atlas="tian_s1")

    assert len(dfs) > 0
    df = dfs[0]
    returned_labels = set(df["region_label"])
    expected_subcortical = set(MOCK_COMBINED_SUBCORTICAL_LABELS.values())
    assert returned_labels == expected_subcortical
    assert returned_labels.isdisjoint(set(MOCK_COMBINED_CORTICAL_LABELS.values()))


def test_schaefer_scalar_output_named_with_component_key(
    mock_qsirecon_combined_dir: Path, tmp_path: Path
) -> None:
    """Scalar TSV files are named with the component atlas key, not the combined key."""
    out_dir = tmp_path / "out"
    ext = _make_combined_extractor(mock_qsirecon_combined_dir, out_dir, ["schaefer100x7"])
    ext.extract()

    scalar_files = list((out_dir / "dwi" / "scalars").rglob("*.tsv"))
    assert any("atlas-schaefer100x7_" in f.name for f in scalar_files)
    assert not any("tian_s1" in f.name for f in scalar_files)


def test_connectivity_written_under_combined_key(
    mock_qsirecon_combined_dir: Path, tmp_path: Path
) -> None:
    """Connectivity matrix is written under the combined atlas key, not component key."""
    out_dir = tmp_path / "out"
    ext = _make_combined_extractor(mock_qsirecon_combined_dir, out_dir, ["schaefer100x7"])
    ext.extract()

    conn_files = list((out_dir / "dwi" / "connectivity").rglob("*.npy"))
    assert len(conn_files) > 0
    # File must carry the full combined key (both cortical and subcortical components)
    assert all("schaefer100x7_tian_s1" in f.name for f in conn_files)
    # Must NOT omit the tian component (i.e. not end the atlas entity at "schaefer100x7_pipeline-")
    assert not any("atlas-schaefer100x7_pipeline-" in f.name for f in conn_files)


def test_connectivity_full_combined_size(
    mock_qsirecon_combined_dir: Path, tmp_path: Path
) -> None:
    """Connectivity matrix has shape matching the full combined atlas (not just the component)."""
    out_dir = tmp_path / "out"
    ext = _make_combined_extractor(mock_qsirecon_combined_dir, out_dir, ["schaefer100x7"])
    ext.extract()

    npy_files = list((out_dir / "dwi" / "connectivity").rglob("*.npy"))
    assert len(npy_files) > 0
    mat = np.load(str(npy_files[0]))
    # Full combined atlas has 6 parcels (4 cortical + 2 subcortical)
    assert mat.shape == (len(MOCK_COMBINED_LABELS), len(MOCK_COMBINED_LABELS))


def test_connectivity_not_duplicated_for_shared_combined_atlas(
    mock_qsirecon_combined_dir: Path, tmp_path: Path
) -> None:
    """Connectivity matrix is written once even when both component atlases are requested."""
    out_dir = tmp_path / "out"
    # Both schaefer100x7 and tian_s1 share schaefer100x7_tian_s1 combined atlas
    ext = _make_combined_extractor(
        mock_qsirecon_combined_dir, out_dir, ["schaefer100x7", "tian_s1"]
    )
    ext.extract()

    npy_files = list((out_dir / "dwi" / "connectivity").rglob("*.npy"))
    # Should be exactly one .npy per measure (not two copies of the same matrix)
    npy_stems = [f.stem for f in npy_files]
    assert len(npy_stems) == len(set(npy_stems)), "Duplicate connectivity files written"
