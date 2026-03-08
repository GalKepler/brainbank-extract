"""FreeSurfer morphometric extractor."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

import nibabel.freesurfer.io as fsio
import numpy as np
import pandas as pd

from brainbank_extract import __version__
from brainbank_extract.atlases import get_atlas
from brainbank_extract.io import write_status_json, write_tsv

logger = logging.getLogger(__name__)

# Metrics extracted from per-vertex surface files.
# area is summed per parcel; all others are meaned.
_SURFACE_METRICS: dict[str, str] = {
    "thickness": "thickness",
    "area": "area",
    "curvature": "curv",
    "sulc": "sulc",
}

# Mapping from stats-file column name → output metric key
# Columns in FreeSurfer surface stats files:
# StructName NumVert SurfArea GrayVol ThickAvg ThickStd MeanCurv GausCurv FoldInd CurvInd
_STATS_COL_TO_METRIC: dict[str, str] = {
    "SurfArea": "area",
    "GrayVol": "volume",
    "ThickAvg": "thickness",
    "MeanCurv": "curvature",
}

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

# Region names to skip when parcellating (FreeSurfer pseudo-labels)
_SKIP_REGIONS = frozenset({"unknown", "corpuscallosum", "medialwall"})

# Substrings that mark pseudo-regions to skip in stats files
_SKIP_SUBSTRINGS = ("FreeSurfer_Defined_Medial_Wall", "Background", "Medial_Wall")


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
                write_tsv(df, anat_dir / f"{prefix}_atlas-aseg_desc-subcortical_morph.tsv")
                atlases_extracted.append("aseg")
                n_files += 1
            except Exception as exc:
                atlases_skipped.append("aseg")
                warnings.append(f"aseg extraction failed: {exc}")
                logger.warning("aseg extraction failed: %s", exc)

        # Surface atlases: try stats-file path first, fall back to per-vertex
        for atlas in self.atlases:
            if atlas == "aseg":
                continue
            atlas_files_written = 0
            atlas_missing = False

            try:
                atlas_meta = get_atlas(atlas)
            except KeyError:
                atlases_skipped.append(atlas)
                warnings.append(f"Atlas '{atlas}' not found in registry")
                continue

            # Try stats-file extraction (primary path)
            stats_pattern = atlas_meta.get("freesurfer_stats_pattern")
            if stats_pattern is not None:
                try:
                    metrics_dict = self.extract_surface_stats(atlas)
                    for metric, df in metrics_dict.items():
                        fname = f"{prefix}_atlas-{atlas}_desc-{metric}_morph.tsv"
                        write_tsv(df, anat_dir / fname)
                        atlas_files_written += 1
                        n_files += 1
                    if atlas_files_written > 0:
                        atlases_extracted.append(atlas)
                    continue  # skip per-vertex fallback if stats worked
                except FileNotFoundError as exc:
                    msg = f"Atlas {atlas!r} stats file not found, trying per-vertex: {exc}"
                    warnings.append(msg)
                    logger.info(msg)
                except Exception as exc:
                    msg = f"Atlas {atlas!r} stats extraction failed: {exc}"
                    warnings.append(msg)
                    logger.warning(msg)

            # Fall back to per-vertex parcellation
            for metric in _SURFACE_METRICS:
                try:
                    df = self.extract_surface_morphometrics(atlas, metric)
                    fname = f"{prefix}_atlas-{atlas}_desc-{metric}_morph.tsv"
                    write_tsv(df, anat_dir / fname)
                    atlas_files_written += 1
                    n_files += 1
                except FileNotFoundError as exc:
                    msg = f"Atlas {atlas!r} metric {metric!r} skipped: {exc}"
                    warnings.append(msg)
                    logger.warning(msg)
                    atlas_missing = True
                except Exception as exc:
                    msg = f"Atlas {atlas!r} metric {metric!r} failed: {exc}"
                    warnings.append(msg)
                    logger.warning(msg)

            if atlas_files_written > 0:
                atlases_extracted.append(atlas)
            elif atlas_missing:
                atlases_skipped.append(atlas)

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
    # Stats file parsers
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

    def extract_surface_stats(self, atlas: str) -> dict[str, pd.DataFrame]:
        """Extract parcellated metrics from pre-computed FreeSurfer stats files.

        This is the primary extraction path when FreeSurfer has already computed
        parcellation statistics (e.g. via ``mris_anatomical_stats``). It reads
        the ``lh.*`` and ``rh.*`` stats files and extracts all four metrics at once:
        thickness (ThickAvg), area (SurfArea), volume (GrayVol), curvature (MeanCurv).

        Stats file column format::

            # ColHeaders StructName NumVert SurfArea GrayVol ThickAvg ThickStd MeanCurv ...
            7Networks_LH_Vis_1  713  471  1527  2.925  0.457  0.118  ...

        Parameters
        ----------
        atlas:
            Atlas key from the registry (must have ``freesurfer_stats_pattern``).

        Returns
        -------
        dict[str, pd.DataFrame]
            Keys are metric names (``"thickness"``, ``"area"``, ``"volume"``,
            ``"curvature"``). Each DataFrame has columns:
            ``region_index``, ``region_label``, ``hemisphere``, ``value``, ``metric``.

        Raises
        ------
        FileNotFoundError
            If the stats files do not exist.
        ValueError
            If no data rows are found or atlas lacks ``freesurfer_stats_pattern``.
        """
        atlas_meta = get_atlas(atlas)
        stats_pattern = atlas_meta.get("freesurfer_stats_pattern")
        if stats_pattern is None:
            raise ValueError(
                f"Atlas {atlas!r} has no freesurfer_stats_pattern — "
                "cannot extract from stats files."
            )

        # Accumulate rows per metric
        all_rows: dict[str, list[dict]] = {m: [] for m in _STATS_COL_TO_METRIC.values()}
        region_counter = 0

        # Determine if this is a bilateral stats file (no ?h. prefix) or hemisphere-specific
        is_bilateral = not stats_pattern.startswith("?h.")

        if is_bilateral:
            # Single stats file (e.g. Tian subcortical)
            stats_path = self.freesurfer_dir / "stats" / stats_pattern
            if not stats_path.exists():
                raise FileNotFoundError(f"Stats file not found: {stats_path}")
            rows_for_hemi, region_counter = _parse_stats_file(
                stats_path, hemi_label="bilateral", start_index=region_counter
            )
            for metric, rows in rows_for_hemi.items():
                all_rows[metric].extend(rows)
        else:
            # Hemisphere-specific stats files (lh.* and rh.*)
            for hemi, hemi_label in (("lh", "L"), ("rh", "R")):
                stats_name = stats_pattern.replace("?h", hemi)
                stats_path = self.freesurfer_dir / "stats" / stats_name
                if not stats_path.exists():
                    raise FileNotFoundError(f"Stats file not found: {stats_path}")
                rows_for_hemi, region_counter = _parse_stats_file(
                    stats_path, hemi_label=hemi_label, start_index=region_counter
                )
                for metric, rows in rows_for_hemi.items():
                    all_rows[metric].extend(rows)

        # Build DataFrames per metric
        result: dict[str, pd.DataFrame] = {}
        cols = ["region_index", "region_label", "hemisphere", "value", "metric"]
        for metric, rows in all_rows.items():
            if rows:
                result[metric] = pd.DataFrame(rows, columns=cols)

        if not result:
            raise ValueError(f"No parcels found in stats files for atlas {atlas!r}.")
        return result

    # ------------------------------------------------------------------
    # Surface parcellation (per-vertex fallback)
    # ------------------------------------------------------------------

    def extract_surface_morphometrics(
        self,
        atlas: str,
        metric: str,
    ) -> pd.DataFrame:
        """Extract parcellated surface morphometrics for a given atlas.

        Loads the atlas annotation file and per-vertex metric file, then
        computes per-parcel values (mean for thickness/curvature/sulc,
        sum for area).

        Parameters
        ----------
        atlas:
            Atlas key from the registry (e.g. ``"schaefer400x7"``).
        metric:
            One of ``"thickness"``, ``"area"``, ``"curvature"``, ``"sulc"``.

        Returns
        -------
        pd.DataFrame
            Columns: ``region_index``, ``region_label``, ``hemisphere``,
            ``value``, ``metric``.

        Raises
        ------
        FileNotFoundError
            If the annotation or metric file is not present.
        ValueError
            If the atlas type does not support surface parcellation.
        """
        if metric not in _SURFACE_METRICS:
            raise ValueError(
                f"Unsupported metric {metric!r}. "
                f"Supported: {list(_SURFACE_METRICS)}"
            )

        atlas_meta = get_atlas(atlas)
        if atlas_meta["type"] not in ("surface", "combined"):
            raise ValueError(
                f"Atlas {atlas!r} is type {atlas_meta['type']!r}; "
                "surface parcellation requires type 'surface' or 'combined'."
            )

        annot_pattern = atlas_meta.get("freesurfer_annot_pattern")
        if annot_pattern is None:
            raise FileNotFoundError(
                f"Atlas {atlas!r} has no freesurfer_annot_pattern — "
                "cannot extract from FreeSurfer surfaces."
            )

        surf_file = _SURFACE_METRICS[metric]
        rows = []

        for hemi, hemi_label in (("lh", "L"), ("rh", "R")):
            annot_name = annot_pattern.replace("?h", hemi)
            annot_path = self.freesurfer_dir / "label" / annot_name
            morph_path = self.freesurfer_dir / "surf" / f"{hemi}.{surf_file}"

            if not annot_path.exists():
                raise FileNotFoundError(
                    f"Annotation file not found: {annot_path}"
                )
            if not morph_path.exists():
                raise FileNotFoundError(
                    f"Surface metric file not found: {morph_path}"
                )

            vertex_labels, ctab, region_names = fsio.read_annot(str(annot_path))
            vertex_data = fsio.read_morph_data(str(morph_path))

            for i, name in enumerate(region_names):
                if isinstance(name, bytes):
                    name = name.decode("utf-8")
                if name.lower() in _SKIP_REGIONS:
                    continue

                mask = vertex_labels == i
                if not mask.any():
                    continue

                parcel_data = vertex_data[mask]
                value = float(np.sum(parcel_data) if metric == "area" else np.mean(parcel_data))
                region_index = int(ctab[i, 4]) if i < len(ctab) else i

                rows.append(
                    {
                        "region_index": region_index,
                        "region_label": name,
                        "hemisphere": hemi_label,
                        "value": value,
                        "metric": metric,
                    }
                )

        if not rows:
            raise ValueError(
                f"No parcels found for atlas {atlas!r} metric {metric!r}."
            )
        return pd.DataFrame(
            rows,
            columns=["region_index", "region_label", "hemisphere", "value", "metric"],
        )


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

def _parse_stats_file(
    stats_path: Path,
    hemi_label: str,
    start_index: int = 0,
) -> tuple[dict[str, list[dict]], int]:
    """Parse a FreeSurfer surface stats file and return per-metric rows.

    Parameters
    ----------
    stats_path:
        Path to the stats file (e.g. ``lh.schaefer400-7.stats``).
    hemi_label:
        Hemisphere label to assign: ``"L"``, ``"R"``, or ``"bilateral"``.
    start_index:
        Starting integer index for region_index (incremented per parcel).

    Returns
    -------
    rows_per_metric : dict[str, list[dict]]
        Maps metric name → list of row dicts.
    next_index : int
        Next region_index to use after this file.
    """
    rows_per_metric: dict[str, list[dict]] = {m: [] for m in _STATS_COL_TO_METRIC.values()}
    col_indices: dict[str, int] = {}
    region_counter = start_index

    with open(stats_path) as f:
        for line in f:
            stripped = line.strip()

            # Parse column headers
            if stripped.startswith("# ColHeaders"):
                headers = stripped.replace("# ColHeaders", "").split()
                for col_name, metric in _STATS_COL_TO_METRIC.items():
                    if col_name in headers:
                        col_indices[metric] = headers.index(col_name)
                continue

            # Skip comment lines and empty lines
            if stripped.startswith("#") or not stripped:
                continue

            # Data row
            parts = stripped.split()
            if not parts or not col_indices:
                continue

            struct_name = parts[0]

            # Skip pseudo-regions
            if any(skip in struct_name for skip in _SKIP_SUBSTRINGS):
                continue
            if struct_name.lower() in _SKIP_REGIONS:
                continue

            region_counter += 1

            # Determine hemisphere from struct name if file is bilateral
            effective_hemi = hemi_label
            if hemi_label == "bilateral":
                effective_hemi = _struct_hemisphere(struct_name)

            for metric, col_idx in col_indices.items():
                if col_idx < len(parts):
                    try:
                        value = float(parts[col_idx])
                    except ValueError:
                        continue
                    rows_per_metric[metric].append(
                        {
                            "region_index": region_counter,
                            "region_label": struct_name,
                            "hemisphere": effective_hemi,
                            "value": value,
                            "metric": metric,
                        }
                    )

    return rows_per_metric, region_counter


def _struct_hemisphere(struct_name: str) -> str:
    """Infer hemisphere from a parcel struct name (for bilateral stats files)."""
    upper = struct_name.upper()
    if "_LH_" in upper or upper.startswith("LH_"):
        return "L"
    if "_RH_" in upper or upper.startswith("RH_"):
        return "R"
    return "bilateral"


def _aseg_hemisphere(struct_name: str) -> str:
    """Infer hemisphere label from an aseg structure name."""
    name = struct_name.lower()
    if name.startswith("left-") or name.startswith("lh.") or "-lh-" in name:
        return "L"
    if name.startswith("right-") or name.startswith("rh.") or "-rh-" in name:
        return "R"
    return "bilateral"
