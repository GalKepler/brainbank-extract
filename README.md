# brainbank-extract

A pip-installable Python package that extracts analysis-ready neuroimaging features from FreeSurfer and QSIRecon derivative directories, and aggregates them across an entire brain bank dataset into researcher-friendly formats.

## Problem

After running FreeSurfer, QSIPrep, and QSIRecon on brain bank MRI sessions, the outputs are scattered across deeply nested BIDS-derivative directories in pipeline-specific formats. A researcher who wants "cortical thickness by Schaefer parcel for all 300 subjects" currently needs to:

1. Know the directory layout of each pipeline
2. Write custom code to locate and parse the right files
3. Handle atlas-specific naming conventions
4. Concatenate across sessions with consistent identifiers
5. Deal with missing data, failed sessions, and edge cases

`brainbank-extract` eliminates this by providing a single extraction + aggregation layer that turns pipeline outputs into standardized, loadable datasets.

## Architecture

```
FreeSurfer outputs ─┐
                    ├─→ bb-extract (per session) ─→ standardized per-session files
QSIRecon outputs  ──┘                                        │
                                                             ▼
                                            bb-aggregate (dataset-wide)
                                                             │
                                                             ▼
                                              aggregated parquet + .npy files
                                                             │
                                                             ▼
                                              researcher: bb.load_morphometrics("CT")
```

## Installation

### With uv (recommended)

```bash
uv pip install brainbank-extract
```

### Development install

```bash
git clone <repo>
cd brainbank-extract
uv venv
uv pip install -e ".[dev]"
```

### With pip

```bash
pip install brainbank-extract
```

## Quick Start

### CLI

```bash
# Extract FreeSurfer + QSIRecon features for a single session
bb-extract \
  --freesurfer-dir /derivatives/freesurfer/sub-001_ses-20240101 \
  --qsirecon-dir /derivatives/qsirecon \
  --output-dir /derivatives/brainbank-extract/sub-001/ses-20240101 \
  --atlases schaefer400x7_tian_s2 \
  --atlases 4S456Parcels \
  --subject sub-001 \
  --session ses-20240101

# Use the "extended" suite to run a standard set of atlases in one flag
bb-extract \
  --freesurfer-dir /derivatives/freesurfer/sub-001_ses-20240101 \
  --qsirecon-dir /derivatives/qsirecon \
  --output-dir /derivatives/brainbank-extract/sub-001/ses-20240101 \
  --atlases extended \
  --subject sub-001 \
  --session ses-20240101

# FreeSurfer only (no QSIRecon)
bb-extract \
  --freesurfer-dir /derivatives/freesurfer/sub-001_ses-20240101 \
  --output-dir /derivatives/brainbank-extract/sub-001/ses-20240101 \
  --atlases desikan --atlases destrieux --atlases aseg \
  --subject sub-001 --session ses-20240101

# QSIRecon only (no FreeSurfer)
bb-extract \
  --qsirecon-dir /derivatives/qsirecon \
  --output-dir /derivatives/brainbank-extract/sub-001/ses-20240101 \
  --atlases 4S156Parcels --atlases 4S456Parcels \
  --subject sub-001 --session ses-20240101
```

### Inspect the atlas registry

```python
from brainbank_extract.atlases import (
    get_atlas,
    get_atlas_metadata,
    list_atlases,
    list_suites,
    resolve_atlases,
    ATLAS_REGISTRY,
)

# All 80 registered atlas keys
list_atlases()

# Expand a suite name to individual atlas keys
resolve_atlases(["extended"])
# → ['schaefer100x7_tian_s2', '4S156Parcels', 'schaefer400x7_tian_s2',
#    '4S456Parcels', 'HCPex', 'brainnetome246ext']

# Metadata for a specific atlas
get_atlas("gordon333ext")
# → {'full_name': 'Gordon 2016 333-parcel + subcortical extension (385 total)',
#    'type': 'combined', 'n_parcels': 385, 'qsirecon_seg_name': 'Gordon333Ext',
#    'components': {'gordon333': {'qsirecon_index_range': [1, 333]},
#                   'gordon333_subcortical': {'qsirecon_index_range': [335, 386]}}}

# Region-level metadata as a DataFrame
df = get_atlas_metadata("schaefer400x7_tian_s2")
#    region_index region_label  hemisphere network_7 ...
# 0             1    LH_Vis_1           L   Default ...
# ...         ...         ...         ...       ...
```

