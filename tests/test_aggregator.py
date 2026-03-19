"""Tests for the dataset-level aggregator."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from click.testing import CliRunner

from brainbank_extract.aggregator import Aggregator, _parse_bids_entities
from brainbank_extract.cli import aggregate


# ---------------------------------------------------------------------------
# _parse_bids_entities helper
# ---------------------------------------------------------------------------


def test_parse_bids_entities_basic() -> None:
    entities = _parse_bids_entities(
        "sub-001_ses-test_atlas-schaefer100x7_pipeline-DIPYDKI"
        "_model-dkimicro_param-fa_desc-parcellated_diffmetrics.tsv"
    )
    assert entities["atlas"] == "schaefer100x7"
    assert entities["pipeline"] == "DIPYDKI"
    assert entities["model"] == "dkimicro"
    assert entities["param"] == "fa"
    assert entities["desc"] == "parcellated"


def test_parse_bids_entities_globalmetrics() -> None:
    entities = _parse_bids_entities("sub-001_ses-test_desc-globalmetrics_morph.tsv")
    assert entities["desc"] == "globalmetrics"
    assert "atlas" not in entities


# ---------------------------------------------------------------------------
# Session discovery
# ---------------------------------------------------------------------------


def test_aggregator_discovers_sessions(mock_extract_dir: Path, tmp_path: Path) -> None:
    agg = Aggregator(extract_dir=mock_extract_dir, output_dir=tmp_path / "out")
    sessions = agg._discover_sessions()
    assert len(sessions) == 3
    subjects = {s[0] for s in sessions}
    assert "sub-001" in subjects
    assert "sub-002" in subjects


def test_discover_sessions_empty_dir(tmp_path: Path) -> None:
    agg = Aggregator(extract_dir=tmp_path / "empty", output_dir=tmp_path / "out")
    assert agg._discover_sessions() == []


# ---------------------------------------------------------------------------
# Sidecar roundtrip
# ---------------------------------------------------------------------------


def test_sidecar_roundtrip(tmp_path: Path) -> None:
    agg = Aggregator(extract_dir=tmp_path, output_dir=tmp_path / "out")
    agg.output_dir.mkdir(parents=True)
    pairs: set[tuple[str, str]] = {("sub-001", "ses-20240101"), ("sub-002", "ses-20240601")}
    agg._save_completed_sessions(pairs)
    assert agg._load_completed_sessions() == pairs


# ---------------------------------------------------------------------------
# Anat aggregation
# ---------------------------------------------------------------------------


def test_aggregator_run_anat_creates_parquets(
    mock_extract_dir_with_anat: Path, tmp_path: Path
) -> None:
    out_dir = tmp_path / "aggregated"
    agg = Aggregator(
        extract_dir=mock_extract_dir_with_anat, output_dir=out_dir, modalities=["anat"]
    )
    summary = agg.run()

    assert summary["new_sessions"] == 3
    assert (out_dir / "anat" / "desc-globalmetrics_morph.parquet").exists()
    assert (out_dir / "anat" / "atlas-desikan_desc-thickness_morph.parquet").exists()
    assert (out_dir / "anat" / "atlas-desikan_desc-area_morph.parquet").exists()


def test_anat_parquet_has_subject_session_columns(
    mock_extract_dir_with_anat: Path, tmp_path: Path
) -> None:
    out_dir = tmp_path / "aggregated"
    Aggregator(
        extract_dir=mock_extract_dir_with_anat, output_dir=out_dir, modalities=["anat"]
    ).run()

    import pandas as pd
    df = pd.read_parquet(out_dir / "anat" / "atlas-desikan_desc-thickness_morph.parquet")
    assert "subject" in df.columns
    assert "session" in df.columns
    assert list(df.columns[:2]) == ["subject", "session"]


def test_anat_thickness_row_count(
    mock_extract_dir_with_anat: Path, tmp_path: Path
) -> None:
    """3 sessions × 3 regions = 9 rows."""
    out_dir = tmp_path / "aggregated"
    Aggregator(
        extract_dir=mock_extract_dir_with_anat, output_dir=out_dir, modalities=["anat"]
    ).run()

    import pandas as pd
    df = pd.read_parquet(out_dir / "anat" / "atlas-desikan_desc-thickness_morph.parquet")
    assert len(df) == 9


def test_anat_subjects_present(
    mock_extract_dir_with_anat: Path, tmp_path: Path
) -> None:
    out_dir = tmp_path / "aggregated"
    Aggregator(
        extract_dir=mock_extract_dir_with_anat, output_dir=out_dir, modalities=["anat"]
    ).run()

    import pandas as pd
    df = pd.read_parquet(out_dir / "anat" / "atlas-desikan_desc-thickness_morph.parquet")
    assert set(df["subject"].unique()) == {"sub-001", "sub-002"}


def test_global_metrics_parquet(
    mock_extract_dir_with_anat: Path, tmp_path: Path
) -> None:
    out_dir = tmp_path / "aggregated"
    Aggregator(
        extract_dir=mock_extract_dir_with_anat, output_dir=out_dir, modalities=["anat"]
    ).run()

    import pandas as pd
    df = pd.read_parquet(out_dir / "anat" / "desc-globalmetrics_morph.parquet")
    assert "metric" in df.columns
    assert "value" in df.columns
    assert len(df) == 9  # 3 sessions × 3 metrics


def test_anat_parquet_column_order(
    mock_extract_dir_with_anat: Path, tmp_path: Path
) -> None:
    out_dir = tmp_path / "aggregated"
    Aggregator(
        extract_dir=mock_extract_dir_with_anat, output_dir=out_dir, modalities=["anat"]
    ).run()

    import pandas as pd
    df = pd.read_parquet(out_dir / "anat" / "atlas-desikan_desc-thickness_morph.parquet")
    assert df.columns[0] == "subject"
    assert df.columns[1] == "session"


# ---------------------------------------------------------------------------
# Incremental and force
# ---------------------------------------------------------------------------


def test_incremental_aggregation(
    mock_extract_dir_with_anat: Path, tmp_path: Path
) -> None:
    out_dir = tmp_path / "aggregated"
    agg = Aggregator(
        extract_dir=mock_extract_dir_with_anat, output_dir=out_dir, modalities=["anat"]
    )
    agg.run()
    assert len(agg._load_completed_sessions()) == 3

    # Add a 4th session
    import pandas as pd
    new_ses_dir = mock_extract_dir_with_anat / "sub-003" / "ses-20240101"
    anat_dir = new_ses_dir / "anat" / "atlas-desikan"
    anat_dir.mkdir(parents=True)
    prefix = "sub-003_ses-20240101"
    rows = [
        {"region_index": i + 1, "region_label": f"region{i}", "hemisphere": "L",
         "value": 2.5, "metric": "thickness"}
        for i in range(3)
    ]
    pd.DataFrame(rows).to_csv(
        anat_dir / f"{prefix}_atlas-desikan_desc-thickness_morph.tsv", sep="\t", index=False
    )

    agg.run()
    assert len(agg._load_completed_sessions()) == 4

    df = pd.read_parquet(out_dir / "anat" / "atlas-desikan_desc-thickness_morph.parquet")
    assert len(df) == 12  # 4 sessions × 3 regions


def test_second_run_no_change(
    mock_extract_dir_with_anat: Path, tmp_path: Path
) -> None:
    out_dir = tmp_path / "aggregated"
    agg = Aggregator(
        extract_dir=mock_extract_dir_with_anat, output_dir=out_dir, modalities=["anat"]
    )
    agg.run()

    import pandas as pd
    df_before = pd.read_parquet(out_dir / "anat" / "atlas-desikan_desc-thickness_morph.parquet")

    summary = agg.run()
    assert summary["new_sessions"] == 0

    df_after = pd.read_parquet(out_dir / "anat" / "atlas-desikan_desc-thickness_morph.parquet")
    assert len(df_before) == len(df_after)


def test_force_reaggregates_all(
    mock_extract_dir_with_anat: Path, tmp_path: Path
) -> None:
    out_dir = tmp_path / "aggregated"
    Aggregator(
        extract_dir=mock_extract_dir_with_anat, output_dir=out_dir, modalities=["anat"]
    ).run()

    summary = Aggregator(
        extract_dir=mock_extract_dir_with_anat, output_dir=out_dir,
        modalities=["anat"], force=True
    ).run()
    assert summary["new_sessions"] == 3


def test_no_new_sessions_returns_zero(
    mock_extract_dir_with_anat: Path, tmp_path: Path
) -> None:
    out_dir = tmp_path / "aggregated"
    agg = Aggregator(
        extract_dir=mock_extract_dir_with_anat, output_dir=out_dir, modalities=["anat"]
    )
    agg.run()
    assert agg.run() == {"new_sessions": 0}


# ---------------------------------------------------------------------------
# DWI scalar aggregation
# ---------------------------------------------------------------------------


def test_dwi_scalars_parquet_exists(
    mock_extract_dir_with_dwi_scalars: Path, tmp_path: Path
) -> None:
    out_dir = tmp_path / "aggregated"
    Aggregator(
        extract_dir=mock_extract_dir_with_dwi_scalars, output_dir=out_dir, modalities=["dwi"]
    ).run()

    expected = (
        out_dir / "dwi" / "scalars"
        / "pipeline-DIPYDKI_atlas-schaefer100x7_model-dkimicro_param-fa"
          "_desc-parcellated_diffmetrics.parquet"
    )
    assert expected.exists()


def test_dwi_scalars_row_count(
    mock_extract_dir_with_dwi_scalars: Path, tmp_path: Path
) -> None:
    """3 sessions × 4 parcels = 12 rows."""
    out_dir = tmp_path / "aggregated"
    Aggregator(
        extract_dir=mock_extract_dir_with_dwi_scalars, output_dir=out_dir, modalities=["dwi"]
    ).run()

    import pandas as pd
    df = pd.read_parquet(
        out_dir / "dwi" / "scalars"
        / "pipeline-DIPYDKI_atlas-schaefer100x7_model-dkimicro_param-fa"
          "_desc-parcellated_diffmetrics.parquet"
    )
    assert len(df) == 12
    assert "mean" in df.columns
    assert df.columns[0] == "subject"
    assert df.columns[1] == "session"


# ---------------------------------------------------------------------------
# DWI connectivity aggregation
# ---------------------------------------------------------------------------


def test_connectivity_npy_exists(
    mock_extract_dir_with_connectivity: Path, tmp_path: Path
) -> None:
    out_dir = tmp_path / "aggregated"
    Aggregator(
        extract_dir=mock_extract_dir_with_connectivity, output_dir=out_dir, modalities=["dwi"]
    ).run()

    expected = (
        out_dir / "dwi" / "connectivity"
        / "pipeline-MRtrix3_act-HSVS_atlas-schaefer100x7_tian_s1_desc-sift2_connmatrix.npy"
    )
    assert expected.exists()


def test_connectivity_shape(
    mock_extract_dir_with_connectivity: Path, tmp_path: Path
) -> None:
    out_dir = tmp_path / "aggregated"
    Aggregator(
        extract_dir=mock_extract_dir_with_connectivity, output_dir=out_dir, modalities=["dwi"]
    ).run()

    arr = np.load(
        out_dir / "dwi" / "connectivity"
        / "pipeline-MRtrix3_act-HSVS_atlas-schaefer100x7_tian_s1_desc-sift2_connmatrix.npy"
    )
    assert arr.shape == (3, 6, 6)


def test_connectivity_meta_parquet(
    mock_extract_dir_with_connectivity: Path, tmp_path: Path
) -> None:
    out_dir = tmp_path / "aggregated"
    Aggregator(
        extract_dir=mock_extract_dir_with_connectivity, output_dir=out_dir, modalities=["dwi"]
    ).run()

    import pandas as pd
    meta = pd.read_parquet(
        out_dir / "dwi" / "connectivity"
        / "pipeline-MRtrix3_act-HSVS_atlas-schaefer100x7_tian_s1"
          "_desc-sift2_connmatrix-meta.parquet"
    )
    assert len(meta) == 3
    assert list(meta.columns[:3]) == ["session_index", "subject", "session"]
    assert meta["session_index"].tolist() == [0, 1, 2]


def test_connectivity_labels_json(
    mock_extract_dir_with_connectivity: Path, tmp_path: Path
) -> None:
    out_dir = tmp_path / "aggregated"
    Aggregator(
        extract_dir=mock_extract_dir_with_connectivity, output_dir=out_dir, modalities=["dwi"]
    ).run()

    labels_path = (
        out_dir / "dwi" / "connectivity"
        / "pipeline-MRtrix3_act-HSVS_atlas-schaefer100x7_tian_s1"
          "_desc-sift2_connmatrix-labels.json"
    )
    assert labels_path.exists()
    labels = json.loads(labels_path.read_text())
    assert len(labels) == 6


def test_connectivity_incremental_stacking(
    mock_extract_dir_with_connectivity: Path, tmp_path: Path
) -> None:
    out_dir = tmp_path / "aggregated"
    agg = Aggregator(
        extract_dir=mock_extract_dir_with_connectivity, output_dir=out_dir, modalities=["dwi"]
    )
    agg.run()

    # Add a 4th session
    rng = np.random.default_rng(99)
    n = 6
    raw = rng.integers(0, 100, size=(n, n)).astype(np.float64)
    matrix = (raw + raw.T) / 2.0
    np.fill_diagonal(matrix, 0)

    new_ses_dir = (
        mock_extract_dir_with_connectivity / "sub-003" / "ses-20240101"
        / "dwi" / "connectivity"
        / "pipeline-MRtrix3_act-HSVS" / "atlas-schaefer100x7_tian_s1"
    )
    new_ses_dir.mkdir(parents=True)
    base = (
        "sub-003_ses-20240101_atlas-schaefer100x7_tian_s1"
        "_pipeline-MRtrix3_act-HSVS_desc-sift2_connmatrix"
    )
    np.save(str(new_ses_dir / f"{base}.npy"), matrix)
    (new_ses_dir / f"{base}-labels.json").write_text(
        json.dumps(["LH_Vis_1", "LH_Vis_2", "RH_Vis_1", "RH_Vis_2", "HIP-lh", "HIP-rh"])
    )

    agg.run()

    arr = np.load(
        out_dir / "dwi" / "connectivity"
        / "pipeline-MRtrix3_act-HSVS_atlas-schaefer100x7_tian_s1_desc-sift2_connmatrix.npy"
    )
    assert arr.shape == (4, 6, 6)

    import pandas as pd
    meta = pd.read_parquet(
        out_dir / "dwi" / "connectivity"
        / "pipeline-MRtrix3_act-HSVS_atlas-schaefer100x7_tian_s1"
          "_desc-sift2_connmatrix-meta.parquet"
    )
    assert len(meta) == 4
    assert meta["session_index"].tolist() == [0, 1, 2, 3]


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


def test_bb_aggregate_cli_anat(
    mock_extract_dir_with_anat: Path, tmp_path: Path
) -> None:
    runner = CliRunner()
    result = runner.invoke(aggregate, [
        "--extract-dir", str(mock_extract_dir_with_anat),
        "--output-dir", str(tmp_path / "out"),
        "--modalities", "anat",
    ])
    assert result.exit_code == 0, result.output
    assert "complete" in result.output.lower()
    assert "3" in result.output


def test_bb_aggregate_cli_empty_dir(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(aggregate, [
        "--extract-dir", str(tmp_path / "empty"),
        "--output-dir", str(tmp_path / "out"),
    ])
    assert result.exit_code == 0
    assert "0" in result.output
