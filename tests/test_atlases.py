"""Tests for the atlas registry and helper functions."""

from __future__ import annotations

import pytest

from brainbank_extract.atlases import (
    ATLAS_REGISTRY,
    TIAN_PARCELS,
    build_label_filter,
    get_atlas,
    get_atlas_metadata,
    get_containing_combined_atlases,
    is_qsirecon_component,
    resolve_atlases,
)


# ---------------------------------------------------------------------------
# Registry completeness: Schaefer + Tian
# ---------------------------------------------------------------------------

def test_schaefer_all_resolutions_in_registry() -> None:
    """All 10 Schaefer resolutions (N100–N1000) are in the registry."""
    for n in range(100, 1100, 100):
        assert f"schaefer{n}x7" in ATLAS_REGISTRY, f"missing schaefer{n}x7"


def test_tian_all_scales_in_registry() -> None:
    """All 4 Tian scales (S1–S4) are in the registry."""
    for s in range(1, 5):
        assert f"tian_s{s}" in ATLAS_REGISTRY, f"missing tian_s{s}"


def test_schaefer_tian_combined_all_40() -> None:
    """All 40 Schaefer+Tian combined atlases (10 × 4) are in the registry."""
    for n in range(100, 1100, 100):
        for s in range(1, 5):
            key = f"schaefer{n}x7_tian_s{s}"
            assert key in ATLAS_REGISTRY, f"missing {key}"


def test_schaefer_tian_n_parcels_correct() -> None:
    """Combined atlas n_parcels = Schaefer_n + Tian_s parcels."""
    assert ATLAS_REGISTRY["schaefer400x7_tian_s2"]["n_parcels"] == 432   # 400+32
    assert ATLAS_REGISTRY["schaefer100x7_tian_s4"]["n_parcels"] == 154   # 100+54
    assert ATLAS_REGISTRY["schaefer1000x7_tian_s1"]["n_parcels"] == 1016  # 1000+16


def test_schaefer_components_reference_valid_combined_atlases() -> None:
    """Each schaefer component's qsirecon_component_of points to existing combined atlases."""
    for n in range(100, 1100, 100):
        meta = ATLAS_REGISTRY[f"schaefer{n}x7"]
        for combined_key in meta["qsirecon_component_of"]:
            assert combined_key in ATLAS_REGISTRY, f"schaefer{n}x7 references missing {combined_key}"


def test_tian_component_of_correct_length() -> None:
    """Each Tian atlas appears in exactly 10 combined atlases (one per Schaefer resolution)."""
    for s in range(1, 5):
        meta = ATLAS_REGISTRY[f"tian_s{s}"]
        assert len(meta["qsirecon_component_of"]) == 10


# ---------------------------------------------------------------------------
# Registry completeness: 4S
# ---------------------------------------------------------------------------

def test_4s_all_10_in_registry() -> None:
    """All 10 4S atlases (4S156–4S1056) are in the registry."""
    for n in range(100, 1100, 100):
        key = f"4S{n + 56}Parcels"
        assert key in ATLAS_REGISTRY, f"missing {key}"


def test_4s_n_parcels_correct() -> None:
    """4S atlas n_parcels matches key."""
    assert ATLAS_REGISTRY["4S156Parcels"]["n_parcels"] == 156
    assert ATLAS_REGISTRY["4S556Parcels"]["n_parcels"] == 556
    assert ATLAS_REGISTRY["4S1056Parcels"]["n_parcels"] == 1056


# ---------------------------------------------------------------------------
# Registry completeness: Ext atlases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key", [
    "gordon333", "gordon333_subcortical", "gordon333ext",
    "brainnetome246", "brainnetome246_subcortical", "brainnetome246ext",
    "aicha384", "aicha384_subcortical", "aicha384ext",
    "hcpmmp", "hcpex_subcortical",
])
def test_ext_atlas_entries_exist(key: str) -> None:
    assert key in ATLAS_REGISTRY, f"missing {key}"


def test_hcpex_has_components() -> None:
    """HCPex combined atlas has components dict with hcpmmp and hcpex_subcortical."""
    meta = ATLAS_REGISTRY["HCPex"]
    assert "components" in meta
    assert "hcpmmp" in meta["components"]
    assert "hcpex_subcortical" in meta["components"]


def test_gordon333ext_n_parcels() -> None:
    assert ATLAS_REGISTRY["gordon333ext"]["n_parcels"] == 385  # 333 + 52


def test_brainnetome246ext_n_parcels() -> None:
    assert ATLAS_REGISTRY["brainnetome246ext"]["n_parcels"] == 256  # 246 + 10


def test_aicha384ext_n_parcels() -> None:
    assert ATLAS_REGISTRY["aicha384ext"]["n_parcels"] == 394  # 384 + 10


def test_aal116_is_surface() -> None:
    """aal116 is surface type with fsatlas_name."""
    meta = ATLAS_REGISTRY["aal116"]
    assert meta["type"] == "surface"
    assert meta.get("fsatlas_name") == "aal116"


# ---------------------------------------------------------------------------
# build_label_filter: label-startswith (existing behaviour)
# ---------------------------------------------------------------------------

def test_label_startswith_filter_accepts_lh_rh() -> None:
    """Schaefer filter returns True for LH_/RH_ labels."""
    f = build_label_filter("schaefer400x7")
    assert f is not None
    assert f(1, "LH_Vis_1") is True
    assert f(200, "RH_SomMot_3") is True