### Python API (aggregated data — not yet implemented)

```python
import brainbank_extract as bb

# Cortical thickness for all sessions, Schaefer 400 atlas
ct = bb.load_morphometrics(
    extract_dir="/derivatives/brainbank-extract/aggregated",
    metric="thickness",
    atlas="schaefer400x7",
)
# Returns long-format DataFrame:
# subject | session | region_index | region_label | hemisphere | value | metric

# DTI fractional anisotropy
fa = bb.load_diffusion_scalars(
    extract_dir="/derivatives/brainbank-extract/aggregated",
    atlas="schaefer400x7",
    model="dkimicro",
    param="fa",
)

# Connectivity matrices
conn, meta, labels = bb.load_connectivity(
    extract_dir="/derivatives/brainbank-extract/aggregated",
    atlas="4S456Parcels",
    measure="sift2",
)
# conn: np.ndarray (N_sessions, N_parcels, N_parcels)
# meta: DataFrame with subject/session columns
# labels: list of region names
```

## CLI Reference

### `bb-extract`

Extract features for a single subject/session. Designed to run inside a Docker container on a Slurm cluster.

```
Usage: bb-extract [OPTIONS]

Options:
  --freesurfer-dir PATH       Path to the FreeSurfer subject/session directory
                              (flat layout: sub-XXX_ses-XXX/ with surf/, label/, stats/).
  --qsirecon-dir PATH         Path to the ROOT QSIRecon derivatives directory
                              (contains sub-*/ses-*/dwi/ and derivatives/qsirecon-*/).
                              Do NOT point to a session-level directory.
  --output-dir PATH           Output directory for extracted files.  [required]
  --atlases TEXT              Atlas key(s) or suite name(s) to extract. May be
                              repeated.  [default: schaefer400x7]
  --subject TEXT              BIDS subject identifier (e.g. sub-001).  [required]
  --session TEXT              BIDS session identifier (e.g. ses-20240101).  [required]
  --qsirecon-atlases-dir PATH Path to the QSIRecon atlases directory (atlas-*/
                              subdirectories). Reserved for future subcortical
                              volumetric extraction.
  --version                   Show the version and exit.
  --help                      Show this message and exit.
```

At least one of `--freesurfer-dir` or `--qsirecon-dir` must be provided.

**Important:** `--freesurfer-dir` accepts the flat session directory layout used in
this pipeline (e.g. `/derivatives/freesurfer/sub-001_ses-20240101`), not a nested
`sub/ses/` structure. `--qsirecon-dir` must point to the **root** QSIRecon derivatives
directory, not a session directory.

### `bb-aggregate`

Aggregate per-session extraction outputs into dataset-level consolidated files.
Not yet implemented.

```
Usage: bb-aggregate [OPTIONS]

Options:
  --extract-dir PATH      Root directory with per-session outputs.  [required]
  --output-dir PATH       Output directory for aggregated files.  [required]
  --modalities TEXT       Modalities to aggregate: anat and/or dwi.
                          May be repeated.  [default: anat, dwi]
  --force                 Re-aggregate all sessions even if previously processed.
  --version               Show the version and exit.
  --help                  Show this message and exit.
```

## Supported Atlases

The registry contains **80 atlases** across five categories. Use `list_atlases()` or
`list_suites()` to enumerate them programmatically.

### Atlas suites

Pass a suite name anywhere an atlas key is accepted — it expands to a curated list:

