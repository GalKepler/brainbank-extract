"""Atlas registry: metadata for all supported brain parcellation atlases."""

from __future__ import annotations

from typing import Any, Callable

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

ATLAS_REGISTRY: dict[str, dict[str, Any]] = {
    # ------------------------------------------------------------------
    # Schaefer cortical atlases (surface type; FreeSurfer + QSIRecon combined)
    # ------------------------------------------------------------------
    "schaefer100x7": {
        "full_name": "Schaefer 2018, 100 parcels, 7 networks",
        "type": "surface",
        "n_parcels": 100,
        "freesurfer_annot_pattern": "?h.schaefer100-7.annot",
        "freesurfer_stats_pattern": "?h.schaefer100-7.stats",
        # In QSIRecon, Schaefer100 is always bundled with Tian S1
        "qsirecon_component_of": ["schaefer100x7_tian_s1"],
        "qsirecon_label_startswith": ["LH_", "RH_"],
    },
    "schaefer200x7": {
        "full_name": "Schaefer 2018, 200 parcels, 7 networks",
        "type": "surface",
        "n_parcels": 200,
        "freesurfer_annot_pattern": "?h.schaefer200-7.annot",
        "freesurfer_stats_pattern": "?h.schaefer200-7.stats",
        "qsirecon_component_of": ["schaefer200x7_tian_s2"],
        "qsirecon_label_startswith": ["LH_", "RH_"],
    },
    "schaefer400x7": {
        "full_name": "Schaefer 2018, 400 parcels, 7 networks",
        "type": "surface",
        "n_parcels": 400,
        "freesurfer_annot_pattern": "?h.schaefer400-7.annot",
        "freesurfer_stats_pattern": "?h.schaefer400-7.stats",
        "qsirecon_component_of": ["schaefer400x7_tian_s2"],
        "qsirecon_label_startswith": ["LH_", "RH_"],
    },

    # ------------------------------------------------------------------
    # Tian subcortical atlases (volumetric type; QSIRecon combined only)
    # ------------------------------------------------------------------
    "tian_s1": {
        "full_name": "Tian 2020, Scale I",
        "type": "volumetric",
        "n_parcels": 16,
        # TianS1 is bundled with Schaefer100 in QSIRecon
        "qsirecon_component_of": ["schaefer100x7_tian_s1"],
        "qsirecon_label_exclude_startswith": ["LH_", "RH_"],
    },
    "tian_s2": {
        "full_name": "Tian 2020, Scale II",
        "type": "volumetric",
        "n_parcels": 32,
        # TianS2 is bundled with both Schaefer200 and Schaefer400 in QSIRecon
        "qsirecon_component_of": ["schaefer200x7_tian_s2", "schaefer400x7_tian_s2"],
        "qsirecon_label_exclude_startswith": ["LH_", "RH_"],
    },
    "tian_s3": {
        "full_name": "Tian 2020, Scale III",
        "type": "volumetric",
        "n_parcels": 50,
        "freesurfer_stats_pattern": "Tian2020S3.stats",
        # TianS3 standalone QSIRecon seg; update if confirmed to exist
        "qsirecon_seg_name": "TianS3",
    },

    # ------------------------------------------------------------------
    # QSIRecon combined atlases: Schaefer cortical + Tian subcortical
    # These are the actual segmentation files on disk. They are the output
    # unit for connectivity matrices.
    # ------------------------------------------------------------------
    "schaefer100x7_tian_s1": {
        "full_name": "Schaefer 2018 100-parcel 7-network + Tian 2020 Scale I",
        "type": "combined",
        "n_parcels": 116,
        "qsirecon_seg_name": "Schaefer2018N100n7Tian2020S1",
        "components": {
            "schaefer100x7": {"qsirecon_label_startswith": ["LH_", "RH_"]},
            "tian_s1": {"qsirecon_label_exclude_startswith": ["LH_", "RH_"]},
        },
    },
    "schaefer200x7_tian_s2": {
        "full_name": "Schaefer 2018 200-parcel 7-network + Tian 2020 Scale II",
        "type": "combined",
        "n_parcels": 232,
        "qsirecon_seg_name": "Schaefer2018N200n7Tian2020S2",
        "components": {
            "schaefer200x7": {"qsirecon_label_startswith": ["LH_", "RH_"]},
            "tian_s2": {"qsirecon_label_exclude_startswith": ["LH_", "RH_"]},
        },
    },
    "schaefer400x7_tian_s2": {
        "full_name": "Schaefer 2018 400-parcel 7-network + Tian 2020 Scale II",
        "type": "combined",
        "n_parcels": 432,
        "qsirecon_seg_name": "Schaefer2018N400n7Tian2020S2",
        "components": {
            "schaefer400x7": {"qsirecon_label_startswith": ["LH_", "RH_"]},
            "tian_s2": {"qsirecon_label_exclude_startswith": ["LH_", "RH_"]},
        },
    },

    # ------------------------------------------------------------------
    # 4S combined atlases (QSIRecon-only; Schaefer cortical + richer subcortical)
    # ------------------------------------------------------------------
    "4S156Parcels": {
        "full_name": "4S 156 Parcels",
        "type": "combined",
        "n_parcels": 156,
        "qsirecon_seg_name": "4S156Parcels",
    },
    "4S256Parcels": {
        "full_name": "4S 256 Parcels",
        "type": "combined",
        "n_parcels": 256,
        "qsirecon_seg_name": "4S256Parcels",
    },
    "4S356Parcels": {
        "full_name": "4S 356 Parcels",
        "type": "combined",
        "n_parcels": 356,
        "qsirecon_seg_name": "4S356Parcels",
    },
    "4S456Parcels": {
        "full_name": "4S 456 Parcels",
        "type": "combined",
        "n_parcels": 456,
        "qsirecon_seg_name": "4S456Parcels",
    },

    # ------------------------------------------------------------------
    # Other volumetric atlases
    # ------------------------------------------------------------------
    "brainnetome246": {
        "full_name": "Brainnetome Atlas, 246 parcels",
        "type": "volumetric",
        "n_parcels": 246,
        "qsirecon_seg_name": "Brainnetome246",
    },
    "aal116": {
        "full_name": "Automated Anatomical Labeling, 116 regions",
        "type": "volumetric",
        "n_parcels": 116,
        "qsirecon_seg_name": "AAL116",
    },

    # ------------------------------------------------------------------
    # Surface atlases (FreeSurfer + standalone QSIRecon seg)
    # ------------------------------------------------------------------
    "gordon333": {
        "full_name": "Gordon 2016, 333 parcels",
        "type": "surface",
        "n_parcels": 333,
        "freesurfer_annot_pattern": "?h.Gordon333.annot",
        "qsirecon_seg_name": "Gordon333",
    },
    "desikan": {
        "full_name": "Desikan-Killiany (FreeSurfer default)",
        "type": "surface",
        "n_parcels": 68,
        "freesurfer_annot_pattern": "?h.aparc.annot",
        "freesurfer_stats_pattern": "?h.aparc.stats",
        "qsirecon_seg_name": "aparc",
    },
    "destrieux": {
        "full_name": "Destrieux (a2009s)",
        "type": "surface",
        "n_parcels": 148,
        "freesurfer_annot_pattern": "?h.aparc.a2009s.annot",
        "freesurfer_stats_pattern": "?h.aparc.a2009s.stats",
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
# QSIRecon helpers
# ---------------------------------------------------------------------------

def get_qsirecon_seg_name(atlas: str) -> str:
    """Return the QSIRecon segmentation name for an atlas.

    Works for atlases that have a direct ``qsirecon_seg_name`` (combined
    atlases, standalone volumetric atlases like brainnetome, gordon333, etc.).

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


def build_label_filter(atlas: str) -> Callable[[str], bool] | None:
    """Return a label-filter function for a component atlas, or None for full atlases.

    The filter is applied to region label strings from a combined seg's label
    file to select only the parcels belonging to this component atlas.

    Parameters
    ----------
    atlas:
        Registry key of the component atlas (e.g. ``"schaefer400x7"``).

    Returns
    -------
    Callable[[str], bool] or None
        Function returning True for labels belonging to this atlas.
        None if no filter is needed (atlas uses all labels in its seg).
    """
    meta = get_atlas(atlas)
    if "qsirecon_label_startswith" in meta:
        prefixes = tuple(meta["qsirecon_label_startswith"])
        return lambda label: label.startswith(prefixes)
    if "qsirecon_label_exclude_startswith" in meta:
        prefixes = tuple(meta["qsirecon_label_exclude_startswith"])
        return lambda label: not label.startswith(prefixes)
    return None
