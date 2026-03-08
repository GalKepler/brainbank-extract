"""Researcher-facing API for loading aggregated brainbank-extract data."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd


def load_morphometrics(
    extract_dir: str | Path,
    metric: str,
    atlas: str,
) -> pd.DataFrame:
    """Load cortical morphometrics for all sessions.

    Parameters
    ----------
    extract_dir:
        Path to the aggregated brainbank-extract directory.
    metric:
        Morphometric to load: ``"thickness"``, ``"area"``, ``"volume"``,
        ``"curvature"``, or ``"sulc"``.
    atlas:
        Atlas key (e.g. ``"schaefer400x7"``).

    Returns
    -------
    pd.DataFrame
        Long-format DataFrame with columns:
        ``subject``, ``session``, ``region_index``, ``region_label``,
        ``hemisphere``, ``value``, ``metric``.
    """
    raise NotImplementedError(
        "load_morphometrics() is not yet implemented. "
        "Run bb-aggregate first to produce aggregated parquet files."
    )


def load_connectivity(
    extract_dir: str | Path,
    atlas: str,
    measure: str = "sift2",
) -> tuple[np.ndarray, pd.DataFrame, list[str]]:
    """Load stacked connectivity matrices for all sessions.

    Parameters
    ----------
    extract_dir:
        Path to the aggregated brainbank-extract directory.
    atlas:
        Atlas key (e.g. ``"schaefer400x7"``).
    measure:
        Connectivity measure: ``"sift2"``, ``"count"``, or ``"meanlength"``.

    Returns
    -------
    conn : np.ndarray
        Shape ``(N_sessions, N_parcels, N_parcels)``.
    meta : pd.DataFrame
        Maps axis-0 index to ``subject`` and ``session``.
    labels : list[str]
        Ordered region labels matching matrix rows/columns.
    """
    raise NotImplementedError(
        "load_connectivity() is not yet implemented. "
        "Run bb-aggregate first to produce aggregated numpy files."
    )


def load_diffusion_scalars(
    extract_dir: str | Path,
    atlas: str,
    model: str,
    param: str,
) -> pd.DataFrame:
    """Load parcellated diffusion scalar values for all sessions.

    Parameters
    ----------
    extract_dir:
        Path to the aggregated brainbank-extract directory.
    atlas:
        Atlas key (e.g. ``"schaefer400x7"``).
    model:
        Diffusion model: ``"DTI"``, ``"NODDI"``, ``"DKI"``, ``"MAPMRI"``.
    param:
        Model parameter (e.g. ``"FA"``, ``"MD"``, ``"ICVF"``, ``"MK"``).

    Returns
    -------
    pd.DataFrame
        Long-format DataFrame with columns:
        ``subject``, ``session``, ``region_index``, ``region_label``,
        ``hemisphere``, ``mean``, ``std``, ``median``, ``n_voxels``.
    """
    raise NotImplementedError(
        "load_diffusion_scalars() is not yet implemented. "
        "Run bb-aggregate first to produce aggregated parquet files."
    )


def load_tract_profiles(
    extract_dir: str | Path,
    tract: Optional[str] = None,
) -> pd.DataFrame:
    """Load pyAFQ tract profiles for all sessions.

    Parameters
    ----------
    extract_dir:
        Path to the aggregated brainbank-extract directory.
    tract:
        Optional tract name filter (e.g. ``"ArcuateL"``).
        If None, all tracts are returned.

    Returns
    -------
    pd.DataFrame
        Long-format DataFrame with columns:
        ``subject``, ``session``, ``tract``, ``node``, ``FA``, ``MD``, ...
    """
    raise NotImplementedError(
        "load_tract_profiles() is not yet implemented. "
        "Run bb-aggregate first to produce aggregated parquet files."
    )


def load_global_metrics(
    extract_dir: str | Path,
) -> pd.DataFrame:
    """Load global brain metrics (eTIV, brain volumes) for all sessions.

    Parameters
    ----------
    extract_dir:
        Path to the aggregated brainbank-extract directory.

    Returns
    -------
    pd.DataFrame
        DataFrame with columns: ``subject``, ``session``, ``metric``, ``value``.
    """
    raise NotImplementedError(
        "load_global_metrics() is not yet implemented. "
        "Run bb-aggregate first to produce aggregated parquet files."
    )


def list_available(extract_dir: str | Path) -> dict:
    """List all aggregated data available in an extract directory.

    Parameters
    ----------
    extract_dir:
        Path to the aggregated brainbank-extract directory.

    Returns
    -------
    dict
        Summary of available atlases, metrics, models, and parameters.
    """
    raise NotImplementedError(
        "list_available() is not yet implemented."
    )


def to_wide(
    df: pd.DataFrame,
    index: list[str],
    columns: str,
    values: str,
) -> pd.DataFrame:
    """Pivot a long-format DataFrame to wide format.

    Convenience wrapper around ``pd.pivot_table``.

    Parameters
    ----------
    df:
        Long-format DataFrame (e.g. from ``load_morphometrics()``).
    index:
        Columns to use as row index (e.g. ``["subject", "session"]``).
    columns:
        Column whose values become new column names (e.g. ``"region_label"``).
    values:
        Column containing the values to fill (e.g. ``"value"``).

    Returns
    -------
    pd.DataFrame
        Wide-format DataFrame.
    """
    return df.pivot_table(index=index, columns=columns, values=values)
