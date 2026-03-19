"""Tests for the FreeSurfer extractor."""

from __future__ import annotations

from pathlib import Path

import pytest

from brainbank_extract.extractors.freesurfer import (
    FreeSurferExtractor,
    _aseg_hemisphere,
    _infer_hemisphere,
    _parse_volumetric_stats_file,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_extractor(fs_dir: Path, out_dir: Path, atlases: list[str]) -> FreeSurferExtractor:
    return FreeSurferExtractor(
        freesurfer_dir=fs_dir,
        output_dir=out_dir,
        subject="sub-001",
        session="ses-test",
        atlases=atlases,
    )


# ---------------------------------------------------------------------------
# Global metrics
# ---------------------------------------------------------------------------

def test_extract_global_metrics_columns(mock_freesurfer_dir: Path, tmp_path: Path) -> None:
    """Global metrics DataFrame has expected columns."""
    ext = _make_extractor(mock_freesurfer_dir, tmp_path / "out", ["desikan"])
    df = ext.extract_global_metrics()
    assert list(df.columns) == ["metric", "value", "source"]


def test_extract_global_metrics_values(mock_freesurfer_dir: Path, tmp_path: Path) -> None:
    """Known metric values are parsed correctly."""
    ext = _make_extractor(mock_freesurfer_dir, tmp_path / "out", ["desikan"])
    df = ext.extract_global_metrics()
    row = df.set_index("metric")
    assert row.loc["eTIV", "value"] == pytest.approx(1_600_000.0)
    assert row.loc["BrainSegVol", "value"] == pytest.approx(1_234_567.0)
    assert (df["source"] == "freesurfer").all()


def test_extract_global_metrics_missing_stats(tmp_path: Path) -> None:
    """FileNotFoundError when aseg.stats does not exist."""
    ext = _make_extractor(tmp_path / "empty_fs", tmp_path / "out", ["desikan"])
    with pytest.raises(FileNotFoundError):
        ext.extract_global_metrics()


# ---------------------------------------------------------------------------
# aseg subcortical
# ---------------------------------------------------------------------------

def test_extract_aseg_columns(mock_freesurfer_dir: Path, tmp_path: Path) -> None:
    """aseg DataFrame has expected columns."""
    ext = _make_extractor(mock_freesurfer_dir, tmp_path / "out", ["aseg"])
    df = ext.extract_aseg()
    assert list(df.columns) == ["region_index", "region_label", "hemisphere", "value", "metric"]


def test_extract_aseg_rows(mock_freesurfer_dir: Path, tmp_path: Path) -> None:
    """aseg DataFrame has one row per structure in the stats file."""
    ext = _make_extractor(mock_freesurfer_dir, tmp_path / "out", ["aseg"])
    df = ext.extract_aseg()
    assert len(df) == 3
    assert "Left-Lateral-Ventricle" in df["region_label"].values
    assert (df["metric"] == "volume").all()


def test_extract_aseg_hemispheres(mock_freesurfer_dir: Path, tmp_path: Path) -> None:
    """aseg hemisphere labels are inferred correctly."""
    ext = _make_extractor(mock_freesurfer_dir, tmp_path / "out", ["aseg"])
    df = ext.extract_aseg().set_index("region_label")
    assert df.loc["Left-Lateral-Ventricle", "hemisphere"] == "L"
    assert df.loc["Right-Lateral-Ventricle", "hemisphere"] == "R"


# ---------------------------------------------------------------------------
# Full extract() orchestration
# ---------------------------------------------------------------------------

def test_extract_creates_output_files(mock_freesurfer_dir: Path, tmp_path: Path) -> None:
    """extract() writes global metrics TSV and status JSON even when fsatlas not available."""
    out_dir = tmp_path / "out"
    ext = _make_extractor(mock_freesurfer_dir, out_dir, ["aseg"])
    status = ext.extract()

    anat_dir = out_dir / "anat"
    assert anat_dir.exists()

    # Global metrics TSV is always written at top level of anat/
    tsv_files = list(anat_dir.glob("*.tsv"))
    assert len(tsv_files) > 0

    assert (out_dir / "_status.json").exists()
    assert status["modalities"]["anat"]["n_files"] > 0


def test_extract_aseg_only(mock_freesurfer_dir: Path, tmp_path: Path) -> None:
    """extract() extracts aseg when requested."""
    out_dir = tmp_path / "out"
    ext = _make_extractor(mock_freesurfer_dir, out_dir, ["aseg"])
    status = ext.extract()

    assert "aseg" in status["atlases_extracted"]
    assert status["atlases_skipped"] == []


def test_extract_atlas_without_fsatlas_name_skipped(
    mock_freesurfer_dir: Path, tmp_path: Path
) -> None:
    """Atlas with no fsatlas_name in registry is reported as skipped."""
    out_dir = tmp_path / "out"
    # 4S156Parcels is a combined atlas with no fsatlas_name
    ext = _make_extractor(mock_freesurfer_dir, out_dir, ["4S156Parcels"])
    status = ext.extract()

    assert "4S156Parcels" in status["atlases_skipped"]
    assert len(status["warnings"]) > 0


def test_extract_fsatlas_failure_skips_atlas(
    mock_freesurfer_dir: Path, tmp_path: Path
) -> None:
    """When fsatlas fails (e.g. FreeSurfer not available), atlas is skipped with warning."""
    out_dir = tmp_path / "out"
    # schaefer400x7 has fsatlas_name but FreeSurfer likely isn't available in test env
    ext = _make_extractor(mock_freesurfer_dir, out_dir, ["schaefer400x7"])
    status = ext.extract()

    # Atlas should be in skipped (not extracted) with a warning
    assert "schaefer400x7" in status["atlases_skipped"]
    assert len(status["warnings"]) > 0


def test_extract_missing_freesurfer_dir(tmp_path: Path) -> None:
    """extract() returns error status when FreeSurfer directory does not exist."""
    out_dir = tmp_path / "out"
    ext = _make_extractor(tmp_path / "nonexistent", out_dir, ["desikan"])
    status = ext.extract()

    assert status["modalities"]["anat"]["status"] == "error"
    assert len(status["warnings"]) > 0


# ---------------------------------------------------------------------------
# _aseg_hemisphere helper
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "name,expected",
    [
        ("Left-Lateral-Ventricle", "L"),
        ("Right-Putamen", "R"),
        ("Brain-Stem", "bilateral"),
        ("CC_Posterior", "bilateral"),
    ],
)
def test_aseg_hemisphere_inference(name: str, expected: str) -> None:
    assert _aseg_hemisphere(name) == expected


