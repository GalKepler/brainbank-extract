"""Tests for the dataset-level aggregator."""

from __future__ import annotations

from pathlib import Path

import pytest

from brainbank_extract.aggregator import Aggregator


@pytest.mark.skip(reason="Aggregator not yet implemented")
def test_aggregator_discovers_sessions(mock_extract_dir: Path, tmp_path: Path) -> None:
    """Aggregator finds all (subject, session) pairs in the extract directory."""
    agg = Aggregator(
        extract_dir=mock_extract_dir,
        output_dir=tmp_path / "aggregated",
    )
    sessions = agg._discover_sessions()
    assert len(sessions) == 3
    subjects = {s[0] for s in sessions}
    assert "sub-001" in subjects
    assert "sub-002" in subjects


@pytest.mark.skip(reason="Aggregator not yet implemented")
def test_aggregator_run_creates_parquet(mock_extract_dir: Path, tmp_path: Path) -> None:
    """Aggregator.run() produces parquet files in the output directory."""
    out_dir = tmp_path / "aggregated"
    agg = Aggregator(
        extract_dir=mock_extract_dir,
        output_dir=out_dir,
        modalities=["anat"],
    )
    agg.run()

    assert out_dir.exists()
    parquet_files = list(out_dir.rglob("*.parquet"))
    assert len(parquet_files) > 0


@pytest.mark.skip(reason="Aggregator not yet implemented")
def test_incremental_aggregation(mock_extract_dir: Path, tmp_path: Path) -> None:
    """Second run only processes newly added sessions."""
    out_dir = tmp_path / "aggregated"
    agg = Aggregator(extract_dir=mock_extract_dir, output_dir=out_dir)
    agg.run()

    completed_after_first = agg._load_completed_sessions()
    assert len(completed_after_first) == 3

    # Run again — no new sessions, no re-processing
    agg.run()
    completed_after_second = agg._load_completed_sessions()
    assert completed_after_first == completed_after_second


@pytest.mark.skip(reason="Aggregator not yet implemented")
def test_force_flag_reaggregates_all(mock_extract_dir: Path, tmp_path: Path) -> None:
    """--force flag causes all sessions to be re-aggregated."""
    out_dir = tmp_path / "aggregated"
    agg = Aggregator(extract_dir=mock_extract_dir, output_dir=out_dir, force=True)
    agg.run()
    # Should complete without error and process all sessions
    completed = agg._load_completed_sessions()
    assert len(completed) == 3


def test_discover_sessions_empty_dir(tmp_path: Path) -> None:
    """_discover_sessions returns empty list for an empty extract directory."""
    agg = Aggregator(
        extract_dir=tmp_path / "empty",
        output_dir=tmp_path / "out",
    )
    # Directory doesn't exist yet — should return empty, not raise
    sessions = agg._discover_sessions()
    assert sessions == []


def test_sidecar_roundtrip(tmp_path: Path) -> None:
    """Completed sessions sidecar is saved and loaded correctly."""
    agg = Aggregator(
        extract_dir=tmp_path,
        output_dir=tmp_path / "out",
    )
    agg.output_dir.mkdir(parents=True)

    pairs: set[tuple[str, str]] = {("sub-001", "ses-20240101"), ("sub-002", "ses-20240601")}
    agg._save_completed_sessions(pairs)
    loaded = agg._load_completed_sessions()
    assert loaded == pairs