def test_label_startswith_filter_rejects_tian_labels() -> None:
    """Schaefer filter returns False for Tian-style labels."""
    f = build_label_filter("schaefer400x7")
    assert f is not None
    assert f(401, "HIP-lh") is False
    assert f(402, "AMY-rh") is False


def test_label_exclude_startswith_filter() -> None:
    """Tian filter excludes LH_/RH_ labels."""
    f = build_label_filter("tian_s2")
    assert f is not None
    assert f(1, "LH_Vis_1") is False
    assert f(101, "HIP-lh") is True


# ---------------------------------------------------------------------------
# build_label_filter: index-range (new behaviour)
# ---------------------------------------------------------------------------

def test_index_range_filter_gordon_cortical() -> None:
    """gordon333 filter accepts indices 1–333, rejects others."""
    f = build_label_filter("gordon333")
    assert f is not None
    assert f(1, "L_Default_1") is True
    assert f(333, "R_VentralAttn_333") is True
    assert f(335, "CIT168Subcortical_Pu_rh") is False  # subcortical start


def test_index_range_filter_gordon_subcortical() -> None:
    """gordon333_subcortical filter accepts indices 335–386."""
    f = build_label_filter("gordon333_subcortical")
    assert f is not None
    assert f(335, "CIT168Subcortical_Pu_rh") is True
    assert f(386, "Cerebellum_Region10") is True
    assert f(333, "R_VentralAttn_333") is False  # cortical


def test_index_range_filter_hcpmmp() -> None:
    """hcpmmp filter accepts indices 1–360."""
    f = build_label_filter("hcpmmp")
    assert f is not None
    assert f(1, "V1_L") is True
    assert f(360, "SFL_R") is True
    assert f(361, "Thal_AV_L") is False


def test_no_filter_for_combined_atlas() -> None:
    """Combined atlas with no filter spec returns None."""
    f = build_label_filter("gordon333ext")
    assert f is None


def test_no_filter_for_standalone_atlas() -> None:
    """Standalone atlas (desikan) returns None."""
    f = build_label_filter("desikan")
    assert f is None


# ---------------------------------------------------------------------------
# QSIRecon helpers
# ---------------------------------------------------------------------------

def test_get_containing_combined_atlases_schaefer() -> None:
    """schaefer400x7 is a component of exactly 4 combined atlases (one per Tian scale)."""
    combined = get_containing_combined_atlases("schaefer400x7")
    assert len(combined) == 4
    assert "schaefer400x7_tian_s1" in combined
    assert "schaefer400x7_tian_s4" in combined


def test_get_containing_combined_atlases_gordon333() -> None:
    """gordon333 is a component of gordon333ext only."""
    combined = get_containing_combined_atlases("gordon333")
    assert combined == ["gordon333ext"]


def test_is_qsirecon_component_true() -> None:
    """schaefer400x7 and tian_s2 are component atlases."""
    assert is_qsirecon_component("schaefer400x7") is True
    assert is_qsirecon_component("tian_s2") is True
    assert is_qsirecon_component("gordon333") is True


def test_is_qsirecon_component_false() -> None:
    """Combined atlases and standalone atlases are not components."""
    assert is_qsirecon_component("gordon333ext") is False
    assert is_qsirecon_component("aal116") is False
    assert is_qsirecon_component("desikan") is False


# ---------------------------------------------------------------------------
# resolve_atlases
# ---------------------------------------------------------------------------

def test_resolve_core_suite() -> None:
    result = resolve_atlases(["core"])
    assert result == ["schaefer100x7_tian_s2", "4S156Parcels"]


def test_resolve_deduplicates() -> None:
    result = resolve_atlases(["core", "4S156Parcels"])
    assert result.count("4S156Parcels") == 1


# ---------------------------------------------------------------------------
# get_atlas_metadata: component atlas (requires dseg file on disk)
# ---------------------------------------------------------------------------

def test_get_atlas_metadata_schaefer100_tian_s1() -> None:
    """get_atlas_metadata returns a DataFrame for a combined atlas that has a dseg file."""
    df = get_atlas_metadata("schaefer100x7_tian_s1")
    assert len(df) > 0
    assert "region_index" in df.columns
    assert "region_label" in df.columns
    assert "hemisphere" in df.columns


def test_get_atlas_metadata_schaefer100_component() -> None:
    """schaefer100x7 metadata is loaded from parent combined atlas and filtered."""
    df = get_atlas_metadata("schaefer100x7")
    # Should contain only LH_/RH_ labels
    assert all(
        str(lbl).startswith(("LH_", "RH_"))
        for lbl in df["region_label"]
        if str(lbl) not in ("nan", "<NA>")
    )


def test_get_atlas_metadata_gordon333ext() -> None:
    """gordon333ext metadata loads from gordon333ext_dseg.tsv."""
    df = get_atlas_metadata("gordon333ext")
    assert len(df) == 385  # 333 cortical + 52 subcortical


def test_get_atlas_metadata_gordon333_cortical_component() -> None:
    """gordon333 metadata filters to cortical parcels only (indices 1–333)."""
    df = get_atlas_metadata("gordon333")
    assert len(df) == 333


def test_get_atlas_metadata_gordon333_subcortical_component() -> None:
    """gordon333_subcortical metadata filters to subcortical parcels only."""
    df = get_atlas_metadata("gordon333_subcortical")
    assert len(df) == 52
