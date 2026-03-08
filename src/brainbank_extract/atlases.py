"""Atlas registry: metadata for all supported brain parcellation atlases."""

from __future__ import annotations

from typing import Any

ATLAS_REGISTRY: dict[str, dict[str, Any]] = {
    "schaefer100x7": {
        "full_name": "Schaefer 2018, 100 parcels, 7 networks",
        "type": "surface",
        "n_parcels": 100,
        "freesurfer_annot_pattern": "?h.Schaefer2018_100Parcels_7Networks_order.annot",
        "qsirecon_name": "Schaefer100x7",
    },
    "schaefer200x7": {
        "full_name": "Schaefer 2018, 200 parcels, 7 networks",
        "type": "surface",
        "n_parcels": 200,
        "freesurfer_annot_pattern": "?h.Schaefer2018_200Parcels_7Networks_order.annot",
        "qsirecon_name": "Schaefer200x7",
    },
    "schaefer400x7": {
        "full_name": "Schaefer 2018, 400 parcels, 7 networks",
        "type": "surface",
        "n_parcels": 400,
        "freesurfer_annot_pattern": "?h.Schaefer2018_400Parcels_7Networks_order.annot",
        "qsirecon_name": "Schaefer400x7",
    },
    "tian_s1": {
        "full_name": "Tian 2020, Scale I",
        "type": "volumetric",
        "n_parcels": 16,
        "qsirecon_name": "TianS1",
    },
    "tian_s2": {
        "full_name": "Tian 2020, Scale II",
        "type": "volumetric",
        "n_parcels": 32,
        "qsirecon_name": "TianS2",
    },
    "4S156Parcels": {
        "full_name": "4S 156 Parcels",
        "type": "combined",
        "n_parcels": 156,
        "qsirecon_name": "4S156Parcels",
    },
    "4S256Parcels": {
        "full_name": "4S 256 Parcels",
        "type": "combined",
        "n_parcels": 256,
        "qsirecon_name": "4S256Parcels",
    },
    "4S356Parcels": {
        "full_name": "4S 356 Parcels",
        "type": "combined",
        "n_parcels": 356,
        "qsirecon_name": "4S356Parcels",
    },
    "4S456Parcels": {
        "full_name": "4S 456 Parcels",
        "type": "combined",
        "n_parcels": 456,
        "qsirecon_name": "4S456Parcels",
    },
    "brainnetome246": {
        "full_name": "Brainnetome Atlas, 246 parcels",
        "type": "volumetric",
        "n_parcels": 246,
        "qsirecon_name": "Brainnetome246",
    },
    "aal116": {
        "full_name": "Automated Anatomical Labeling, 116 regions",
        "type": "volumetric",
        "n_parcels": 116,
        "qsirecon_name": "AAL116",
    },
    "gordon333": {
        "full_name": "Gordon 2016, 333 parcels",
        "type": "surface",
        "n_parcels": 333,
        "freesurfer_annot_pattern": "?h.Gordon333.annot",
        "qsirecon_name": "Gordon333",
    },
    "desikan": {
        "full_name": "Desikan-Killiany (FreeSurfer default)",
        "type": "surface",
        "n_parcels": 68,
        "freesurfer_annot_pattern": "?h.aparc.annot",
        "qsirecon_name": "aparc",
    },
    "destrieux": {
        "full_name": "Destrieux (a2009s)",
        "type": "surface",
        "n_parcels": 148,
        "freesurfer_annot_pattern": "?h.aparc.a2009s.annot",
        "qsirecon_name": "aparc.a2009s",
    },
    "aseg": {
        "full_name": "FreeSurfer automatic subcortical segmentation",
        "type": "volumetric",
        "n_parcels": 45,
    },
}


def get_atlas(name: str) -> dict[str, Any]:
    """Return atlas metadata by registry key.

    Parameters
    ----------
    name:
        Atlas key as used in ATLAS_REGISTRY (e.g. ``"schaefer400x7"``).

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