| Suite | Contents |
|-------|----------|
| `core` | `schaefer100x7_tian_s2`, `4S156Parcels` |
| `extended` | core + `schaefer400x7_tian_s2`, `4S456Parcels`, `HCPex`, `brainnetome246ext` |
| `cortical` | `schaefer100x7`–`schaefer400x7`, `desikan`, `destrieux` |
| `subcortical` | `tian_s1`–`tian_s4`, `aseg` |
| `full` | Every atlas in the registry |

```python
from brainbank_extract.atlases import resolve_atlases, list_suites

# Expand a mix of suite names and individual atlas keys
resolve_atlases(["core", "destrieux"])
# → ['schaefer100x7_tian_s2', '4S156Parcels', 'destrieux']

list_suites()
# → ['core', 'cortical', 'extended', 'full', 'subcortical']
```

### Schaefer cortical atlases (surface)

Ten resolutions, all paired with 7-network parcellation:

| Key | Parcels | fsatlas name |
|-----|---------|--------------|
| `schaefer100x7` | 100 | `schaefer100-7` |
| `schaefer200x7` | 200 | `schaefer200-7` |
| `schaefer300x7` | 300 | `schaefer300-7` |
| … | … | … |
| `schaefer1000x7` | 1000 | `schaefer1000-7` |

### Tian subcortical atlases (volumetric)

| Key | Parcels | Scale | fsatlas name |
|-----|---------|-------|--------------|
| `tian_s1` | 16 | I | `tian-s1` |
| `tian_s2` | 32 | II | `tian-s2` |
| `tian_s3` | 50 | III | `tian-s3` |
| `tian_s4` | 54 | IV | `tian-s4` |

### Schaefer+Tian combined atlases (QSIRecon)

40 entries — every Schaefer resolution paired with every Tian scale.
FreeSurfer extraction decomposes each into its Schaefer and Tian components.

| Key pattern | n_parcels | QSIRecon seg |
|-------------|-----------|--------------|
| `schaefer{N}x7_tian_s{S}` | N + Tian_S parcels | `Schaefer2018N{N}n7Tian2020S{S}` |

Examples: `schaefer100x7_tian_s1` (116), `schaefer400x7_tian_s2` (432), `schaefer1000x7_tian_s4` (1054)

### 4S combined atlases (QSIRecon)

Ten entries pairing each Schaefer resolution with a 56-parcel subcortical extension:

| Key | n_parcels | QSIRecon seg |
|-----|-----------|--------------|
| `4S156Parcels` | 156 | `4S156Parcels` |
| `4S256Parcels` | 256 | `4S256Parcels` |
| … | … | … |
| `4S1056Parcels` | 1056 | `4S1056Parcels` |

### Extended atlases (Ext families)

Each Ext atlas has a cortical component (surface, with a future fsatlas entry) and a
subcortical component. FreeSurfer extraction runs on the cortical component once
fsatlas entries are added (Phase 2).

| Combined key | n_parcels | Cortical component | Subcortical component |
|--------------|-----------|-------------------|-----------------------|
| `gordon333ext` | 385 | `gordon333` (333) | `gordon333_subcortical` (52) |
| `brainnetome246ext` | 256 | `brainnetome246` (246) | `brainnetome246_subcortical` (10) |
| `aicha384ext` | 394 | `aicha384` (384) | `aicha384_subcortical` (10) |
| `HCPex` | 426 | `hcpmmp` (360) | `hcpex_subcortical` (66) |

### FreeSurfer default parcellations

| Key | Parcels | Type | fsatlas name |
|-----|---------|------|--------------|
| `desikan` | 68 | surface | `desikan` |
| `destrieux` | 148 | surface | `destrieux` |
| `aseg` | ~45 | volumetric | — |
| `aal116` | 116 | surface | `aal116` |

### Programmatic atlas inspection

```python
from brainbank_extract.atlases import get_atlas, list_atlases, get_atlas_metadata

# Inspect any atlas
get_atlas("schaefer400x7_tian_s2")
# → {'full_name': 'Schaefer 2018 400-parcel 7-network + Tian 2020 Scale II',
#    'type': 'combined', 'n_parcels': 432, 'qsirecon_seg_name': 'Schaefer2018N400n7Tian2020S2',
#    'components': {'schaefer400x7': {...}, 'tian_s2': {...}}}

# Load region metadata as a DataFrame
df = get_atlas_metadata("gordon333ext")
# → DataFrame with region_index, region_label, hemisphere columns (385 rows)

# Register a custom atlas
from brainbank_extract.atlases import register_atlas
register_atlas("myatlas200", {"full_name": "My Atlas", "type": "surface", "n_parcels": 200})
```

