"""QSIRecon diffusion extractor."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import nibabel as nib
import numpy as np
import pandas as pd
import scipy.io  # type: ignore[import]

from brainbank_extract import __version__
from brainbank_extract.atlases import (
    build_label_filter,
    get_atlas,
    get_containing_combined_atlases,
)
from brainbank_extract.io import write_status_json, write_tsv

logger = logging.getLogger(__name__)

# Leading columns for diffusion scalar output TSVs (others from VolumetricParcellator follow)
_SCALAR_LEADING_COLS = ["region_index", "region_label", "hemisphere"]


class QSIReconExtractor:
    """Extract diffusion features from QSIRecon derivative directories.

    Parameters
    ----------
    qsirecon_dir:
        Path to the **root** QSIRecon derivatives directory (the one containing
        ``sub-*/`` session directories and a ``derivatives/`` subdirectory with
        pipeline-specific outputs).
    output_dir:
        Path where extracted files will be written (``dwi/`` subdirectory).
    subject:
        BIDS subject identifier (e.g. ``"sub-001"``).
    session:
        BIDS session identifier (e.g. ``"ses-20240101"``).
    atlases:
        List of atlas keys to extract (e.g. ``["4S156Parcels", "schaefer100x7"]``).
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

    # ------------------------------------------------------------------
    # Public orchestrator
    # ------------------------------------------------------------------

    def extract(self) -> dict:
        """Run all QSIRecon extractions for this session.

        Returns
        -------
        dict
            Status summary.
        """
        warnings: list[str] = []
        atlases_extracted: list[str] = []
        atlases_skipped: list[str] = []
        n_scalar_files = 0
        n_conn_files = 0

        if not self.qsirecon_dir.exists():
            msg = f"QSIRecon directory not found: {self.qsirecon_dir}"
            logger.warning(msg)
            status = {
                "subject": self.subject,
                "session": self.session,
                "extraction_date": datetime.now().isoformat(),
                "brainbank_extract_version": __version__,
                "atlases_extracted": [],
                "atlases_skipped": self.atlases,
                "modalities": {
                    "dwi_scalars": {"status": "error", "n_files": 0},
                    "dwi_connectivity": {"status": "error", "n_files": 0},
                    "dwi_tractprofiles": {"status": "skipped", "reason": "no pyAFQ outputs"},
                },
                "warnings": [msg],
            }
            write_status_json(status, self.output_dir / "_status.json")
            return status

        # Track which combined atlases have had their connectivity written to
        # avoid writing the same full matrix multiple times when several
        # component atlases (e.g. schaefer400x7 + tian_s2) share one combined seg.
        written_combined_connectivity: set[str] = set()

        for atlas in self.atlases:
            atlas_ok = False

            # Scalar extraction
            try:
                written = self._extract_and_write_scalars(atlas)
                n_scalar_files += written
                if written > 0:
                    atlas_ok = True
            except Exception as exc:
                msg = f"Atlas {atlas!r} scalar extraction failed: {exc}"
                warnings.append(msg)
                logger.warning(msg)

            # Connectivity extraction
            try:
                written = self._extract_and_write_connectivity(
                    atlas, written_combined_connectivity
                )
                n_conn_files += written
                if written > 0:
                    atlas_ok = True
            except Exception as exc:
                msg = f"Atlas {atlas!r} connectivity extraction failed: {exc}"
                warnings.append(msg)
                logger.warning(msg)

            if atlas_ok:
                atlases_extracted.append(atlas)
            else:
                atlases_skipped.append(atlas)

        # Tract profiles (not implemented — pyAFQ outputs not available)
        tract_profiles = self.extract_tract_profiles()

        status = {
            "subject": self.subject,
            "session": self.session,
            "extraction_date": datetime.now().isoformat(),
            "brainbank_extract_version": __version__,
            "atlases_extracted": atlases_extracted,
            "atlases_skipped": atlases_skipped,
            "modalities": {
                "dwi_scalars": {
                    "status": "complete" if n_scalar_files > 0 else "failed",
                    "n_files": n_scalar_files,
                },
                "dwi_connectivity": {
                    "status": "complete" if n_conn_files > 0 else "failed",
                    "n_files": n_conn_files,
                },
                "dwi_tractprofiles": {
                    "status": "complete" if tract_profiles else "skipped",
                    "reason": "no pyAFQ outputs" if not tract_profiles else None,
                    "n_tracts": len(tract_profiles),
                },
            },
            "warnings": warnings,
        }
        write_status_json(status, self.output_dir / "_status.json")
        return status

    # ------------------------------------------------------------------
    # Scalar extraction
    # ------------------------------------------------------------------

    def extract_scalars(self, atlas: str) -> list[pd.DataFrame]:
        """Parcellate scalar dwimap NII files for a given atlas.

        Discovers all ``*_model-*_param-*_dwimap.nii.gz`` files across all
        pipeline subdirectories and uses :class:`~parcellate.VolumetricParcellator`
        to compute extended per-parcel statistics.

        For component atlases (e.g. ``schaefer400x7``), the combined QSIRecon
        segmentation (e.g. ``Schaefer2018N400n7Tian2020S2``) is used and labels
        are filtered to only those belonging to this component.

        Parameters
        ----------
        atlas:
            Atlas key from the registry.

        Returns
        -------
        list[pd.DataFrame]
            One DataFrame per (pipeline, model, param) combination found.
            Each has columns: ``region_index``, ``region_label``, ``hemisphere``,
            extended statistics (mean, std, median, n_voxels, ...), ``model``,
            ``param``, ``pipeline``.

        Raises
        ------
        FileNotFoundError
            If the atlas segmentation NII is not found.
        """
        from parcellate import VolumetricParcellator  # type: ignore[import]

        seg_name, label_filter = self._resolve_seg_and_filter(atlas)
        atlas_path, labels = self._find_atlas_seg(seg_name)

        # Apply label filter for component atlases
        if label_filter is not None:
            labels = {idx: lbl for idx, lbl in labels.items() if label_filter(idx, lbl)}

        if not labels:
            logger.warning(
                "No labels remain after filtering for atlas %r in seg %r", atlas, seg_name
            )
            return []

        # Build LUT DataFrame for VolumetricParcellator
        lut_df = pd.DataFrame(
            [(idx, lbl) for idx, lbl in sorted(labels.items())],
            columns=["index", "label"],
        )

        # Discover all scalar maps across pipelines
        scalar_maps = self._find_scalar_maps()
        if not scalar_maps:
            logger.info(
                "No scalar dwimap files found for subject %s session %s",
                self.subject, self.session,
            )
            return []

        # Create parcellator and fit once to the first scalar image's space
        atlas_img = nib.load(str(atlas_path))
        parcellator = VolumetricParcellator(
            atlas_img,
            lut=lut_df,
            stat_tier="extended",
            resampling_target="data",
        )
        first_path = scalar_maps[0][0]
        parcellator.fit(nib.load(str(first_path)))

        results = []
        for scalar_path, pipeline, model, param in scalar_maps:
            try:
                df = parcellator.transform(scalar_path)

                # Rename LUT columns to brainbank spec
                df = df.rename(columns={"index": "region_index", "label": "region_label"})

                # Rename voxel_count → n_voxels for spec compatibility
                if "voxel_count" in df.columns:
                    df = df.rename(columns={"voxel_count": "n_voxels"})

                # Add hemisphere inferred from region label
                df.insert(2, "hemisphere", df["region_label"].apply(_label_hemisphere))

                # Add metadata columns
                df["model"] = model
                df["param"] = param
                df["pipeline"] = pipeline

                results.append(df)
            except Exception as exc:
                logger.warning("Failed to parcellate %s: %s", scalar_path.name, exc)

        return results

    def _extract_and_write_scalars(self, atlas: str) -> int:
        """Extract scalars for an atlas and write TSV files. Returns number of files written."""
        prefix = f"{self.subject}_{self.session}"

        dfs = self.extract_scalars(atlas)
        written = 0
        for df in dfs:
            model = df["model"].iloc[0]
            param = df["param"].iloc[0]
            pipeline = df["pipeline"].iloc[0]
            out_dir = (
                self.output_dir / "dwi" / "scalars"
                / f"pipeline-{pipeline}" / f"atlas-{atlas}"
            )
            fname = (
                f"{prefix}_atlas-{atlas}_pipeline-{pipeline}"
                f"_model-{model}_param-{param}"
                f"_desc-parcellated_diffmetrics.tsv"
            )
            # Reorder: leading columns first, then remaining stats columns
            stat_cols = [
                c for c in df.columns
                if c not in _SCALAR_LEADING_COLS + ["model", "param", "pipeline"]
            ]
            ordered_cols = _SCALAR_LEADING_COLS + stat_cols + ["model", "param", "pipeline"]
            ordered_cols = [c for c in ordered_cols if c in df.columns]
            write_tsv(df[ordered_cols], out_dir / fname)
            written += 1
        return written

    # ------------------------------------------------------------------
    # Connectivity extraction
    # ------------------------------------------------------------------

    def extract_connectivity(
        self,
        atlas: str,
        measure: str = "sift2",
    ) -> tuple[np.ndarray, list[str]]:
        """Extract a connectivity matrix for a given atlas.

        For component atlases (e.g. ``schaefer400x7``), the full combined
        segmentation matrix is returned — NOT a sub-matrix — because
        cross-system connections (cortical↔subcortical) are scientifically
        meaningful.  The labels returned correspond to all parcels in the
        combined seg.

        Parameters
        ----------
        atlas:
            Atlas key from the registry.
        measure:
            Connectivity measure key to extract from the .mat file.
            Common keys: ``"sift2"``, ``"count"``, ``"meanlength"``.

        Returns
        -------
        matrix : np.ndarray
            Shape ``(N_parcels, N_parcels)``.  For component atlases this is
            the full combined matrix (e.g. 432×432 for Schaefer400+TianS2).
        labels : list[str]
            Ordered region labels matching matrix rows/columns.
        combined_atlas_key : str
            Registry key of the combined atlas whose seg was used.  Equals
            ``atlas`` when the atlas has its own standalone seg.
        pipeline : str
            The QSIRecon workflow name (e.g. ``"MRtrix3_act-HSVS"``).

        Raises
        ------
        FileNotFoundError
            If no connectivity .mat file is found.
        KeyError
            If the measure key is not found in the .mat file.
        """
        seg_name, _ = self._resolve_seg_and_filter(atlas)
        combined_key = self._combined_atlas_key_for(atlas)
        _, labels_dict = self._find_atlas_seg(seg_name)
        labels = [labels_dict[i] for i in sorted(labels_dict)]

        mat_path, pipeline = self._find_connectivity_mat()
        mat_data = scipy.io.loadmat(str(mat_path))

        matrix = _extract_mat_matrix(mat_data, measure, expected_size=len(labels))

        return matrix, labels, combined_key, pipeline

    def _extract_and_write_connectivity(
        self,
        atlas: str,
        written_combined: set[str],
    ) -> int:
        """Extract connectivity for an atlas and write .npy + labels JSON.

        For component atlases (e.g. ``schaefer400x7``), the output is written
        under the combined atlas key (e.g. ``schaefer400x7_tian_s2``) so that
        the full cross-system matrix is preserved.  If the combined atlas key
        has already been written in this session (tracked via ``written_combined``),
        this is a no-op.

        Returns number of files written.
        """
        combined_key = self._combined_atlas_key_for(atlas)

        # Avoid writing the same combined matrix more than once per session
        if combined_key in written_combined:
            return 0

        prefix = f"{self.subject}_{self.session}"

        seg_name, _ = self._resolve_seg_and_filter(atlas)
        _, labels_dict = self._find_atlas_seg(seg_name)
        labels = [labels_dict[i] for i in sorted(labels_dict)]

        mat_path, pipeline = self._find_connectivity_mat()
        mat_data = scipy.io.loadmat(str(mat_path))

        # Find all square matrices in the .mat file
        matrices = _find_all_matrices(mat_data, expected_size=len(labels))
        written = 0

        out_dir = (
            self.output_dir / "dwi" / "connectivity"
            / f"pipeline-{pipeline}" / f"atlas-{combined_key}"
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        for measure, matrix in matrices.items():
            npy_name = (
                f"{prefix}_atlas-{combined_key}_pipeline-{pipeline}"
                f"_desc-{measure}_connmatrix.npy"
            )
            labels_name = (
                f"{prefix}_atlas-{combined_key}_pipeline-{pipeline}"
                f"_desc-{measure}_connmatrix-labels.json"
            )
            np.save(str(out_dir / npy_name), matrix)
            (out_dir / labels_name).write_text(json.dumps(labels, indent=2))
            written += 2  # .npy + labels JSON

        if written:
            written_combined.add(combined_key)

        return written

    # ------------------------------------------------------------------
    # Tract profiles
    # ------------------------------------------------------------------

    def extract_tract_profiles(self) -> list[pd.DataFrame]:
        """Extract pyAFQ tract profiles if present.

        Returns an empty list — pyAFQ tract profile CSVs are not yet available
        in the current pipeline outputs.
        """
        return []

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_seg_and_filter(
        self,
        atlas: str,
    ) -> tuple[str, Any]:
        """Return ``(qsirecon_seg_name, label_filter)`` for an atlas.

        For atlases with a direct ``qsirecon_seg_name`` (combined, standalone
        volumetric), returns ``(seg_name, None)`` — all labels are used.

        For component atlases (surface Schaefer, volumetric Tian without a
        standalone seg), finds the first available combined atlas on disk and
        returns its seg name together with the appropriate label-filter callable.

        Raises
        ------
        FileNotFoundError
            If the atlas has no standalone seg and no combined atlas is found.
        ValueError
            If the atlas has no QSIRecon representation at all.
        """
        meta = get_atlas(atlas)

        # Atlas has its own seg file
        if "qsirecon_seg_name" in meta:
            return meta["qsirecon_seg_name"], None

        # Atlas is a component — find available combined atlas on disk
        combined_keys = get_containing_combined_atlases(atlas)
        if not combined_keys:
            raise ValueError(
                f"Atlas {atlas!r} has no qsirecon_seg_name and no qsirecon_component_of — "
                "cannot extract from QSIRecon outputs."
            )

        dwi_dir = self._session_dwi_dir()
        for combined_key in combined_keys:
            combined_meta = get_atlas(combined_key)
            seg_name = combined_meta.get("qsirecon_seg_name", "")
            candidates = list(dwi_dir.glob(f"*_seg-{seg_name}_dseg.nii.gz")) if dwi_dir.exists() else []
            if candidates:
                label_filter = build_label_filter(atlas)
                return seg_name, label_filter

        # None found — raise with helpful message
        tried = [get_atlas(k).get("qsirecon_seg_name", k) for k in combined_keys]
        raise FileNotFoundError(
            f"No combined atlas segmentation found for {atlas!r}. "
            f"Tried seg names: {tried} in {dwi_dir}"
        )

    def _combined_atlas_key_for(self, atlas: str) -> str:
        """Return the registry key used to name connectivity output files.

        For a direct atlas (has ``qsirecon_seg_name``), returns ``atlas`` itself.
        For a component atlas, returns the first available combined atlas key.
        """
        meta = get_atlas(atlas)
        if "qsirecon_seg_name" in meta:
            return atlas

        combined_keys = get_containing_combined_atlases(atlas)
        dwi_dir = self._session_dwi_dir()
        for combined_key in combined_keys:
            combined_meta = get_atlas(combined_key)
            seg_name = combined_meta.get("qsirecon_seg_name", "")
            candidates = list(dwi_dir.glob(f"*_seg-{seg_name}_dseg.nii.gz")) if dwi_dir.exists() else []
            if candidates:
                return combined_key

        # Fall back to first combined key (will fail at seg lookup stage anyway)
        return combined_keys[0] if combined_keys else atlas

    def _session_dwi_dir(self) -> Path:
        """Return the main session dwi directory (contains atlas dseg files)."""
        return self.qsirecon_dir / self.subject / self.session / "dwi"

    def _find_atlas_seg(self, seg_name: str) -> tuple[Path, dict[int, str]]:
        """Find the atlas segmentation NII and its label file.

        Searches in ``{qsirecon_dir}/{subject}/{session}/dwi/``.
        Prefers files without ``dir-AP`` prefix.

        Returns
        -------
        atlas_path : Path
        labels : dict[int, str]
            Maps integer label index → region label string.
        """
        dwi_dir = self._session_dwi_dir()
        if not dwi_dir.exists():
            raise FileNotFoundError(f"QSIRecon session dwi dir not found: {dwi_dir}")

        candidates = sorted(dwi_dir.glob(f"*_seg-{seg_name}_dseg.nii.gz"))
        if not candidates:
            raise FileNotFoundError(
                f"No atlas segmentation found for seg_name={seg_name!r} in {dwi_dir}"
            )
        no_dirap = [p for p in candidates if "dir-AP" not in p.name]
        atlas_path = no_dirap[0] if no_dirap else candidates[0]

        label_path = atlas_path.with_suffix("").with_suffix(".txt")
        if not label_path.exists():
            label_path = Path(str(atlas_path).replace("_dseg.nii.gz", "_dseg.txt"))
        if not label_path.exists():
            raise FileNotFoundError(f"Label file not found for {atlas_path}")

        labels = _parse_dseg_txt(label_path)
        return atlas_path, labels

    def _find_scalar_maps(self) -> list[tuple[Path, str, str, str]]:
        """Glob for all scalar dwimap NII files across all pipeline subdirs.

        Returns
        -------
        list of (path, pipeline_name, model, param)
        """
        derivatives_dir = self.qsirecon_dir / "derivatives"
        if not derivatives_dir.exists():
            return []

        found: dict[tuple[str, str, str], tuple[Path, str]] = {}

        for pipeline_dir in sorted(derivatives_dir.glob("qsirecon-*")):
            pipeline_name = pipeline_dir.name.replace("qsirecon-", "")
            session_dwi = pipeline_dir / self.subject / self.session / "dwi"
            if not session_dwi.exists():
                continue

            for nii_path in sorted(session_dwi.glob("*_model-*_param-*_dwimap.nii.gz")):
                model, param = _parse_model_param(nii_path.name)
                if model is None or param is None:
                    continue
                key = (pipeline_name, model, param)
                if key not in found or "dir-AP" not in nii_path.name:
                    found[key] = (nii_path, pipeline_name)

        return [(path, pipeline, model, param) for (pipeline, model, param), (path, _) in found.items()]

    def _find_connectivity_mat(self) -> tuple[Path, str]:
        """Find the MRtrix3 connectivity .mat file for this session.

        Returns
        -------
        mat_path : Path
        pipeline : str
            The workflow name (e.g. ``"MRtrix3_act-HSVS"``).
        """
        candidates: list[tuple[Path, str]] = []

        # Prefer MRtrix3 pipeline
        mrtrix_pipeline = self.qsirecon_dir / "derivatives" / "qsirecon-MRtrix3_act-HSVS"
        session_dwi = mrtrix_pipeline / self.subject / self.session / "dwi"
        if session_dwi.exists():
            for p in sorted(session_dwi.glob("*_connectivity.mat")):
                candidates.append((p, "MRtrix3_act-HSVS"))

        if not candidates:
            derivatives_dir = self.qsirecon_dir / "derivatives"
            if derivatives_dir.exists():
                for pipeline_dir in sorted(derivatives_dir.glob("qsirecon-*")):
                    pipeline_name = pipeline_dir.name.replace("qsirecon-", "")
                    sd = pipeline_dir / self.subject / self.session / "dwi"
                    if sd.exists():
                        for p in sorted(sd.glob("*_connectivity.mat")):
                            candidates.append((p, pipeline_name))

        if not candidates:
            raise FileNotFoundError(
                f"No connectivity .mat file found for {self.subject}/{self.session}"
            )

        no_dirap = [(p, pl) for p, pl in candidates if "dir-AP" not in p.name]
        return no_dirap[0] if no_dirap else candidates[0]


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _parse_dseg_txt(label_path: Path) -> dict[int, str]:
    """Parse a ``*_dseg.txt`` file into a dict of index → label name.

    File format (tab-separated)::

        1\\tLH_Vis_1
        2\\tLH_Vis_2
        ...
    """
    labels: dict[int, str] = {}
    with open(label_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                try:
                    idx = int(parts[0])
                    name = parts[1].strip()
                    labels[idx] = name
                except (ValueError, IndexError):
                    continue
    return labels


def _parse_model_param(filename: str) -> tuple[str | None, str | None]:
    """Extract model and param BIDS entities from a dwimap filename."""
    import re
    model_m = re.search(r"_model-([^_]+)", filename)
    param_m = re.search(r"_param-([^_]+)", filename)
    model = model_m.group(1) if model_m else None
    param = param_m.group(1) if param_m else None
    return model, param


def _label_hemisphere(label: str) -> str:
    """Infer hemisphere from a region label string."""
    upper = label.upper()
    if upper.startswith("LH_") or "_LH_" in upper or upper.endswith("-LH"):
        return "L"
    if upper.startswith("RH_") or "_RH_" in upper or upper.endswith("-RH"):
        return "R"
    return "bilateral"


def _extract_mat_matrix(
    mat_data: dict,
    measure: str,
    expected_size: int,
) -> np.ndarray:
    """Extract a named square matrix from a loaded .mat file dict."""
    if measure in mat_data:
        arr = np.array(mat_data[measure], dtype=np.float64)
        if arr.ndim == 2 and arr.shape[0] == arr.shape[1]:
            return arr

    for key, val in mat_data.items():
        if key.startswith("_"):
            continue
        if key.lower() == measure.lower():
            arr = np.array(val, dtype=np.float64)
            if arr.ndim == 2 and arr.shape[0] == arr.shape[1]:
                return arr

    for key, val in mat_data.items():
        if key.startswith("_"):
            continue
        try:
            arr = np.array(val, dtype=np.float64)
            if arr.ndim == 2 and arr.shape[0] == arr.shape[1] == expected_size:
                return arr
        except (ValueError, TypeError):
            continue

    raise KeyError(
        f"Measure {measure!r} not found in .mat file. "
        f"Available keys: {[k for k in mat_data if not k.startswith('_')]}"
    )


def _find_all_matrices(
    mat_data: dict,
    expected_size: int,
) -> dict[str, np.ndarray]:
    """Return all square matrices from a .mat file, keyed by their variable name."""
    result: dict[str, np.ndarray] = {}
    for key, val in mat_data.items():
        if key.startswith("_"):
            continue
        try:
            arr = np.array(val, dtype=np.float64)
            if arr.ndim == 2 and arr.shape[0] == arr.shape[1]:
                if expected_size <= 0 or arr.shape[0] == expected_size:
                    result[key] = arr
        except (ValueError, TypeError):
            continue
    return result
