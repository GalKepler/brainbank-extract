"""Atlas registry: metadata for all supported brain parcellation atlases."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import pandas as pd

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
# Atlas types:
#   "surface"   — FreeSurfer cortical (per-vertex annotation); no standalone QSIRecon seg
#   "volumetric"— FreeSurfer volumetric (aseg / Tian); no standalone QSIRecon seg
#   "combined"  — QSIRecon combined seg (cortical + subcortical in one NIfTI)
#
# Component atlases (surface / volumetric) that appear inside a QSIRecon combined
# seg carry a "qsirecon_component_of" list pointing to registry keys of type
# "combined".  The combined atlas entry has a "components" dict that maps each
# component registry key to its label-filter spec.
#
# Label-filter specs (used to split parcels from a combined seg):
#   {"qsirecon_label_startswith": ["LH_", "RH_"]}  — keep labels starting with any prefix
#   {"qsirecon_label_exclude_startswith": ["LH_", "RH_"]}  — keep labels NOT starting with any
#   {"qsirecon_index_range": [lo, hi]}  — keep parcels with index in [lo, hi] inclusive

# ---------------------------------------------------------------------------
# Generator helpers
# ---------------------------------------------------------------------------

TIAN_PARCELS: dict[int, int] = {1: 16, 2: 32, 3: 50, 4: 54}
_TIAN_ROMAN: dict[int, str] = {1: "I", 2: "II", 3: "III", 4: "IV"}


def _build_schaefer_tian_entries() -> dict[str, dict]:
    """Generate all Schaefer component, Tian component, and Schaefer+Tian combined entries.

    Produces:
    - 10 Schaefer component entries (N100–N1000, 7-network)
    - 4 Tian component entries (S1–S4)
    - 40 Schaefer+Tian combined entries (every Schaefer × every Tian)
    """
    entries: dict[str, dict] = {}

    # Schaefer cortical component entries
    for n in range(100, 1100, 100):
        key = f"schaefer{n}x7"
        entries[key] = {
            "full_name": f"Schaefer 2018, {n} parcels, 7 networks",
            "type": "surface",
            "n_parcels": n,
            "freesurfer_annot_pattern": f"?h.schaefer{n}-7.annot",
            "freesurfer_stats_pattern": f"?h.schaefer{n}-7.stats",
            "fsatlas_name": f"schaefer{n}-7",
            # Appears as cortical component in all Schaefer+Tian combined atlases
            "qsirecon_component_of": [f"schaefer{n}x7_tian_s{s}" for s in range(1, 5)],
            "qsirecon_label_startswith": ["LH_", "RH_"],
        }

    # Tian subcortical component entries
    for s, np_ in TIAN_PARCELS.items():
        key = f"tian_s{s}"
        entries[key] = {
            "full_name": f"Tian 2020, Scale {_TIAN_ROMAN[s]}",
            "type": "volumetric",
            "n_parcels": np_,
            "fsatlas_name": f"tian-s{s}",
            # Appears as subcortical component in all Schaefer+Tian combined atlases
            "qsirecon_component_of": [
                f"schaefer{n}x7_tian_s{s}" for n in range(100, 1100, 100)
            ],
            "qsirecon_label_exclude_startswith": ["LH_", "RH_"],
        }

    # Schaefer+Tian combined entries (40 total)
    for n in range(100, 1100, 100):
        for s, tp in TIAN_PARCELS.items():
            combo = f"schaefer{n}x7_tian_s{s}"
            entries[combo] = {
                "full_name": (
                    f"Schaefer 2018 {n}-parcel 7-network + Tian 2020 Scale {_TIAN_ROMAN[s]}"
                ),
                "type": "combined",
                "n_parcels": n + tp,
                "qsirecon_seg_name": f"Schaefer2018N{n}n7Tian2020S{s}",
                "components": {
                    f"schaefer{n}x7": {"qsirecon_label_startswith": ["LH_", "RH_"]},
                    f"tian_s{s}": {"qsirecon_label_exclude_startswith": ["LH_", "RH_"]},
                },
            }

    return entries


def _build_4s_entries() -> dict[str, dict]:
    """Generate all 4S combined atlas entries (4S156–4S1056).

    The 4S atlas series pairs each Schaefer resolution (N100–N1000) with
    a fixed 56-parcel subcortical extension.
    """
    subcortical_count = 56
    entries: dict[str, dict] = {}
    for n in range(100, 1100, 100):
        total = n + subcortical_count
        key = f"4S{total}Parcels"
        entries[key] = {
            "full_name": f"4S {total} Parcels",
            "type": "combined",
            "n_parcels": total,
            "qsirecon_seg_name": key,
        }
    return entries


# ---------------------------------------------------------------------------
# Atlas registry
# ---------------------------------------------------------------------------

ATLAS_REGISTRY: dict[str, dict[str, Any]] = {
    # ------------------------------------------------------------------
    # Schaefer cortical (10 entries), Tian subcortical (4 entries),
    # and Schaefer+Tian combined (40 entries) — generated programmatically
    # ------------------------------------------------------------------
    **_build_schaefer_tian_entries(),

    # ------------------------------------------------------------------
    # 4S combined atlases (10 entries: 4S156–4S1056) — generated
    # ------------------------------------------------------------------
    **_build_4s_entries(),

    # ------------------------------------------------------------------
    # HCPex combined atlas (cortical HCP-MMP + subcortical extension)
    # ------------------------------------------------------------------
    # HCP-MMP cortical component (360 parcels, indices 1–360)
    "hcpmmp": {
        "full_name": "HCP Multi-Modal Parcellation (360 cortical parcels)",
        "type": "surface",
        "n_parcels": 360,
        "fsatlas_name": "hcp-mmp",
        "qsirecon_component_of": ["HCPex"],
        "qsirecon_index_range": [1, 360],
    },
    # HCPex subcortical component (66 parcels, indices 361–426)
    "hcpex_subcortical": {
        "full_name": "HCPex subcortical component (66 parcels)",
        "type": "volumetric",
        "n_parcels": 66,
        "qsirecon_component_of": ["HCPex"],
        "qsirecon_index_range": [361, 426],
    },
    # HCPex combined atlas (426 total parcels)
    "HCPex": {
        "full_name": "HCPex Atlas, 426 parcels",
        "type": "combined",
        "n_parcels": 426,
        "qsirecon_seg_name": "HCPex",
        "components": {
            "hcpmmp": {"qsirecon_index_range": [1, 360]},
            "hcpex_subcortical": {"qsirecon_index_range": [361, 426]},
        },
    },

    # ------------------------------------------------------------------
    # Gordon333Ext combined atlas
    # ------------------------------------------------------------------
    # Gordon333 cortical component (333 parcels, indices 1–333)
    # Note: index 334 is absent from the QSIRecon dseg file (gap between cortical/subcortical)
    "gordon333": {
        "full_name": "Gordon 2016, 333 parcels",
        "type": "surface",
        "n_parcels": 333,
        "freesurfer_annot_pattern": "?h.Gordon333.annot",
        "fsatlas_name": "gordon333",
        "qsirecon_component_of": ["gordon333ext"],
        "qsirecon_index_range": [1, 333],
    },
    # Gordon333 subcortical component (52 parcels, indices 335–386)
    "gordon333_subcortical": {
        "full_name": "Gordon333Ext subcortical component (52 parcels)",
        "type": "volumetric",
        "n_parcels": 52,
        "qsirecon_component_of": ["gordon333ext"],
        "qsirecon_index_range": [335, 386],
    },
    # Gordon333Ext combined (385 parcels: 333 cortical + 52 subcortical)
    "gordon333ext": {
        "full_name": "Gordon 2016 333-parcel + subcortical extension (385 total)",
        "type": "combined",
        "n_parcels": 385,
        "qsirecon_seg_name": "Gordon333Ext",
        "components": {
            "gordon333": {"qsirecon_index_range": [1, 333]},
            "gordon333_subcortical": {"qsirecon_index_range": [335, 386]},
        },
    },

    # ------------------------------------------------------------------
    # Brainnetome246Ext combined atlas
    # ------------------------------------------------------------------
    # Brainnetome246 cortical component (246 parcels, indices 1–246)
    # Note: index 247 is absent from the QSIRecon dseg file (gap)
    "brainnetome246": {
        "full_name": "Brainnetome Atlas, 246 cortical parcels",
        "type": "surface",
        "n_parcels": 246,
        "fsatlas_name": "BN_Atlas",
        "qsirecon_component_of": ["brainnetome246ext"],
        "qsirecon_index_range": [1, 246],
    },
    # Brainnetome246 subcortical component (10 parcels, indices 248–257)
    "brainnetome246_subcortical": {
        "full_name": "Brainnetome246Ext subcortical component (10 parcels)",
        "type": "volumetric",
        "n_parcels": 10,
        "qsirecon_component_of": ["brainnetome246ext"],
        "qsirecon_index_range": [248, 257],
    },
    # Brainnetome246Ext combined (256 parcels: 246 cortical + 10 subcortical)
    "brainnetome246ext": {
        "full_name": "Brainnetome Atlas 246-parcel + subcortical extension (256 total)",
        "type": "combined",
        "n_parcels": 256,
        "qsirecon_seg_name": "Brainnetome246Ext",
        "components": {
            "brainnetome246": {"qsirecon_index_range": [1, 246]},
            "brainnetome246_subcortical": {"qsirecon_index_range": [248, 257]},
        },
    },

    # ------------------------------------------------------------------
    # AICHA384Ext combined atlas
    # ------------------------------------------------------------------
    # AICHA384 cortical component (384 parcels, indices 1–384)
    # Note: index 385 is absent from the QSIRecon dseg file (gap)
    "aicha384": {
        "full_name": "AICHA 2015, 384 parcels",
        "type": "surface",
        "n_parcels": 384,
        "fsatlas_name": "aicha384",
        "qsirecon_component_of": ["aicha384ext"],
        "qsirecon_index_range": [1, 384],
    },
    # AICHA384 subcortical component (10 parcels, indices 386–395)
    "aicha384_subcortical": {
        "full_name": "AICHA384Ext subcortical component (10 parcels)",
        "type": "volumetric",
        "n_parcels": 10,
        "qsirecon_component_of": ["aicha384ext"],
        "qsirecon_index_range": [386, 395],
    },
    # AICHA384Ext combined (394 parcels: 384 cortical + 10 subcortical)
    "aicha384ext": {
        "full_name": "AICHA 2015 384-parcel + subcortical extension (394 total)",
        "type": "combined",
        "n_parcels": 394,
        "qsirecon_seg_name": "AICHA384Ext",
        "components": {
            "aicha384": {"qsirecon_index_range": [1, 384]},
            "aicha384_subcortical": {"qsirecon_index_range": [386, 395]},
        },
    },

    # ------------------------------------------------------------------
    # AAL116 standalone (surface extraction via fsatlas mri_vol2surf projection)
    # ------------------------------------------------------------------
    "aal116": {
        "full_name": "Automated Anatomical Labeling, 116 regions",
        "type": "surface",
        "n_parcels": 116,
        "fsatlas_name": "aal116",
        "qsirecon_seg_name": "AAL116",
    },

    # ------------------------------------------------------------------
    # Surface atlases (FreeSurfer default parcellations)
    # ------------------------------------------------------------------
    "desikan": {
        "full_name": "Desikan-Killiany (FreeSurfer default)",
        "type": "surface",
        "n_parcels": 68,
        "freesurfer_annot_pattern": "?h.aparc.annot",
        "freesurfer_stats_pattern": "?h.aparc.stats",
        "fsatlas_name": "desikan",
        "qsirecon_seg_name": "aparc",
    },
    "destrieux": {
        "full_name": "Destrieux (a2009s)",
        "type": "surface",
        "n_parcels": 148,
        "freesurfer_annot_pattern": "?h.aparc.a2009s.annot",
        "freesurfer_stats_pattern": "?h.aparc.a2009s.stats",
        "fsatlas_name": "destrieux",
        "qsirecon_seg_name": "aparc.a2009s",
    },

    # ------------------------------------------------------------------
    # FreeSurfer-only
    # ------------------------------------------------------------------
    "aseg": {
        "full_name": "FreeSurfer automatic subcortical segmentation",
        "type": "volumetric",
        "n_parcels": 45,
    },
}


# ---------------------------------------------------------------------------
# Atlas suites
# ---------------------------------------------------------------------------
# Suites are named collections of atlas keys for common use cases.
# Use resolve_atlases() to expand a mix of suite names and individual atlas
# keys into a deduplicated, ordered list of atlas registry keys.

ATLAS_SUITES: dict[str, list[str]] = {
    # Primary workhorse atlases — good balance of coverage and resolution.
    # Uses Schaefer100 + TianS2 for richer subcortical coverage over S1.
    "core": [
        "schaefer100x7_tian_s2",
        "4S156Parcels",
    ],
    # Extended set adds higher-resolution and alternative atlases.
    "extended": [
        "schaefer100x7_tian_s2",
        "4S156Parcels",
        "schaefer400x7_tian_s2",
        "4S456Parcels",
        "HCPex",
        "brainnetome246ext",
    ],
    # Full set: every atlas in the registry that can be extracted.
    "full": sorted(ATLAS_REGISTRY.keys()),
    # Cortical-only atlases (FreeSurfer surface parcellations).
    "cortical": [
        "schaefer100x7",
        "schaefer200x7",
        "schaefer400x7",
        "desikan",
        "destrieux",
    ],
    # Subcortical-only atlases.
    "subcortical": [
        "tian_s1",
        "tian_s2",
        "tian_s3",
        "tian_s4",
        "aseg",
    ],
}


# ---------------------------------------------------------------------------
# Core lookup
# ---------------------------------------------------------------------------

def get_atlas(name: str) -> dict[str, Any]:
    """Return atlas metadata by registry key.

    Raises
    ------
    KeyError
        If the atlas is not found in the registry.
    """
    if name not in ATLAS_REGISTRY:
        known = ", ".join(sorted(ATLAS_REGISTRY))
        raise KeyError(f"Atlas '{name}' not in registry. Known atlases: {known}")
    return ATLAS_REGISTRY[name]


def register_atlas(name: str, metadata: dict[str, Any]) -> None:
    """Register a custom atlas at runtime.

    Parameters
    ----------
    name:
        Short key for the atlas (e.g. ``"myatlas200"``).
    metadata:
        Dict with at minimum ``full_name``, ``type``, and ``n_parcels`` keys.
    """
    required = {"full_name", "type", "n_parcels"}
    missing = required - metadata.keys()
    if missing:
        raise ValueError(f"Atlas metadata missing required keys: {missing}")
    ATLAS_REGISTRY[name] = metadata


def list_atlases() -> list[str]:
    """Return sorted list of all registered atlas keys."""
    return sorted(ATLAS_REGISTRY)


# ---------------------------------------------------------------------------
# Suite helpers
# ---------------------------------------------------------------------------

def list_suites() -> list[str]:
    """Return sorted list of all defined suite names."""
    return sorted(ATLAS_SUITES)


def resolve_atlases(specs: list[str]) -> list[str]:
    """Expand a list of atlas keys and/or suite names into a deduplicated atlas list.

    Suite names are expanded to their constituent atlas keys. Individual atlas
    registry keys are passed through as-is. The returned list preserves the
    order of first appearance and contains no duplicates.

    Parameters
    ----------
    specs:
        List of atlas registry keys (e.g. ``"schaefer100x7"``) and/or suite
        names (e.g. ``"core"``). May be mixed freely.

    Returns
    -------
    list[str]
        Ordered, deduplicated list of atlas registry keys.

    Raises
    ------
    ValueError
        If any spec is neither a known suite name nor a known atlas registry key.

    Examples
    --------
    >>> resolve_atlases(["core"])
    ['schaefer100x7_tian_s2', '4S156Parcels']

    >>> resolve_atlases(["core", "schaefer100x7_tian_s1"])
    ['schaefer100x7_tian_s2', '4S156Parcels', 'schaefer100x7_tian_s1']

    >>> resolve_atlases(["core", "4S156Parcels"])  # deduplicates
    ['schaefer100x7_tian_s2', '4S156Parcels']
    """
    unknown = [s for s in specs if s not in ATLAS_SUITES and s not in ATLAS_REGISTRY]
    if unknown:
        raise ValueError(
            f"Unknown atlas or suite name(s): {unknown}. "
            f"Known suites: {sorted(ATLAS_SUITES)}. "
            f"Known atlases: {sorted(ATLAS_REGISTRY)}."
        )

    seen: set[str] = set()
    result: list[str] = []
    for spec in specs:
        keys = ATLAS_SUITES[spec] if spec in ATLAS_SUITES else [spec]
        for key in keys:
            if key not in seen:
                seen.add(key)
                result.append(key)
    return result


# ---------------------------------------------------------------------------
# QSIRecon helpers
# ---------------------------------------------------------------------------

def get_qsirecon_seg_name(atlas: str) -> str:
    """Return the QSIRecon segmentation name for an atlas.

    Works for atlases that have a direct ``qsirecon_seg_name`` (combined
    atlases, standalone volumetric atlases like aal116, etc.).

    Raises
    ------
    ValueError
        If the atlas is a component of a combined seg (use
        ``get_containing_combined_atlases`` instead) or has no QSIRecon seg.
    """
    meta = get_atlas(atlas)
    seg_name = meta.get("qsirecon_seg_name")
    if seg_name is not None:
        return seg_name
    component_of = meta.get("qsirecon_component_of", [])
    if component_of:
        raise ValueError(
            f"Atlas {atlas!r} has no standalone QSIRecon segmentation — "
            f"it is a component of: {component_of}. "
            "Use get_containing_combined_atlases() to find the combined atlas."
        )
    raise ValueError(
        f"Atlas {atlas!r} has no QSIRecon segmentation (no qsirecon_seg_name)."
    )


def get_containing_combined_atlases(atlas: str) -> list[str]:
    """Return the registry keys of combined atlases that contain this component atlas.

    Returns an empty list if the atlas is not a component of any combined atlas.
    """
    meta = get_atlas(atlas)
    return list(meta.get("qsirecon_component_of", []))


def is_qsirecon_component(atlas: str) -> bool:
    """True if this atlas only exists as a component of a QSIRecon combined seg."""
    meta = get_atlas(atlas)
    return bool(meta.get("qsirecon_component_of")) and "qsirecon_seg_name" not in meta


def build_label_filter(atlas: str) -> Callable[[int, str], bool] | None:
    """Return a label-filter function for a component atlas, or None for full atlases.

    The filter is applied to ``(region_index, region_label)`` pairs from a
    combined seg's label file to select only the parcels belonging to this
    component atlas.

    Parameters
    ----------
    atlas:
        Registry key of the component atlas (e.g. ``"schaefer400x7"``).

    Returns
    -------
    Callable[[int, str], bool] or None
        Function ``(index, label) -> bool`` returning True for parcels belonging
        to this atlas.  None if no filter is needed (atlas uses all labels).
    """
    meta = get_atlas(atlas)
    if "qsirecon_label_startswith" in meta:
        prefixes = tuple(meta["qsirecon_label_startswith"])
        return lambda idx, label: label.startswith(prefixes)
    if "qsirecon_label_exclude_startswith" in meta:
        prefixes = tuple(meta["qsirecon_label_exclude_startswith"])
        return lambda idx, label: not label.startswith(prefixes)
    if "qsirecon_index_range" in meta:
        lo, hi = meta["qsirecon_index_range"]
        return lambda idx, label: lo <= idx <= hi
    return None


# ---------------------------------------------------------------------------
# Atlas metadata (dseg TSV loading)
# ---------------------------------------------------------------------------

_DATA_DIR = Path(__file__).parent / "data" / "atlases"

# Normalized output columns for all get_atlas_metadata results
_OUTPUT_COLS = ["region_index", "region_label", "hemisphere", "network_7", "network_17", "source_atlas"]


def get_atlas_metadata(atlas: str) -> pd.DataFrame:
    """Load and return region-level metadata for an atlas as a normalized DataFrame.

    For combined atlases (e.g. ``"schaefer100x7_tian_s1"``), the full dseg TSV
    is loaded from the bundled data directory.

    For component atlases (e.g. ``"schaefer100x7"``, ``"tian_s1"``), the metadata
    is loaded from the first parent combined atlas's dseg file and filtered to
    only the rows belonging to this component using :func:`build_label_filter`.

    For standalone volumetric atlases with their own dseg file (e.g. ``"aseg"``),
    the file is loaded directly.

    Parameters
    ----------
    atlas:
        Atlas registry key (e.g. ``"schaefer100x7_tian_s1"``, ``"aseg"``).

    Returns
    -------
    pd.DataFrame
        Normalized DataFrame with columns:
        ``region_index`` (Int64), ``region_label``, ``hemisphere``,
        ``network_7``, ``network_17``, ``source_atlas``.

    Raises
    ------
    FileNotFoundError
        If no dseg TSV file can be found for the atlas or its parent.
    KeyError
        If the atlas key is not in the registry.
    """
    # Validate atlas exists in registry
    get_atlas(atlas)

    # 1. Try direct dseg file
    direct_path = _DATA_DIR / f"{atlas}_dseg.tsv"
    if direct_path.exists():
        return _load_and_normalize_dseg(direct_path, atlas)

    # 2. Component atlas: load from first available parent combined atlas
    meta = get_atlas(atlas)
    parents = meta.get("qsirecon_component_of", [])
    for parent_key in parents:
        parent_path = _DATA_DIR / f"{parent_key}_dseg.tsv"
        if parent_path.exists():
            df = _load_and_normalize_dseg(parent_path, parent_key)
            label_filter = build_label_filter(atlas)
            if label_filter is not None:
                mask = df.apply(
                    lambda row: label_filter(
                        int(row["region_index"]) if pd.notna(row["region_index"]) else -1,
                        str(row["region_label"]) if pd.notna(row["region_label"]) else "",
                    ),
                    axis=1,
                )
                df = df[mask].reset_index(drop=True)
            # Re-index region_index to 1-based for the component subset
            df["region_index"] = pd.array(range(1, len(df) + 1), dtype="Int64")
            return df

    raise FileNotFoundError(
        f"No dseg TSV found for atlas '{atlas}' or any of its parent combined atlases "
        f"(searched: {[str(_DATA_DIR / f'{p}_dseg.tsv') for p in parents]}). "
        f"Expected: {direct_path}"
    )


def _load_and_normalize_dseg(tsv_path: Path, atlas: str) -> pd.DataFrame:
    """Load a dseg TSV and normalize column names to the standard schema.

    Reads the TSV, renames columns to the canonical output schema, infers
    hemisphere from region labels, coerces region_index to Int64, and
    replaces literal ``"n/a"`` / empty strings with ``pd.NA``.

    Parameters
    ----------
    tsv_path:
        Path to the ``*_dseg.tsv`` file.
    atlas:
        Atlas key (used only for context in error messages).

    Returns
    -------
    pd.DataFrame
        Normalized DataFrame with columns:
        ``region_index``, ``region_label``, ``hemisphere``,
        ``network_7``, ``network_17``, ``source_atlas``.
    """
    from brainbank_extract.extractors.freesurfer import _infer_hemisphere

    df = pd.read_csv(tsv_path, sep="\t", dtype=str)

    # Replace literal "n/a" and empty strings with pd.NA across all columns
    df = df.replace({"n/a": pd.NA, "": pd.NA})

    # Column rename map: source → target
    rename_map = {
        "index": "region_index",
        "label": "region_label",
        "network_label": "network_7",
        "network_label_17network": "network_17",
        "atlas_name": "source_atlas",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    # Ensure all output columns exist
    for col in _OUTPUT_COLS:
        if col not in df.columns:
            df[col] = pd.NA

    # Coerce region_index to nullable integer
    df["region_index"] = pd.to_numeric(df["region_index"], errors="coerce").astype("Int64")

    # Infer hemisphere from region label
    df["hemisphere"] = df["region_label"].apply(
        lambda lbl: _infer_hemisphere(str(lbl)) if pd.notna(lbl) else pd.NA
    )

    return df[_OUTPUT_COLS].copy()


def get_combined_metadata(atlases: list[str]) -> pd.DataFrame:
    """Concatenate atlas metadata for multiple atlases into a single DataFrame.

    Parameters
    ----------
    atlases:
        List of atlas registry keys.

    Returns
    -------
    pd.DataFrame
        Concatenated metadata with an additional ``atlas`` column identifying
        the source atlas for each row.
    """
    frames = []
    for atlas in atlases:
        df = get_atlas_metadata(atlas)
        df.insert(0, "atlas", atlas)
        frames.append(df)
    return pd.concat(frames, ignore_index=True)
