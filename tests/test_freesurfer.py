"""Tests for the FreeSurfer extractor."""

from __future__ import annotations

from pathlib import Path

import pytest

from brainbank_extract.extractors.freesurfer import FreeSurferExtractor


@pytest.mark.skip(reason="FreeSurferExtractor not yet implemented")
def test_extract_global_metrics(mock_freesurfer_dir: Path, tmp_path: Path) -> None:
    """Global metrics are parsed from aseg.stats header."""
    extractor = FreeSurferExtractor(
        freesurfer_dir=mock_freesurfer_dir,
        output_dir=tmp_path / "out",
        subject="sub-001",
        session="ses-test",
        atlases=["desikan"],
    )
    df = extractor.extract_global_metrics()

    assert "metric" in df.columns
    assert "value" in df.columns
    assert "source" in df.columns
    assert "eTIV" in df["metric"].values
    assert "BrainSegVol" in df["metric"].values


@pytest.mark.skip(reason="FreeSurferExtractor not yet implemented")
def test_extract_aseg(mock_freesurfer_dir: Path, tmp_path: Path) -> None:
    """Subcortical volumes are parsed from aseg.stats."""
    extractor = FreeSurferExtractor(
        freesurfer_dir=mock_freesurfer_dir,
        output_dir=tmp_path / "out",
        subject="sub-001",
        session="ses-test",
        atlases=["aseg"],
    )
    df = extractor.extract_aseg()

    assert "region_label" in df.columns
    assert "value" in df.columns
    assert len(df) > 0


@pytest.mark.skip(reason="FreeSurferExtractor not yet implemented")
def test_extract_surface_morphometrics_thickness(
    mock_freesurfer_dir: Path, tmp_path: Path
) -> None:
    """Surface morphometrics are extracted for a given atlas and metric."""
    extractor = FreeSurferExtractor(
        freesurfer_dir=mock_freesurfer_dir,
        output_dir=tmp_path / "out",
        subject="sub-001",
        session="ses-test",
        atlases=["desikan"],
    )
    df = extractor.extract_surface_morphometrics(atlas="desikan", metric="thickness")

    assert "region_label" in df.columns
    assert "hemisphere" in df.columns
    assert "value" in df.columns
    assert df["metric"].iloc[0] == "thickness"


@pytest.mark.skip(reason="FreeSurferExtractor not yet implemented")
def test_missing_atlas_is_skipped(mock_freesurfer_dir: Path, tmp_path: Path) -> None:
    """Missing atlas annotation files result in a warning, not an error."""
    extractor = FreeSurferExtractor(
        freesurfer_dir=mock_freesurfer_dir,
        output_dir=tmp_path / "out",
        subject="sub-001",
        session="ses-test",
        atlases=["schaefer400x7"],  # annotation not present in mock dir
    )
    status = extractor.extract()
    assert "schaefer400x7" in status["atlases_skipped"]


@pytest.mark.skip(reason="FreeSurferExtractor not yet implemented")
def test_output_files_written(mock_freesurfer_dir: Path, tmp_path: Path) -> None:
    """Extraction writes expected TSV files to output directory."""
    out_dir = tmp_path / "out"
    extractor = FreeSurferExtractor(
        freesurfer_dir=mock_freesurfer_dir,
        output_dir=out_dir,
        subject="sub-001",
        session="ses-test",
        atlases=["aseg"],
    )
    extractor.extract()

    anat_dir = out_dir / "anat"
    assert anat_dir.exists()
    tsv_files = list(anat_dir.glob("*.tsv"))
    assert len(tsv_files) > 0
