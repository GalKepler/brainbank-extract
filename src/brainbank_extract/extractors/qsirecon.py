"""QSIRecon diffusion extractor."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class QSIReconExtractor:
    """Extract diffusion features from a QSIRecon session directory.

    Parameters
    ----------
    qsirecon_dir:
        Path to the QSIRecon subject/session directory
        (contains ``dwi/`` subdirectory with parcellated TSVs and connectivity files).
    output_dir:
        Path where extracted files will be written (``dwi/`` subdirectory).
    subject:
        BIDS subject identifier (e.g. ``"sub-001"``).
    session:
        BIDS session identifier (e.g. ``"ses-20240101"``).
    atlases:
        List of atlas keys to extract (e.g. ``["schaefer400x7", "tian_s2"]``).
    """

    def __init__(
        self,
        qsirecon_dir: Path,
        output_dir: Path,
        subject: str,
        session: str,
        atlases: list[str],
    ) -> None:
        self.qsirecon_dir = Path(qsirecon_dir)
        self.output_dir = Path(output_dir)
        self.subject = subject
        self.session = session
        self.atlases = atlases

    def extract(self) -> dict[str, str]:
        """Run all QSIRecon extractions for this session.

        Returns
        -------
        dict
            Status summary with keys ``atlases_extracted``, ``atlases_skipped``,
            and ``warnings``.

        Raises
        ------
        NotImplementedError
            Until extraction is implemented.
        """
        raise NotImplementedError(
            "QSIReconExtractor.extract() is not yet implemented."
        )

    def extract_scalars(self, atlas: str) -> list[pd.DataFrame]:
        """Discover and standardize parcellated scalar TSVs for a given atlas.

        Globs for ``*_parc.tsv`` files, parses BIDS entities from filenames,
        and copies/renames to the standard output naming convention.

        Parameters
        ----------
        atlas:
            Atlas key from the registry (e.g. ``"schaefer400x7"``).

        Returns
        -------
        list[pd.DataFrame]
            One DataFrame per (model, param) combination found.

        Raises
        ------
        NotImplementedError
            Until extraction is implemented.
        """
        raise NotImplementedError(
            "QSIReconExtractor.extract_scalars() is not yet implemented."
        )

    def extract_connectivity(
        self,
        atlas: str,
        measure: str,
    ) -> tuple[np.ndarray, list[str]]:
        """Extract a connectivity matrix for a given atlas and measure.

        Locates the connectivity CSV or npy file, converts to numpy array,
        verifies symmetry, and generates a companion labels JSON.

        Parameters
        ----------
        atlas:
            Atlas key from the registry.
        measure:
            Connectivity measure: ``"sift2"``, ``"count"``, or ``"meanlength"``.

        Returns
        -------
        matrix : np.ndarray
            Shape ``(N_parcels, N_parcels)``.
        labels : list[str]
            Ordered region labels.

        Raises
        ------
        NotImplementedError
            Until extraction is implemented.
        """
        raise NotImplementedError(
            "QSIReconExtractor.extract_connectivity() is not yet implemented."
        )

    def extract_tract_profiles(self) -> list[pd.DataFrame]:
        """Extract pyAFQ tract profiles if present.

        Checks for pyAFQ output directory, locates per-tract profile files,
        and standardizes column names.

        Returns
        -------
        list[pd.DataFrame]
            One DataFrame per tract. Empty list if no pyAFQ outputs found.

        Raises
        ------
        NotImplementedError
            Until extraction is implemented.
        """
        raise NotImplementedError(
            "QSIReconExtractor.extract_tract_profiles() is not yet implemented."
        )