## Supported Diffusion Models and Parameters

Model names and parameter names are taken directly from QSIRecon output filenames
(`*_model-{model}_param-{param}_dwimap.nii.gz`). Common values:

| Pipeline | Model | Parameters |
|----------|-------|-----------|
| `qsirecon-DIPYDKI` | `dkimicro` | `fa`, `md`, `rd`, `ad`, `mk`, `ak`, `rk`, ... |
| `qsirecon-AMICONODDI` | `noddi` | `icvf`, `isovf`, `od` |
| `qsirecon-DIPYMAPMRI` | `mapmri` | `rtop`, `rtap`, `rtpp` |

## Output File Structure

### Per-session (`bb-extract`)

```
/derivatives/brainbank-extract/sub-001/ses-20240101/
├── anat/
│   ├── sub-001_ses-20240101_atlas-schaefer400x7_desc-thickness_morph.tsv
│   ├── sub-001_ses-20240101_atlas-schaefer400x7_desc-area_morph.tsv
│   ├── sub-001_ses-20240101_atlas-schaefer400x7_desc-volume_morph.tsv
│   ├── sub-001_ses-20240101_atlas-schaefer400x7_desc-curvature_morph.tsv
│   ├── sub-001_ses-20240101_atlas-aseg_desc-subcortical_morph.tsv
│   └── sub-001_ses-20240101_desc-globalmetrics_morph.tsv
├── dwi/
│   ├── scalars/
│   │   ├── sub-001_ses-20240101_atlas-4S156Parcels_model-dkimicro_param-fa_desc-parcellated_diffmetrics.tsv
│   │   ├── sub-001_ses-20240101_atlas-4S156Parcels_model-dkimicro_param-md_desc-parcellated_diffmetrics.tsv
│   │   └── ...  (one file per atlas × model × parameter)
│   └── connectivity/
│       ├── sub-001_ses-20240101_atlas-4S156Parcels_desc-{measure}_connmatrix.npy
│       ├── sub-001_ses-20240101_atlas-4S156Parcels_desc-{measure}_connmatrix-labels.json
│       └── ...  (one .npy per matrix found in connectivity .mat file)
└── _status.json
```

Connectivity measure names (`{measure}`) come directly from the MATLAB variable names
in the QSIRecon `*_connectivity.mat` file (e.g.
`atlas_4S156Parcels_radius2_count_connectivity`,
`atlas_4S156Parcels_sift_radius2_count_connectivity`).

### TSV column specs

**Morphometrics** (`_morph.tsv`):

| Column | Description |
|--------|-------------|
| `region_index` | Integer label in the atlas |
| `region_label` | Human-readable region name |
| `hemisphere` | `L`, `R`, or `bilateral` |
| `value` | The metric value |
| `metric` | `thickness`, `area`, `volume`, or `curvature` |

**Diffusion scalars** (`_diffmetrics.tsv`):

| Column | Description |
|--------|-------------|
| `region_index` | Integer label in the atlas |
| `region_label` | Human-readable region name |
| `hemisphere` | `L`, `R`, or `bilateral` |
| `mean` | Mean scalar value within ROI |
| `std` | Standard deviation |
| `median` | Median value |
| `n_voxels` | Number of voxels in ROI |

### Aggregated (`bb-aggregate`, not yet implemented)

