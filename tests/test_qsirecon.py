"""Tests for the QSIRecon extractor."""

from __future__ import annotations

from pathlib import Path

import pytest

from brainbank_extract.extractors.qsirecon import QSIReconExtractor


@pytest.mark.skip(reason="QSIReconExtractor not yet implemented")
def test_extract_scalars_dti_fa(mock_qsirecon_dir: Path, tmp_path: Path) -> None:
    """DTI FA parcellated TSV is discovered and standardized."""
    extractor = QSIReconExtractor(
        qsirecon_dir=mock_qsirecon_dir,
        output_dir=tmp_path / "out",
        subject="sub-001",
        session="ses-test",
        atlases=["schaefer400x7"],
    )
    dfs = extractor.extract_scalars(atlas="schaefer400x7")

    assert len(dfs) > 0
    df = dfs[0]
    assert "region_label" in df.columns
    assert "mean" in df.columns


@pytest.mark.skip(reason="QSIReconExtractor not yet implemented")
def test_extract_connectivity_sift2(mock_qsirecon_dir: Path, tmp_path: Path) -> None:
    """SIFT2 connectivity matrix is loaded and verified symmetric."""
    import numpy as np

    extractor = QSIReconExtractor(
        qsirecon_dir=mock_qsirecon_dir,
        output_dir=tmp_path / "out",
        subject="sub-001",
        session="ses-test",
        atlases=["schaefer400x7"],
    )
    matrix, labels = extractor.extract_connectivity(
        atlas="schaefer400x7", measure="sift2"
    )

    assert matrix.ndim == 2
    assert matrix.shape[0] == matrix.shape[1]
    assert np.allclose(matrix, matrix.T)
    assert len(labels) == matrix.shape[0]


@pytest.mark.skip(reason="QSIReconExtractor not yet implemented")
def test_extract_tract_profiles_absent(
    mock_qsirecon_dir: Path, tmp_path: Path
) -> None:
    """Tract profile extraction returns empty list when pyAFQ outputs absent."""
    extractor = QSIReconExtractor(
        qsirecon_dir=mock_qsirecon_dir,
        output_dir=tmp_path / "out",
        subject="sub-001",
        session="ses-test",
        atlases=["schaefer400x7"],
    )
    profiles = extractor.extract_tract_profiles()
    assert profiles == []


@pytest.mark.skip(reason="QSIReconExtractor not yet implemented")
def test_output_directory_structure(mock_qsirecon_dir: Path, tmp_path: Path) -> None:
    """Extraction creates expected dwi/ subdirectory structure."""
    out_dir = tmp_path / "out"
    extractor = QSIReconExtractor(
        qsirecon_dir=mock_qsirecon_dir,
        output_dir=out_dir,
        subject="sub-001",
        session="ses-test",
        atlases=["schaefer400x7"],
    )
    extractor.extract()

    assert (out_dir / "dwi" / "scalars").exists()
    assert (out_dir / "dwi" / "connectivity").exists()
