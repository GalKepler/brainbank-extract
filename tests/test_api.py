"""Tests for the researcher-facing Python API."""

from __future__ import annotations

from pathlib import Path

import pytest

import brainbank_extract as bb
from brainbank_extract.api import (
    list_available,
    load_connectivity,
    load_diffusion_scalars,
    load_global_metrics,
    load_morphometrics,
    load_tract_profiles,
    to_wide,
)


def test_version_is_set() -> None:
    """Package version is set."""
    assert bb.__version__ == "0.1.0"


def test_load_morphometrics_raises_not_implemented(tmp_path: Path) -> None:
    """load_morphometrics raises NotImplementedError until implemented."""
    with pytest.raises(NotImplementedError):
        load_morphometrics(
            extract_dir=tmp_path,
            metric="thickness",
            atlas="schaefer400x7",
        )


def test_load_connectivity_raises_not_implemented(tmp_path: Path) -> None:
    """load_connectivity raises NotImplementedError until implemented."""
    with pytest.raises(NotImplementedError):
        load_connectivity(
            extract_dir=tmp_path,
            atlas="schaefer400x7",
        )


def test_load_diffusion_scalars_raises_not_implemented(tmp_path: Path) -> None:
    """load_diffusion_scalars raises NotImplementedError until implemented."""
    with pytest.raises(NotImplementedError):
        load_diffusion_scalars(
            extract_dir=tmp_path,
            atlas="schaefer400x7",
            model="DTI",
            param="FA",
        )


def test_load_tract_profiles_raises_not_implemented(tmp_path: Path) -> None:
    """load_tract_profiles raises NotImplementedError until implemented."""
    with pytest.raises(NotImplementedError):
        load_tract_profiles(extract_dir=tmp_path)


def test_load_global_metrics_raises_not_implemented(tmp_path: Path) -> None:
    """load_global_metrics raises NotImplementedError until implemented."""
    with pytest.raises(NotImplementedError):
        load_global_metrics(extract_dir=tmp_path)


def test_list_available_raises_not_implemented(tmp_path: Path) -> None:
    """list_available raises NotImplementedError until implemented."""
    with pytest.raises(NotImplementedError):
        list_available(extract_dir=tmp_path)


def test_to_wide_pivot() -> None:
    """to_wide correctly pivots a long-format DataFrame."""
    import pandas as pd

    df = pd.DataFrame(
        {
            "subject": ["sub-001", "sub-001", "sub-002", "sub-002"],
            "session": ["ses-01", "ses-01", "ses-01", "ses-01"],
            "region_label": ["R1", "R2", "R1", "R2"],
            "value": [1.0, 2.0, 3.0, 4.0],
        }
    )
    wide = to_wide(df, index=["subject", "session"], columns="region_label", values="value")
    assert wide.shape == (2, 2)
    assert wide.loc[("sub-001", "ses-01"), "R1"] == 1.0
    assert wide.loc[("sub-002", "ses-01"), "R2"] == 4.0
