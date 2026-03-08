"""I/O helpers for reading and writing brainbank-extract files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def write_tsv(df: pd.DataFrame, path: Path | str) -> None:
    """Write a DataFrame to a tab-separated file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, sep="\t", index=False)


def read_tsv(path: Path | str) -> pd.DataFrame:
    """Read a tab-separated file into a DataFrame."""
    return pd.read_csv(path, sep="\t")


def write_parquet(df: pd.DataFrame, path: Path | str) -> None:
    """Write a DataFrame to a Parquet file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def read_parquet(path: Path | str) -> pd.DataFrame:
    """Read a Parquet file into a DataFrame."""
    return pd.read_parquet(path)


def write_npy(array: np.ndarray, path: Path | str) -> None:
    """Write a numpy array to a .npy file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    np.save(path, array)


def read_npy(path: Path | str) -> np.ndarray:
    """Read a .npy file into a numpy array."""
    return np.load(path)


def write_labels_json(labels: list[str], path: Path | str) -> None:
    """Write an ordered list of region labels to a JSON file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(labels, f, indent=2)


def read_labels_json(path: Path | str) -> list[str]:
    """Read an ordered list of region labels from a JSON file."""
    with open(path) as f:
        return json.load(f)


def write_status_json(status: dict[str, Any], path: Path | str) -> None:
    """Write a session status sidecar JSON file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(status, f, indent=2)


def read_status_json(path: Path | str) -> dict[str, Any]:
    """Read a session status sidecar JSON file."""
    with open(path) as f:
        return json.load(f)
