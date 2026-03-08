"""Tests for the FreeSurfer extractor."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from brainbank_extract.extractors.freesurfer import FreeSurferExtractor, _aseg_hemisphere
from tests.conftest import MOCK_LABELS, MOCK_REGION_NAMES, N_VERTICES


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
# Surface stats (primary extraction path)
# ---------------------------------------------------------------------------

def test_extract_surface_stats_returns_dict(
    mock_freesurfer_dir_with_schaefer: Path, tmp_path: Path
) -> None:
    """extract_surface_stats() returns a dict of metric → DataFrame."""
    ext = _make_extractor(mock_freesurfer_dir_with_schaefer, tmp_path / "out", ["schaefer100x7"])
    result = ext.extract_surface_stats("schaefer100x7")
    assert isinstance(result, dict)
    assert len(result) > 0
    assert "thickness" in result
    assert "area" in result
    assert "volume" in result
    assert "curvature" in result


def test_extract_surface_stats_columns(
    mock_freesurfer_dir_with_schaefer: Path, tmp_path: Path
) -> None:
    """Each DataFrame in extract_surface_stats() has expected columns."""
    ext = _make_extractor(mock_freesurfer_dir_with_schaefer, tmp_path / "out", ["schaefer100x7"])
    result = ext.extract_surface_stats("schaefer100x7")
    for metric, df in result.items():
        assert list(df.columns) == [
            "region_index", "region_label", "hemisphere", "value", "metric"
        ], f"Wrong columns for metric {metric!r}"
        assert (df["metric"] == metric).all()


def test_extract_surface_stats_parcel_count(
    mock_freesurfer_dir_with_schaefer: Path, tmp_path: Path
) -> None:
    """extract_surface_stats() returns 3 parcels × 2 hemispheres = 6 rows per metric."""
    ext = _make_extractor(mock_freesurfer_dir_with_schaefer, tmp_path / "out", ["schaefer100x7"])
    result = ext.extract_surface_stats("schaefer100x7")
    # 3 parcels per hemi × 2 hemispheres = 6
    assert len(result["thickness"]) == 6


def test_extract_surface_stats_hemispheres(
    mock_freesurfer_dir_with_schaefer: Path, tmp_path: Path
) -> None:
    """Hemisphere labels are correctly assigned from lh/rh stats files."""
    ext = _make_extractor(mock_freesurfer_dir_with_schaefer, tmp_path / "out", ["schaefer100x7"])
    result = ext.extract_surface_stats("schaefer100x7")
    df = result["thickness"]
    assert set(df["hemisphere"].unique()) == {"L", "R"}


def test_extract_surface_stats_values_match(
    mock_freesurfer_dir_with_schaefer: Path, tmp_path: Path
) -> None:
    """Thickness values match those in the mock stats file."""
    ext = _make_extractor(mock_freesurfer_dir_with_schaefer, tmp_path / "out", ["schaefer100x7"])
    result = ext.extract_surface_stats("schaefer100x7")
    df = result["thickness"]
    # First LH parcel should have ThickAvg = 2.925
    lh_rows = df[df["hemisphere"] == "L"]
    first_row = lh_rows.iloc[0]
    assert first_row["value"] == pytest.approx(2.925)
    assert "LH_Vis_1" in first_row["region_label"]


def test_extract_surface_stats_missing_file(
    mock_freesurfer_dir: Path, tmp_path: Path
) -> None:
    """FileNotFoundError when stats file does not exist."""
    ext = _make_extractor(mock_freesurfer_dir, tmp_path / "out", ["schaefer100x7"])
    with pytest.raises(FileNotFoundError):
        ext.extract_surface_stats("schaefer100x7")


def test_extract_surface_stats_no_pattern_raises(
    mock_freesurfer_dir: Path, tmp_path: Path
) -> None:
    """ValueError when atlas has no freesurfer_stats_pattern."""
    ext = _make_extractor(mock_freesurfer_dir, tmp_path / "out", ["aseg"])
    with pytest.raises(ValueError, match="freesurfer_stats_pattern"):
        ext.extract_surface_stats("aseg")


def test_extract_surface_stats_desikan(
    mock_freesurfer_dir: Path, tmp_path: Path
) -> None:
    """extract_surface_stats() works for Desikan atlas (aparc.stats)."""
    ext = _make_extractor(mock_freesurfer_dir, tmp_path / "out", ["desikan"])
    result = ext.extract_surface_stats("desikan")
    assert "thickness" in result
    # 3 parcels × 2 hemispheres = 6 rows
    assert len(result["thickness"]) == 6


# ---------------------------------------------------------------------------
# Surface morphometrics (per-vertex fallback)
# ---------------------------------------------------------------------------

def test_surface_morphometrics_thickness_columns(
    mock_freesurfer_dir: Path, tmp_path: Path
) -> None:
    """Thickness DataFrame has expected columns."""
    ext = _make_extractor(mock_freesurfer_dir, tmp_path / "out", ["desikan"])
    df = ext.extract_surface_morphometrics("desikan", "thickness")
    assert list(df.columns) == ["region_index", "region_label", "hemisphere", "value", "metric"]


def test_surface_morphometrics_n_parcels(mock_freesurfer_dir: Path, tmp_path: Path) -> None:
    """Correct number of parcels × 2 hemispheres are returned."""
    ext = _make_extractor(mock_freesurfer_dir, tmp_path / "out", ["desikan"])
    df = ext.extract_surface_morphometrics("desikan", "thickness")
    # 3 real regions × 2 hemispheres (unknown is excluded)
    expected_real_regions = len([n for n in MOCK_REGION_NAMES if n.lower() != "unknown"])
    assert len(df) == expected_real_regions * 2


def test_surface_morphometrics_metric_column(mock_freesurfer_dir: Path, tmp_path: Path) -> None:
    """metric column matches the requested metric."""
    ext = _make_extractor(mock_freesurfer_dir, tmp_path / "out", ["desikan"])
    for metric in ("thickness", "area", "curvature", "sulc"):
        df = ext.extract_surface_morphometrics("desikan", metric)
        assert (df["metric"] == metric).all(), f"metric column wrong for {metric}"


def test_surface_morphometrics_area_is_summed(mock_freesurfer_dir: Path, tmp_path: Path) -> None:
    """Area values are sums (not means) of per-vertex areas."""
    import nibabel.freesurfer.io as fsio
    ext = _make_extractor(mock_freesurfer_dir, tmp_path / "out", ["desikan"])
    df = ext.extract_surface_morphometrics("desikan", "area")

    # For left hemisphere superiorfrontal: sum vertices at indices where label==1
    lh_area_data = fsio.read_morph_data(
        str(mock_freesurfer_dir / "surf" / "lh.area")
    )
    from tests.conftest import MOCK_LABELS
    expected_sum = float(lh_area_data[MOCK_LABELS == 1].sum())
    lh_rows = df[df["hemisphere"] == "L"]
    actual = lh_rows.loc[lh_rows["region_label"] == "superiorfrontal", "value"].iloc[0]
    assert actual == pytest.approx(expected_sum)


def test_surface_morphometrics_unknown_excluded(
    mock_freesurfer_dir: Path, tmp_path: Path
) -> None:
    """The 'unknown' region is not included in the output."""
    ext = _make_extractor(mock_freesurfer_dir, tmp_path / "out", ["desikan"])
    df = ext.extract_surface_morphometrics("desikan", "thickness")
    assert "unknown" not in df["region_label"].values


def test_surface_morphometrics_missing_annot(tmp_path: Path) -> None:
    """FileNotFoundError when annotation file is absent."""
    # Create a minimal FS dir with stats but no label/surf files
    fs_dir = tmp_path / "fs"
    (fs_dir / "stats").mkdir(parents=True)
    (fs_dir / "label").mkdir(parents=True)
    ext = _make_extractor(fs_dir, tmp_path / "out", ["desikan"])
    with pytest.raises(FileNotFoundError, match="Annotation file not found"):
        ext.extract_surface_morphometrics("desikan", "thickness")


def test_surface_morphometrics_volumetric_atlas_raises(
    mock_freesurfer_dir: Path, tmp_path: Path
) -> None:
    """ValueError when atlas type is 'volumetric' (can't use surface files)."""
    ext = _make_extractor(mock_freesurfer_dir, tmp_path / "out", ["aseg"])
    with pytest.raises(ValueError, match="surface"):
        ext.extract_surface_morphometrics("aseg", "thickness")


def test_surface_morphometrics_invalid_metric(mock_freesurfer_dir: Path, tmp_path: Path) -> None:
    """ValueError for unsupported metric name."""
    ext = _make_extractor(mock_freesurfer_dir, tmp_path / "out", ["desikan"])
    with pytest.raises(ValueError, match="Unsupported metric"):
        ext.extract_surface_morphometrics("desikan", "foobar")


# ---------------------------------------------------------------------------
# Full extract() orchestration
# ---------------------------------------------------------------------------

def test_extract_creates_output_files(mock_freesurfer_dir: Path, tmp_path: Path) -> None:
    """extract() writes expected TSV files and status JSON."""
    out_dir = tmp_path / "out"
    ext = _make_extractor(mock_freesurfer_dir, out_dir, ["aseg", "desikan"])
    status = ext.extract()

    anat_dir = out_dir / "anat"
    assert anat_dir.exists()

    tsv_files = list(anat_dir.glob("*.tsv"))
    assert len(tsv_files) > 0

    assert (out_dir / "_status.json").exists()
    assert status["modalities"]["anat"]["n_files"] > 0


def test_extract_uses_stats_file_when_available(
    mock_freesurfer_dir_with_schaefer: Path, tmp_path: Path
) -> None:
    """extract() uses stats-file path for schaefer100x7 and writes thickness/area/volume/curvature."""
    out_dir = tmp_path / "out"
    ext = _make_extractor(mock_freesurfer_dir_with_schaefer, out_dir, ["schaefer100x7"])
    status = ext.extract()

    anat_dir = out_dir / "anat"
    assert "schaefer100x7" in status["atlases_extracted"]
    # Should have thickness, area, volume, curvature
    tsv_files = list(anat_dir.glob("*atlas-schaefer100x7*"))
    metrics_found = {p.stem.split("desc-")[1].split("_")[0] for p in tsv_files}
    assert "thickness" in metrics_found
    assert "area" in metrics_found
    assert "volume" in metrics_found
    assert "curvature" in metrics_found


def test_extract_atlases_extracted(mock_freesurfer_dir: Path, tmp_path: Path) -> None:
    """extract() reports extracted and skipped atlases correctly."""
    out_dir = tmp_path / "out"
    ext = _make_extractor(mock_freesurfer_dir, out_dir, ["aseg", "desikan"])
    status = ext.extract()

    assert "aseg" in status["atlases_extracted"]
    assert "desikan" in status["atlases_extracted"]
    assert status["atlases_skipped"] == []


def test_extract_missing_atlas_skipped(mock_freesurfer_dir: Path, tmp_path: Path) -> None:
    """Atlas with missing annotation file is reported as skipped, not an error."""
    out_dir = tmp_path / "out"
    ext = _make_extractor(mock_freesurfer_dir, out_dir, ["schaefer400x7"])
    status = ext.extract()

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
