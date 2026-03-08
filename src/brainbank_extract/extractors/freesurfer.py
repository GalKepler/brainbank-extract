"""FreeSurfer morphometric extractor."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


class FreeSurferExtractor:
    """Extract morphometric features from a FreeSurfer subject directory.

    Parameters
    ----------
    freesurfer_dir:
        Path to the FreeSurfer subject/session directory
        (contains ``surf/``, ``label/``, ``stats/`` subdirectories).
    output_dir:
        Path where extracted TSV files will be written (``anat/`` subdirectory).
    subject:
        BIDS subject identifier (e.g. ``"sub-001"``).
    session:
        BIDS session identifier (e.g. ``"ses-20240101"``).
    atlases:
        List of atlas keys to extract (e.g. ``["schaefer400x7", "desikan"]``).
    """

    def __init__(
        self,
        freesurfer_dir: Path,
        output_dir: Path,
        subject: str,
        session: str,
        atlases: list[str],
    ) -> None:
        self.freesurfer_dir = Path(freesurfer_dir)
        self.output_dir = Path(output_dir)
        self.subject = subject
        self.session = session
        self.atlases = atlases

    def extract(self) -> dict[str, str]:
        """Run all FreeSurfer extractions for this session.

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
            "FreeSurferExtractor.extract() is not yet implemented."
        )

    def extract_aseg(self) -> pd.DataFrame:
        """Parse ``stats/aseg.stats`` for subcortical volumes.

        Returns
        -------
        pd.DataFrame
            Columns: ``region_index``, ``region_label``, ``hemisphere``,
            ``value``, ``metric``.

        Raises
        ------
        NotImplementedError
            Until extraction is implemented.
        """
        raise NotImplementedError(
            "FreeSurferExtractor.extract_aseg() is not yet implemented."
        )

    def extract_global_metrics(self) -> pd.DataFrame:
        """Parse global metrics from the ``aseg.stats`` header.

        Extracts: eTIV, BrainSegVol, BrainSegVolNotVent, lhCortexVol,
        rhCortexVol, SubCortGrayVol, CerebralWhiteMatterVol, MaskVol.

        Returns
        -------
        pd.DataFrame
            Columns: ``metric``, ``value``, ``source``.

        Raises
        ------
        NotImplementedError
            Until extraction is implemented.
        """
        raise NotImplementedError(
            "FreeSurferExtractor.extract_global_metrics() is not yet implemented."
        )

    def extract_surface_morphometrics(
        self,
        atlas: str,
        metric: str,
    ) -> pd.DataFrame:
        """Extract parcellated surface morphometrics for a given atlas.

        Loads the atlas annotation file and per-vertex metric file, then
        computes mean/std/median/n_vertices per parcel.

        Parameters
        ----------
        atlas:
            Atlas key from the registry (e.g. ``"schaefer400x7"``).
        metric:
            One of ``"thickness"``, ``"area"``, ``"volume"``,
            ``"curvature"``, ``"sulc"``.

        Returns
        -------
        pd.DataFrame
            Columns: ``region_index``, ``region_label``, ``hemisphere``,
            ``value``, ``metric``.

        Raises
        ------
        NotImplementedError
            Until extraction is implemented.
        """
        raise NotImplementedError(
            "FreeSurferExtractor.extract_surface_morphometrics() is not yet implemented."
        )
