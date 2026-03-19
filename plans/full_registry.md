# Plan: Unify QSIRecon atlases for FreeSurfer extraction

## Context

QSIRecon uses 55 volumetric atlases (all MNI-space NIfTI). Currently only a handful have FreeSurfer extraction support (Schaefer 100/200/400, Tian S1-S3, Desikan, Destrieux). The goal is to make **all 55** atlases usable for FreeSurfer morphometric extraction, so researchers get consistent parcellation across both dMRI and sMRI modalities.

**Strategy by atlas category:**

| Category | Count | FreeSurfer approach |
|----------|-------|-------------------|
| Schaefer N100-N1000 | 10 | Surface .annot via fsatlas (7 missing from bb registry) |
| Tian S1-S4 | 4 | Volumetric via fsatlas (S4 missing from bb registry) |
| Schaefer+Tian combos | 40 | Decompose: Schaefer surface + Tian volumetric (36 missing from bb registry) |
| 4S combined | 10 | Decompose: Schaefer surface + subcortical volumetric (6 missing from bb registry) |
| Gordon333Ext | 1 | **New**: Gordon cortical .annot (add to fsatlas) + subcortical volumetric |
| Brainnetome246Ext | 1 | **New**: Brainnetome cortical .annot (add to fsatlas) + subcortical volumetric |
| AICHA384Ext | 1 | **New**: AICHA cortical .annot (add to fsatlas) + subcortical volumetric |
| HCPex | 1 | HCP-MMP cortical .annot (already in fsatlas) + subcortical volumetric |
| AAL116 | 1 | `mri_vol2surf` projection to create .annot, then surface extraction |

---

## Phase 1: Expand atlas registry (`atlases.py`)

### 1A. Programmatic generation for Schaefer + Tian entries

Replace the 3 hand-coded Schaefer entries and 4 Schaefer+Tian combined entries with a generator function. This produces:
- 10 Schaefer component entries (N100-N1000, 7-network)
- 4 Tian component entries (S1-S4, adding missing S4)
- 40 Schaefer+Tian combined entries

```python
TIAN_PARCELS = {1: 16, 2: 32, 3: 50, 4: 54}

def _build_schaefer_tian_entries() -> dict[str, dict]:
    """Generate all Schaefer component + Schaefer+Tian combined entries."""
    entries = {}
    for n in range(100, 1100, 100):
        key = f"schaefer{n}x7"
        entries[key] = {
            "full_name": f"Schaefer 2018, {n} parcels, 7 networks",
            "type": "surface",
            "n_parcels": n,
            "fsatlas_name": f"schaefer{n}-7",
            "qsirecon_component_of": [f"schaefer{n}x7_tian_s{s}" for s in [1,2,3,4]],
            "qsirecon_label_startswith": ["LH_", "RH_"],
        }
    for s, np_ in TIAN_PARCELS.items():
        # ... tian entries with qsirecon_component_of for all SchN+TianS combos
    for n in range(100, 1100, 100):
        for s, tp in TIAN_PARCELS.items():
            combo = f"schaefer{n}x7_tian_s{s}"
            entries[combo] = {
                "type": "combined", "n_parcels": n + tp,
                "qsirecon_seg_name": f"Schaefer2018N{n}n7Tian2020S{s}",
                "components": { ... },
            }
    return entries
```

### 1B. Add missing 4S entries (4S556-4S1056)

6 new entries following the existing 4S pattern. Need to determine their Schaefer+subcortical decomposition for FreeSurfer extraction. The 4S cortical component maps to Schaefer N; subcortical parcels need volumetric extraction from the QSIRecon NIfTI atlas.

### 1C. Add "Ext" atlas entries and their cortical components

New entries:
- `gordon333` — type "surface", `fsatlas_name: "gordon333"`
- `gordon333ext` — type "combined", components: gordon333 (surface) + subcortical (volumetric)
- `brainnetome246` — type "surface", `fsatlas_name: "brainnetome246"`
- `brainnetome246ext` — type "combined", components: brainnetome246 + subcortical
- `aicha384` — type "surface", `fsatlas_name: "aicha384"`
- `aicha384ext` — type "combined", components: aicha384 + subcortical
- Update `HCPex` — components: hcpmmp (surface, `fsatlas_name: "hcp-mmp"`) + subcortical
- `aal116` — type "surface", `fsatlas_name: "aal116"` (after mri_vol2surf projection)

### 1D. Label filtering for Ext atlas components

The Ext atlases use different label conventions than Schaefer+Tian (which uses `LH_`/`RH_` prefixes). Add **index-range-based filtering** as an alternative to prefix-based:

```python
# New filter spec fields:
{"qsirecon_index_range": [1, 333]}      # cortical: indices 1-333
{"qsirecon_index_range": [334, 386]}     # subcortical: indices 334-386
```

Extend `build_label_filter()` to handle index-range specs.

**Files:** `src/brainbank_extract/atlases.py`

---

## Phase 2: Add new atlases to fsatlas catalog

### 2A. Gordon333 surface atlas
Source: Gordon lab fsaverage .annot files (published with Gordon et al., Cerebral Cortex, 2016). Add entry to `catalog.yaml` with download URLs for `lh.Gordon333.annot` / `rh.Gordon333.annot`.

### 2B. Brainnetome246 surface atlas
Source: https://atlas.brainnetome.org/ — fsaverage .annot files available. Add `brainnetome246` entry.

### 2C. AICHA384 surface atlas
Source: https://www.gin.cnrs.fr/en/tools/aicha/ — fsaverage surface parcellation available. Add `aicha384` entry.