```
/derivatives/brainbank-extract/aggregated/
├── anat/
│   ├── atlas-schaefer400x7_desc-thickness_morph.parquet
│   └── desc-globalmetrics_morph.parquet
└── dwi/
    ├── scalars/
    │   └── atlas-4S156Parcels_model-dkimicro_param-fa_desc-parcellated_diffmetrics.parquet
    └── connectivity/
        ├── atlas-4S156Parcels_desc-{measure}_connmatrix.npy     # (N_sessions, N, N)
        ├── atlas-4S156Parcels_desc-{measure}_connmatrix-meta.parquet
        └── atlas-4S156Parcels_desc-{measure}_connmatrix-labels.json
```

## FreeSurfer Extraction Details

For **surface atlases**, the extractor calls `fsatlas` to transfer the atlas to the
subject's space and run `mris_anatomical_stats`, extracting thickness, surface area,
gray matter volume, and curvature in a single pass.

For **combined atlases with a `components` dict** (e.g. `schaefer400x7_tian_s2`,
`gordon333ext`), the extractor decomposes the atlas and processes each component
separately:

- Cortical components with an `fsatlas_name` (e.g. `schaefer400x7`, `gordon333`) are
  extracted via fsatlas, producing `atlas-schaefer400x7_desc-thickness_morph.tsv` etc.
- Subcortical volumetric components with an `fsatlas_name` (e.g. `tian_s1`) are
  extracted via fsatlas volumetric stats.
- Subcortical components without an `fsatlas_name` (e.g. `gordon333_subcortical`) are
  skipped until a volumetric NIfTI extraction path is added (Phase 3B).

For **volumetric atlases** (Tian), the extractor first tries to parse an existing
`<atlas>.subcortical.stats` file. If the file contains generic `Seg####` region names
(no colour table was used), it re-runs fsatlas to regenerate the file with proper names.

**Combined atlases without a `components` dict** (e.g. the 4S series) have no defined
FreeSurfer decomposition and are skipped with a warning — they are extracted via
QSIRecon only.

## QSIRecon Extraction Details

The extractor discovers scalar maps by globbing all
`qsirecon-*/sub-*/ses-*/dwi/*_model-*_param-*_dwimap.nii.gz` files across pipeline
subdirectories, then parcellates each map against the atlas segmentation NII
(`*_seg-{atlas}_dseg.nii.gz`). Label names come from the companion `*_dseg.txt` file.

Connectivity matrices are read from MATLAB `.mat` files in the
`qsirecon-MRtrix3_act-HSVS` pipeline directory. All square matrices found in the
`.mat` file are extracted (one output `.npy` per matrix variable).

## Docker / Slurm

```bash
# Build
docker build -t brainbank-extract .

# Run a single session via Apptainer
apptainer run \
  --bind /derivatives:/derivatives \
  brainbank-extract.sif \
  bb-extract \
    --freesurfer-dir /derivatives/freesurfer/sub-001_ses-20240101 \
    --qsirecon-dir /derivatives/qsirecon \
    --output-dir /derivatives/brainbank-extract/sub-001/ses-20240101 \
    --atlases schaefer400x7 \
    --atlases 4S156Parcels \
    --subject sub-001 \
    --session ses-20240101
```

## Development

```bash
# Setup
uv venv
uv pip install -e ".[dev]"

# Run tests
uv run pytest tests/ -v

# Run a specific test file
uv run pytest tests/test_freesurfer.py -v
```

## Implementation Status

| Component | Status |
|-----------|--------|
| Package skeleton & CLI | ✅ Done |
| Atlas registry (80 atlases, suites, index-range filters) | ✅ Done |
| I/O helpers | ✅ Done |
| FreeSurfer extractor (surface + volumetric + combined decomposition) | ✅ Done |
| QSIRecon extractor (scalars, connectivity, label filtering) | ✅ Done |
| dseg TSV files for all 55 QSIRecon atlases | ✅ Done |
| fsatlas catalog entries for Gordon333, Brainnetome246, AICHA384, AAL116 | ⬜ Phase 2 |
| FreeSurfer volumetric NIfTI extraction (Ext subcortical components) | ⬜ Phase 3B |
| Aggregator (`bb-aggregate`) | ⬜ Not started |
| Python API (`load_*`) | ⬜ Not started |
| Docker | ⬜ Stub only |
