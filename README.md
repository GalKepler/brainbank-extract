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
# 1. Extract features for a single session
bb-extract \
  --freesurfer-dir /derivatives/freesurfer/sub-001/ses-20240101 \
  --qsirecon-dir /derivatives/qsirecon/sub-001/ses-20240101 \
  --output-dir /derivatives/brainbank-extract/sub-001/ses-20240101 \
  --atlases schaefer400x7 \
  --atlases tian_s2 \
  --subject sub-001 \
  --session ses-20240101

# 2. Aggregate across all sessions
bb-aggregate \
  --extract-dir /derivatives/brainbank-extract \
  --output-dir /derivatives/brainbank-extract/aggregated
```

### Python API

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
    model="DTI",
    param="FA",
)

# Connectivity matrices
conn, meta, labels = bb.load_connectivity(
    extract_dir="/derivatives/brainbank-extract/aggregated",
    atlas="schaefer400x7",
    measure="sift2",
)
# conn: np.ndarray (N_sessions, N_parcels, N_parcels)
# meta: DataFrame with subject/session columns
# labels: list of region names

# Wide format for ML
ct_wide = bb.to_wide(ct, index=["subject", "session"], columns="region_label", values="value")

# What's available?
bb.list_available("/derivatives/brainbank-extract/aggregated")
```

## CLI Reference

### `bb-extract`

Extract features for a single subject/session. Designed to run inside a Docker container on a Slurm cluster.

```
Usage: bb-extract [OPTIONS]

Options:
  --freesurfer-dir PATH   Path to FreeSurfer subject/session directory.
  --qsirecon-dir PATH     Path to QSIRecon subject/session directory.
  --output-dir PATH       Output directory for extracted files.  [required]
  --atlases TEXT          Atlas key(s) to extract. May be repeated.
                          [default: schaefer400x7]
  --subject TEXT          BIDS subject identifier (e.g. sub-001).  [required]
  --session TEXT          BIDS session identifier (e.g. ses-20240101).  [required]
  --version               Show the version and exit.
  --help                  Show this message and exit.
```

At least one of `--freesurfer-dir` or `--qsirecon-dir` must be provided.

### `bb-aggregate`

Aggregate per-session extraction outputs into dataset-level consolidated files.

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

## Python API Reference

### `load_morphometrics(extract_dir, metric, atlas)`

Load cortical morphometrics aggregated across all sessions.

| Parameter | Type | Description |
|-----------|------|-------------|
| `extract_dir` | `str \| Path` | Aggregated brainbank-extract directory |
| `metric` | `str` | `"thickness"`, `"area"`, `"volume"`, `"curvature"`, `"sulc"` |
| `atlas` | `str` | Atlas key (e.g. `"schaefer400x7"`) |

Returns `pd.DataFrame` with columns: `subject`, `session`, `region_index`, `region_label`, `hemisphere`, `value`, `metric`.

### `load_connectivity(extract_dir, atlas, measure)`

Load stacked connectivity matrices.

| Parameter | Type | Description |
|-----------|------|-------------|
| `extract_dir` | `str \| Path` | Aggregated brainbank-extract directory |
| `atlas` | `str` | Atlas key |
| `measure` | `str` | `"sift2"`, `"count"`, `"meanlength"` |

Returns `(np.ndarray, pd.DataFrame, list[str])`: stacked matrices `(N, P, P)`, session metadata, region labels.

### `load_diffusion_scalars(extract_dir, atlas, model, param)`

Load parcellated diffusion scalar values.

| Parameter | Type | Description |
|-----------|------|-------------|
| `extract_dir` | `str \| Path` | Aggregated brainbank-extract directory |
| `atlas` | `str` | Atlas key |
| `model` | `str` | `"DTI"`, `"NODDI"`, `"DKI"`, `"MAPMRI"` |
| `param` | `str` | Model parameter (see table below) |

Returns `pd.DataFrame` with columns: `subject`, `session`, `region_index`, `region_label`, `hemisphere`, `mean`, `std`, `median`, `n_voxels`.

### `load_tract_profiles(extract_dir, tract=None)`

Load pyAFQ tract profiles.

Returns `pd.DataFrame` with columns: `subject`, `session`, `tract`, `node`, `FA`, `MD`, ...

### `load_global_metrics(extract_dir)`

Load global brain metrics (eTIV, volumes).

Returns `pd.DataFrame` with columns: `subject`, `session`, `metric`, `value`.

### `list_available(extract_dir)`

List all aggregated data in an extract directory.

### `to_wide(df, index, columns, values)`

Pivot a long-format DataFrame to wide format (thin wrapper around `pd.pivot_table`).

## Supported Atlases