# ---------------------------------------------------------------------------
# _infer_hemisphere (unified helper)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "name,expected",
    [
        # aseg-style prefixes
        ("Left-Lateral-Ventricle", "L"),
        ("Right-Putamen", "R"),
        ("Brain-Stem", "bilateral"),
        # Tian-style suffixes
        ("HIP-rh", "R"),
        ("HIP-lh", "L"),
        ("AMY-rh", "R"),
        ("pTHA-lh", "L"),
        ("CAU-rh", "R"),
        # Other patterns
        ("lh_superiorfrontal", "L"),
        ("rh_superiorfrontal", "R"),
        ("CC_Posterior", "bilateral"),
    ],
)
def test_infer_hemisphere(name: str, expected: str) -> None:
    assert _infer_hemisphere(name) == expected


# ---------------------------------------------------------------------------
# _parse_volumetric_stats_file
# ---------------------------------------------------------------------------

def test_parse_volumetric_stats_with_proper_names(mock_freesurfer_dir: Path) -> None:
    """Stats file with real region names is parsed correctly."""
    stats_path = mock_freesurfer_dir / "stats" / "tian-s1.subcortical.stats"
    result = _parse_volumetric_stats_file(stats_path)

    assert result is not None
    assert "volume" in result
    df = result["volume"]
    assert list(df.columns) == ["region_index", "region_label", "hemisphere", "value", "metric"]
    assert len(df) == 4
    assert "HIP-rh" in df["region_label"].values
    assert "AMY-lh" in df["region_label"].values
    assert set(df["hemisphere"]) == {"L", "R"}


def test_parse_volumetric_stats_returns_none_for_generic_names(mock_freesurfer_dir: Path) -> None:
    """Stats file with Seg#### names returns None (needs regeneration)."""
    stats_path = mock_freesurfer_dir / "stats" / "badatlas.subcortical.stats"
    result = _parse_volumetric_stats_file(stats_path)
    assert result is None


def test_parse_volumetric_stats_correct_values(mock_freesurfer_dir: Path) -> None:
    """Parsed volumes match the stats file values."""
    stats_path = mock_freesurfer_dir / "stats" / "tian-s1.subcortical.stats"
    result = _parse_volumetric_stats_file(stats_path)
    df = result["volume"]
    hip_rh = df[df["region_label"] == "HIP-rh"]
    assert len(hip_rh) == 1
    assert hip_rh.iloc[0]["value"] == pytest.approx(5974.0)
    assert hip_rh.iloc[0]["hemisphere"] == "R"
    assert hip_rh.iloc[0]["region_index"] == 1