### 2D. AAL116 — `mri_vol2surf` projected atlas
AAL has no published fsaverage surface version. Add to fsatlas:
1. Add a new atlas type or mechanism in fsatlas for `mri_vol2surf`-projected atlases
2. The workflow: take MNI volumetric NIfTI → `mri_vol2surf --projfrac 0.5` onto fsaverage → convert to .annot
3. This is a one-time conversion; the resulting .annot can be cached/shipped

Alternative (simpler): Create the AAL .annot files manually using a script, then add them to fsatlas as a regular surface atlas with pre-built .annot files hosted somewhere.

### 2E. Subcortical extension atlas as volumetric
For the subcortical parts of Ext atlases, add volumetric entries to fsatlas OR (recommended) handle them directly in brainbank-extract by pointing to the QSIRecon NIfTI atlas files.

**Files:** `/home/galkepler/Projects/fsatlas/src/fsatlas/atlases/catalog.yaml`

---

## Phase 3: FreeSurfer extractor changes (`freesurfer.py`)

### 3A. Add combined atlas extraction support

New method `_extract_combined_atlas()` that:
1. Looks up `components` dict from the atlas registry
2. For each component with `fsatlas_name`: calls existing `_extract_with_fsatlas(component_key)`
3. For subcortical components without `fsatlas_name`: extracts volumetric metrics using the QSIRecon NIfTI atlas (see 3B)
4. Merges results: cortical-only metrics (thickness, area, curvature) from surface component; volume from both

### 3B. Add QSIRecon NIfTI volumetric extraction path

New method `_extract_volumetric_from_nifti()`:
1. Takes QSIRecon atlas NIfTI path + label file
2. Uses `mri_vol2vol` to register MNI atlas → subject native space (via FreeSurfer's `transforms/talairach.xfm` or similar)
3. Uses `mri_segstats` with the registered atlas + norm.mgz to extract volumes
4. Parses output → brainbank DataFrame

This requires a new optional parameter: `qsirecon_atlases_dir` on `FreeSurferExtractor.__init__()`.

### 3C. Update extract() loop

```python
for atlas in self.atlases:
    if atlas == "aseg":
        continue
    atlas_meta = get_atlas(atlas)

    if atlas_meta["type"] == "combined" and "components" in atlas_meta:
        # Decompose and extract each component
        self._extract_combined_atlas(atlas)
    elif atlas_meta.get("fsatlas_name"):
        # Direct surface or volumetric extraction via fsatlas
        self._extract_with_fsatlas(atlas)
    else:
        # Skip with warning
        ...
```

**Files:** `src/brainbank_extract/extractors/freesurfer.py`

---

## Phase 4: CLI update (`cli.py`)

Add `--qsirecon-atlases-dir` parameter to `bb-extract` CLI, passed through to `FreeSurferExtractor`. Defaults to `None` (subcortical volumetric extraction skipped if not provided).

**Files:** `src/brainbank_extract/cli.py`

---

## Phase 5: dseg TSV metadata files

Generate `*_dseg.tsv` files for all new atlas entries from the QSIRecon source files at `/media/storage/yalab-dev/snbb_scheduler/derivatives/qsirecon/atlases/atlas-*/`. Write a one-time script to:
1. Read each QSIRecon `*_dseg.tsv`
2. Normalize column names
3. Write to `src/brainbank_extract/data/atlases/`

**Files:** `src/brainbank_extract/data/atlases/*.tsv`, one-time generation script

---

## Phase 6: Tests

- Test programmatic Schaefer+Tian registry generation (correct keys, n_parcels, component mappings)
- Test index-range-based label filtering for Ext atlases
- Test `_extract_combined_atlas()` with mock combined atlas
- Test `_extract_volumetric_from_nifti()` (mock mri_vol2vol + mri_segstats)
- Update existing test fixtures for expanded registry

**Files:** `tests/conftest.py`, `tests/test_freesurfer.py`, `tests/test_atlases.py` (new)

---

## Implementation order

1. **Phase 1** — Atlas registry expansion (foundation; everything depends on this)
2. **Phase 5** — dseg TSV files (needed for metadata lookups)
3. **Phase 2** — fsatlas catalog additions (needed before FreeSurfer extraction works)
4. **Phase 3** — FreeSurfer extractor changes (the core feature)
5. **Phase 4** — CLI update
6. **Phase 6** — Tests

---

## Verification

1. `uv run pytest` — all existing tests pass + new atlas/extractor tests
2. Smoke test with real data:
   ```bash
   uv run bb-extract \
     --freesurfer-dir data/freesurfer/sub-CLMC10_ses-202407110849 \
     --qsirecon-dir data/qsirecon \
     --qsirecon-atlases-dir data/qsirecon/atlases \
     --output-dir /tmp/bb-test/sub-CLMC10/ses-202407110849 \
     --atlases gordon333ext --atlases brainnetome246ext --atlases aal116 \
     --subject sub-CLMC10 --session ses-202407110849
   ```
3. Verify output: cortical metric TSVs (thickness, area, volume, curvature) for surface components + volume TSV for subcortical components

---

## Open questions for implementation

1. **AAL116 mri_vol2surf**: Should the .annot creation be a one-time script that ships pre-built files, or should fsatlas learn to do `mri_vol2surf` projections on-the-fly? Pre-built is simpler.
2. **4S subcortical decomposition**: The 4S subcortical component includes CIT168, thalamus, hippocampus, amygdala, cerebellum parcels. These don't map 1:1 to Tian. Need to verify which Schaefer resolution maps to which 4S atlas (e.g., 4S156 = Schaefer100 + 56 subcortical).
3. **Ext atlas .annot availability**: Need to verify exact download URLs for Gordon, Brainnetome, and AICHA fsaverage .annot files. Some may need conversion from .gii or .label format.