| Key | Full Name | Type | Parcels |
|-----|-----------|------|---------|
| `schaefer100x7` | Schaefer 2018, 100 parcels, 7 networks | surface | 100 |
| `schaefer200x7` | Schaefer 2018, 200 parcels, 7 networks | surface | 200 |
| `schaefer400x7` | Schaefer 2018, 400 parcels, 7 networks | surface | 400 |
| `tian_s1` | Tian 2020, Scale I | volumetric | 16 |
| `tian_s2` | Tian 2020, Scale II | volumetric | 32 |
| `4S156Parcels` | 4S 156 Parcels | combined | 156 |
| `4S256Parcels` | 4S 256 Parcels | combined | 256 |
| `4S356Parcels` | 4S 356 Parcels | combined | 356 |
| `4S456Parcels` | 4S 456 Parcels | combined | 456 |
| `brainnetome246` | Brainnetome Atlas | volumetric | 246 |
| `aal116` | Automated Anatomical Labeling | volumetric | 116 |
| `gordon333` | Gordon 2016 | surface | 333 |
| `desikan` | Desikan-Killiany (FreeSurfer default) | surface | 68 |
| `destrieux` | Destrieux (a2009s) | surface | 148 |
| `aseg` | FreeSurfer subcortical segmentation | volumetric | ~45 |

Register custom atlases at runtime:

```python
from brainbank_extract.atlases import register_atlas
register_atlas("myatlas200", {"full_name": "My Atlas", "type": "surface", "n_parcels": 200})
```

## Supported Diffusion Models and Parameters

| Model | Parameters |
|-------|-----------|
| DTI | FA, MD, RD, AD |
| NODDI | ICVF, ISOVF, OD |
| DKI | MK, AK, RK |
| MAPMRI | RTOP, RTAP, RTPP |

## Output File Structure

```
/derivatives/brainbank-extract/
├── sub-001/
│   └── ses-20240101/
│       ├── anat/
│       │   ├── sub-001_ses-20240101_atlas-schaefer400x7_desc-thickness_morph.tsv
│       │   ├── sub-001_ses-20240101_atlas-schaefer400x7_desc-area_morph.tsv
│       │   ├── sub-001_ses-20240101_atlas-aseg_desc-subcortical_morph.tsv
│       │   └── sub-001_ses-20240101_desc-globalmetrics_morph.tsv
│       ├── dwi/
│       │   ├── scalars/
│       │   │   ├── sub-001_ses-20240101_atlas-schaefer400x7_model-DTI_param-FA_desc-parcellated_diffmetrics.tsv
│       │   │   └── ...
│       │   ├── connectivity/
│       │   │   ├── sub-001_ses-20240101_atlas-schaefer400x7_desc-sift2_connmatrix.npy
│       │   │   ├── sub-001_ses-20240101_atlas-schaefer400x7_desc-sift2_connmatrix-labels.json
│       │   │   └── ...
│       │   └── tractprofiles/
│       │       └── sub-001_ses-20240101_tract-ArcuateL_desc-profile_tractmetrics.tsv
│       └── _status.json
│
└── aggregated/
    ├── anat/
    │   ├── atlas-schaefer400x7_desc-thickness_morph.parquet
    │   └── desc-globalmetrics_morph.parquet
    └── dwi/
        ├── scalars/
        │   └── atlas-schaefer400x7_model-DTI_param-FA_desc-parcellated_diffmetrics.parquet
        └── connectivity/
            ├── atlas-schaefer400x7_desc-sift2_connmatrix.npy        # (N_sessions, N, N)
            ├── atlas-schaefer400x7_desc-sift2_connmatrix-meta.parquet
            └── atlas-schaefer400x7_desc-sift2_connmatrix-labels.json
```

## Docker / Slurm

```bash
# Build
docker build -t brainbank-extract .

# Run a single session
apptainer run \
  --bind /derivatives:/derivatives \
  brainbank-extract.sif \
  bb-extract \
    --freesurfer-dir /derivatives/freesurfer/sub-001/ses-20240101 \
    --qsirecon-dir /derivatives/qsirecon/sub-001/ses-20240101 \
    --output-dir /derivatives/brainbank-extract/sub-001/ses-20240101 \
    --atlases schaefer400x7 \
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
uv run pytest tests/test_atlases.py -v
```

## Implementation Status

| Component | Status |
|-----------|--------|
| Package skeleton & CLI stubs | ✅ Done |
| Atlas registry | ✅ Done |
| I/O helpers | ✅ Done |
| FreeSurfer extractor | 🚧 In progress |
| QSIRecon extractor | 🚧 In progress |
| Aggregator | 🚧 In progress |
| Python API | 🚧 In progress |
| Docker | 🚧 Stub only |
