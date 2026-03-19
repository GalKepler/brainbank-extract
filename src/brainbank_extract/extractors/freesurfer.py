"""FreeSurfer morphometric extractor."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from brainbank_extract import __version__
from brainbank_extract.atlases import get_atlas
from brainbank_extract.io import write_status_json, write_tsv

logger = logging.getLogger(__name__)

# Short measure names in aseg.stats header → output metric key
_GLOBAL_MEASURE_MAP: dict[str, str] = {
    "BrainSeg": "BrainSegVol",
    "BrainSegNotVent": "BrainSegVolNotVent",
    "lhCortex": "lhCortexVol",
    "rhCortex": "rhCortexVol",
    "SubCortGray": "SubCortGrayVol",
    "WM": "CerebralWhiteMatterVol",
    "Mask": "MaskVol",
    "EstimatedTotalIntraCranialVol": "eTIV",
}

# fsatlas cortical measure names → brainbank metric names
_FSATLAS_MEASURE_MAP: dict[str, str] = {
    "thickness_mean_mm": "thickness",
    "surface_area_mm2": "area",
    "gray_matter_volume_mm3": "volume",
    "mean_curvature": "curvature",
}

# fsatlas volumetric measure names → brainbank metric names
_FSATLAS_VOLUMETRIC_MEASURE_MAP: dict[str, str] = {
    "volume_mm3": "volume",
}

# fsatlas hemisphere labels → brainbank hemisphere codes
_FSATLAS_HEMI_MAP: dict[str, str] = {
    "lh": "L",
    "rh": "R",
    "bilateral": "bilateral",
}


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

    # ------------------------------------------------------------------
    # Public orchestrator
    # ------------------------------------------------------------------

    def extract(self) -> dict:
        """Run all FreeSurfer extractions for this session.

        Returns
        -------
        dict
            Status summary written to ``_status.json`` in the output directory.
        """
        warnings: list[str] = []
        atlases_extracted: list[str] = []
        atlases_skipped: list[str] = []
        n_files = 0

        if not self.freesurfer_dir.exists():
            msg = f"FreeSurfer directory not found: {self.freesurfer_dir}"
            logger.warning(msg)
            status = {
                "subject": self.subject,
                "session": self.session,
                "extraction_date": datetime.now().isoformat(),
                "brainbank_extract_version": __version__,
                "atlases_extracted": [],
                "atlases_skipped": self.atlases,
                "modalities": {"anat": {"status": "error", "n_files": 0}},
                "warnings": [msg],
            }
            write_status_json(status, self.output_dir / "_status.json")
            return status

        anat_dir = self.output_dir / "anat"
        prefix = f"{self.subject}_{self.session}"

        # Global metrics (always attempted)
        try:
            df = self.extract_global_metrics()
            write_tsv(df, anat_dir / f"{prefix}_desc-globalmetrics_morph.tsv")
            n_files += 1
        except Exception as exc:
            warnings.append(f"Global metrics failed: {exc}")
            logger.warning("Global metrics extraction failed: %s", exc)

        # aseg subcortical volumes
        if "aseg" in self.atlases:
            try:
                df = self.extract_aseg()
                write_tsv(df, anat_dir / "atlas-dseg" / f"{prefix}_atlas-aseg_desc-subcortical_morph.tsv")
                atlases_extracted.append("aseg")
                n_files += 1
            except Exception as exc:
                atlases_skipped.append("aseg")
                warnings.append(f"aseg extraction failed: {exc}")
                logger.warning("aseg extraction failed: %s", exc)

        # Surface and combined atlases via fsatlas
        for atlas in self.atlases:
            if atlas == "aseg":
                continue

            try:
                atlas_meta = get_atlas(atlas)
            except KeyError:
                atlases_skipped.append(atlas)
                warnings.append(f"Atlas '{atlas}' not found in registry")
                continue

            has_components = (
                atlas_meta.get("type") == "combined"
                and "components" in atlas_meta
            )
            fsatlas_name = atlas_meta.get("fsatlas_name")

            if has_components:
                # Combined atlas: extract each component that has an fsatlas_name
                atlas_files_written = 0
                try:
                    component_results = self._extract_combined_atlas(atlas)
                    for (component_key, metric), df in component_results.items():
                        fname = f"{prefix}_atlas-{component_key}_desc-{metric}_morph.tsv"
                        write_tsv(df, anat_dir / f"atlas-{component_key}" / fname)
                        atlas_files_written += 1
                        n_files += 1
                        if component_key not in atlases_extracted:
                            atlases_extracted.append(component_key)
                    if atlas_files_written > 0 and atlas not in atlases_extracted:
                        atlases_extracted.append(atlas)
                    elif atlas_files_written == 0:
                        atlases_skipped.append(atlas)
                        warnings.append(
                            f"Atlas '{atlas}' combined extraction produced no output"
                        )
                except Exception as exc:
                    atlases_skipped.append(atlas)
                    warnings.append(f"Atlas '{atlas}' combined extraction failed: {exc}")
                    logger.warning("Atlas '%s' combined extraction failed: %s", atlas, exc)

            elif fsatlas_name is not None:
                # Direct surface or volumetric atlas via fsatlas
                atlas_files_written = 0
                try:
                    metrics_dict = self._extract_with_fsatlas(atlas)
                    for metric, df in metrics_dict.items():
                        fname = f"{prefix}_atlas-{atlas}_desc-{metric}_morph.tsv"
                        write_tsv(df, anat_dir / f"atlas-{atlas}" / fname)
                        atlas_files_written += 1
                        n_files += 1
                    if atlas_files_written > 0:
                        atlases_extracted.append(atlas)
                    else:
                        atlases_skipped.append(atlas)
                        warnings.append(f"Atlas '{atlas}' produced no output from fsatlas")
                except Exception as exc:
                    atlases_skipped.append(atlas)
                    warnings.append(f"Atlas '{atlas}' extraction failed: {exc}")
                    logger.warning("Atlas '%s' extraction failed: %s", atlas, exc)

            else:
                atlases_skipped.append(atlas)
                warnings.append(
                    f"Atlas '{atlas}' has no fsatlas_name and no decomposable components"
                    " — skipping FreeSurfer extraction"
                )

        status = {
            "subject": self.subject,
            "session": self.session,
            "extraction_date": datetime.now().isoformat(),
            "brainbank_extract_version": __version__,
            "atlases_extracted": atlases_extracted,
            "atlases_skipped": atlases_skipped,
            "modalities": {
                "anat": {
                    "status": "complete" if n_files > 0 else "failed",
                    "n_files": n_files,
                },
            },
            "warnings": warnings,
        }
        write_status_json(status, self.output_dir / "_status.json")
        return status

    # ------------------------------------------------------------------
    # Combined atlas extraction
    # ------------------------------------------------------------------

    def _extract_combined_atlas(
        self, atlas: str
    ) -> dict[tuple[str, str], pd.DataFrame]:
        """Extract morphometrics for a combined atlas by decomposing into components.

        For each component of the combined atlas that has an ``fsatlas_name``,
        calls :meth:`_extract_with_fsatlas` to extract its morphometrics.
        Components without an ``fsatlas_name`` (e.g. subcortical-only) are
        skipped with an info log — they require volumetric NIfTI extraction
        which is not yet implemented.

        Parameters
        ----------
        atlas:
            Registry key of the combined atlas (must have ``"components"`` field).

        Returns
        -------
        dict[tuple[str, str], pd.DataFrame]
            Keys are ``(component_key, metric_name)`` tuples. Each value is a
            DataFrame with columns:
            ``region_index``, ``region_label``, ``hemisphere``, ``value``, ``metric``.
        """
        atlas_meta = get_atlas(atlas)
        components = atlas_meta.get("components", {})
        result: dict[tuple[str, str], pd.DataFrame] = {}

        for component_key in components:
            try:
                component_meta = get_atlas(component_key)
            except KeyError:
                logger.warning(
                    "Combined atlas '%s' references unknown component '%s', skipping",
                    atlas, component_key,
                )
                continue

            if not component_meta.get("fsatlas_name"):
                logger.info(
                    "Component '%s' of atlas '%s' has no fsatlas_name — "
                    "skipping FreeSurfer extraction (requires volumetric NIfTI path)",
                    component_key, atlas,
                )
                continue

            try:
                metrics_dict = self._extract_with_fsatlas(component_key)
                for metric, df in metrics_dict.items():
                    result[(component_key, metric)] = df
            except Exception as exc:
                logger.warning(
                    "Component '%s' extraction failed: %s", component_key, exc
                )

        return result

    # ------------------------------------------------------------------
    # fsatlas-based extraction
    # ------------------------------------------------------------------

    def _extract_with_fsatlas(self, atlas: str) -> dict[str, pd.DataFrame]:
        """Extract morphometrics using fsatlas.

        For volumetric atlases, first tries to parse an existing
        ``.subcortical.stats`` file directly.  Falls back to running fsatlas
        (ensuring the atlas data is downloaded and forcing regeneration when
        the stats file contains generic ``Seg####`` region names).

        Parameters
        ----------
        atlas:
            Atlas key from the registry (must have ``fsatlas_name``).

        Returns
        -------
        dict[str, pd.DataFrame]
            Keys are metric names. Each DataFrame has columns:
            ``region_index``, ``region_label``, ``hemisphere``, ``value``, ``metric``.

        Raises
        ------
        Exception
            If FreeSurfer is not available, atlas transfer fails, or extraction fails.
        """
        from fsatlas.atlases.registry import AtlasRegistry  # type: ignore[import]
        from fsatlas.core.environment import FreeSurferEnv  # type: ignore[import]
        from fsatlas.core.extract import (  # type: ignore[import]
            extract_cortical_stats,
            extract_volumetric_stats,
        )
        from fsatlas.core.transfer import transfer_atlas  # type: ignore[import]

        atlas_meta = get_atlas(atlas)
        fsatlas_name = atlas_meta["fsatlas_name"]

        env = FreeSurferEnv.detect(subjects_dir=self.freesurfer_dir.parent)
        subject = env.find_subject(self.freesurfer_dir.name)
        reg = AtlasRegistry()
        atlas_spec = reg.get(fsatlas_name)

        if atlas_spec.type == "surface":
            transfer_result = transfer_atlas(atlas_spec, subject, env)
            df = extract_cortical_stats(atlas_spec, subject, env, transfer_result)
            return _fsatlas_cortical_to_brainbank(df)

        # -- Volumetric atlas --
        # Approach 2: try parsing existing stats file directly
        stats_path = self.freesurfer_dir / "stats" / f"{fsatlas_name}.subcortical.stats"
        if stats_path.exists():
            result = _parse_volumetric_stats_file(stats_path)
            if result is not None:
                logger.info("Parsed volumetric stats directly from %s", stats_path)
                return result
            logger.info(
                "Stats file %s has generic region names, will regenerate via fsatlas",
                stats_path,
            )

        # Approach 1: run fsatlas (ensure atlas is downloaded for ctab)
        if not atlas_spec.is_downloaded():
            logger.info("Downloading atlas %s for label data", fsatlas_name)
            atlas_spec = reg.download(fsatlas_name)

        transfer_result = transfer_atlas(atlas_spec, subject, env)

        # Force regeneration if existing stats file had generic names
        force = stats_path.exists()
        df = extract_volumetric_stats(
            atlas_spec, subject, env, transfer_result, force=force,
        )
        return _fsatlas_volumetric_to_brainbank(df)

    # ------------------------------------------------------------------
    # Stats file parsers (unchanged)
    # ------------------------------------------------------------------

    def extract_global_metrics(self) -> pd.DataFrame:
        """Parse global metrics from the ``aseg.stats`` header.

        Returns
        -------
        pd.DataFrame
            Columns: ``metric``, ``value``, ``source``.
        """
        aseg_path = self.freesurfer_dir / "stats" / "aseg.stats"
        if not aseg_path.exists():
            raise FileNotFoundError(f"aseg.stats not found: {aseg_path}")

        rows = []
        pattern = re.compile(
            r"^# Measure (\w+),\s+\S+,\s+[^,]+,\s+([\d.]+),\s+mm"
        )
        with open(aseg_path) as f:
            for line in f:
                m = pattern.match(line)
                if m:
                    short_name, value_str = m.group(1), m.group(2)
                    if short_name in _GLOBAL_MEASURE_MAP:
                        rows.append(
                            {
                                "metric": _GLOBAL_MEASURE_MAP[short_name],
                                "value": float(value_str),
                                "source": "freesurfer",
                            }
                        )

        if not rows:
            raise ValueError(f"No global metrics found in {aseg_path}")
        return pd.DataFrame(rows, columns=["metric", "value", "source"])

    def extract_aseg(self) -> pd.DataFrame:
        """Parse subcortical volumes from ``stats/aseg.stats``.

        Returns
        -------
        pd.DataFrame
            Columns: ``region_index``, ``region_label``, ``hemisphere``,
            ``value``, ``metric``.
        """
        aseg_path = self.freesurfer_dir / "stats" / "aseg.stats"
        if not aseg_path.exists():
            raise FileNotFoundError(f"aseg.stats not found: {aseg_path}")

        rows = []
        in_data = False
        with open(aseg_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("# ColHeaders"):
                    in_data = True
                    continue
                if not in_data or line.startswith("#") or not line:
                    continue
                parts = line.split()
                if len(parts) < 5:
                    continue
                seg_id = int(parts[1])
                volume = float(parts[3])
                struct_name = parts[4]
                hemisphere = _aseg_hemisphere(struct_name)
                rows.append(
                    {
                        "region_index": seg_id,
                        "region_label": struct_name,
                        "hemisphere": hemisphere,
                        "value": volume,
                        "metric": "volume",
                    }
                )

        if not rows:
            raise ValueError(f"No segmentation data found in {aseg_path}")
        return pd.DataFrame(
            rows,
            columns=["region_index", "region_label", "hemisphere", "value", "metric"],
        )


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _fsatlas_cortical_to_brainbank(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Convert fsatlas long-format cortical stats to per-metric brainbank DataFrames.

    Parameters
    ----------
    df:
        Long-format DataFrame from ``extract_cortical_stats()`` with columns:
        ``subject_id``, ``atlas``, ``hemisphere``, ``region``, ``measure``, ``value``.

    Returns
    -------
    dict[str, pd.DataFrame]
        Keys are brainbank metric names. Each DataFrame has columns:
        ``region_index``, ``region_label``, ``hemisphere``, ``value``, ``metric``.
    """
    df = df[df["measure"].isin(_FSATLAS_MEASURE_MAP)].copy()
    if df.empty:
        return {}

    df["hemisphere"] = df["hemisphere"].map(_FSATLAS_HEMI_MAP).fillna("bilateral")
    df["metric"] = df["measure"].map(_FSATLAS_MEASURE_MAP)

    # Assign consistent 1-based region_index across all metrics
    unique_regions = (
        df[["region", "hemisphere"]]
        .drop_duplicates()
        .sort_values(["hemisphere", "region"])
        .reset_index(drop=True)
    )
    unique_regions["region_index"] = unique_regions.index + 1

    df = df.merge(unique_regions, on=["region", "hemisphere"])
    df = df.rename(columns={"region": "region_label"})

    result: dict[str, pd.DataFrame] = {}
    cols = ["region_index", "region_label", "hemisphere", "value", "metric"]
    for metric, group in df.groupby("metric"):
        result[metric] = group[cols].reset_index(drop=True)

    return result


def _fsatlas_volumetric_to_brainbank(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Convert fsatlas long-format volumetric stats to per-metric brainbank DataFrames.

    Parameters
    ----------
    df:
        Long-format DataFrame from ``extract_volumetric_stats()`` with columns:
        ``subject_id``, ``atlas``, ``hemisphere``, ``region``, ``measure``, ``value``.

    Returns
    -------
    dict[str, pd.DataFrame]
        Keys are brainbank metric names (e.g. ``"volume"``). Each DataFrame has
        columns: ``region_index``, ``region_label``, ``hemisphere``, ``value``, ``metric``.
    """
    df = df[df["measure"].isin(_FSATLAS_VOLUMETRIC_MEASURE_MAP)].copy()
    if df.empty:
        return {}

    df["hemisphere"] = df["hemisphere"].map(_FSATLAS_HEMI_MAP).fillna("bilateral")
    df["metric"] = df["measure"].map(_FSATLAS_VOLUMETRIC_MEASURE_MAP)

    unique_regions = (
        df[["region", "hemisphere"]]
        .drop_duplicates()
        .sort_values(["hemisphere", "region"])
        .reset_index(drop=True)
    )
    unique_regions["region_index"] = unique_regions.index + 1

    df = df.merge(unique_regions, on=["region", "hemisphere"])
    df = df.rename(columns={"region": "region_label"})

    result: dict[str, pd.DataFrame] = {}
    cols = ["region_index", "region_label", "hemisphere", "value", "metric"]
    for metric, group in df.groupby("metric"):
        result[metric] = group[cols].reset_index(drop=True)

    return result


def _parse_volumetric_stats_file(
    stats_path: Path,
) -> dict[str, pd.DataFrame] | None:
    """Parse a ``mri_segstats`` ``.subcortical.stats`` file directly.

    Returns ``None`` if the file contains generic ``Seg####`` region names
    (meaning it was generated without a proper color table).

    Returns
    -------
    dict[str, pd.DataFrame] or None
        Keys are metric names (``"volume"``).  Each DataFrame has columns:
        ``region_index``, ``region_label``, ``hemisphere``, ``value``, ``metric``.
    """
    rows: list[dict] = []
    in_data = False
    with open(stats_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("# ColHeaders"):
                in_data = True
                continue
            if not in_data or line.startswith("#") or not line:
                continue
            parts = line.split()
            if len(parts) < 5:
                continue
            seg_id = int(parts[1])
            volume = float(parts[3])
            struct_name = parts[4]
            # Bail out if names are generic (no ctab was used)
            if re.match(r"^Seg\d+$", struct_name):
                return None
            hemisphere = _infer_hemisphere(struct_name)
            rows.append(
                {
                    "region_index": seg_id,
                    "region_label": struct_name,
                    "hemisphere": hemisphere,
                    "value": volume,
                    "metric": "volume",
                }
            )

    if not rows:
        return None

    df = pd.DataFrame(
        rows,
        columns=["region_index", "region_label", "hemisphere", "value", "metric"],
    )
    return {"volume": df}


def _infer_hemisphere(struct_name: str) -> str:
    """Infer hemisphere from a structure name.

    Handles conventions used by aseg (``Left-``, ``Right-``), Tian
    (``-lh``, ``-rh`` suffix), and other atlases.
    """
    name = struct_name.lower()
    # Prefix patterns (aseg, some cortical atlases)
    if name.startswith(("left-", "left_", "lh.", "lh-", "lh_", "l-", "l_")):
        return "L"
    if name.startswith(("right-", "right_", "rh.", "rh-", "rh_", "r-", "r_")):
        return "R"
    # Infix patterns
    if "-lh-" in name or "_lh_" in name:
        return "L"
    if "-rh-" in name or "_rh_" in name:
        return "R"
    # Suffix patterns (Tian atlas: HIP-rh, CAU-lh)
    if name.endswith(("-lh", "_lh")):
        return "L"
    if name.endswith(("-rh", "_rh")):
        return "R"
    return "bilateral"


def _aseg_hemisphere(struct_name: str) -> str:
    """Infer hemisphere label from an aseg structure name."""
    return _infer_hemisphere(struct_name)
