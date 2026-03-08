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
  --freesurfer-dir /derivatives/freesurfer/sub-001_ses-20240101 \
  --qsirecon-dir /derivatives/qsirecon \
  --output-dir /derivatives/brainbank-extract/sub-001/ses-20240101 \
  --atlases schaefer400x7 \
  --atlases 4S156Parcels \
  --subject sub-001 \
  --session ses-20240101

# 2. Aggregate across all sessions (not yet implemented)
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
    model="dkimicro",
    param="fa",
)

# Connectivity matrices
conn, meta, labels = bb.load_connectivity(
    extract_dir="/derivatives/brainbank-extract/aggregated",
    atlas="schaefer400x7",
    measure="atlas_4S156Parcels_radius2_count_connectivity",
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
  --freesurfer-dir PATH   Path to the FreeSurfer subject/session directory
                          (flat layout: sub-XXX_ses-XXX/ with surf/, label/, stats/).
  --qsirecon-dir PATH     Path to the ROOT QSIRecon derivatives directory
                          (contains sub-*/ses-*/dwi/ and derivatives/qsirecon-*/).
                          Do NOT point to a session-level directory.
  --output-dir PATH       Output directory for extracted files.  [required]
  --atlases TEXT          Atlas key(s) to extract. May be repeated.
                          [default: schaefer400x7]
  --subject TEXT          BIDS subject identifier (e.g. sub-001).  [required]
  --session TEXT          BIDS session identifier (e.g. ses-20240101).  [required]
  --version               Show the version and exit.
  --help                  Show this message and exit.
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

| Key | Full Name | Type | Parcels | FreeSurfer stats | QSIRecon seg name |
|-----|-----------|------|---------|-----------------|-------------------|
| `schaefer100x7` | Schaefer 2018, 100 parcels, 7 networks | surface | 100 | `?h.schaefer100-7.stats` | `Schaefer2018N100n7Tian2020S1` |
| `schaefer200x7` | Schaefer 2018, 200 parcels, 7 networks | surface | 200 | `?h.schaefer200-7.stats` | `Schaefer2018N200n7Tian2020S2` |
| `schaefer400x7` | Schaefer 2018, 400 parcels, 7 networks | surface | 400 | `?h.schaefer400-7.stats` | `Schaefer2018N400n7Tian2020S2` |
| `tian_s1` | Tian 2020, Scale I | volumetric | 16 | — | `TianS1` |
| `tian_s2` | Tian 2020, Scale II | volumetric | 32 | — | `TianS2` |
| `tian_s3` | Tian 2020, Scale III | volumetric | 50 | `Tian2020S3.stats` | `TianS3` |
| `4S156Parcels` | 4S 156 Parcels | combined | 156 | — | `4S156Parcels` |
| `4S256Parcels` | 4S 256 Parcels | combined | 256 | — | `4S256Parcels` |
| `4S356Parcels` | 4S 356 Parcels | combined | 356 | — | `4S356Parcels` |
| `4S456Parcels` | 4S 456 Parcels | combined | 456 | — | `4S456Parcels` |
| `brainnetome246` | Brainnetome Atlas | volumetric | 246 | — | `Brainnetome246` |
| `aal116` | Automated Anatomical Labeling | volumetric | 116 | — | `AAL116` |
| `gordon333` | Gordon 2016 | surface | 333 | — | `Gordon333` |
| `desikan` | Desikan-Killiany (FreeSurfer default) | surface | 68 | `?h.aparc.stats` | `aparc` |
| `destrieux` | Destrieux (a2009s) | surface | 148 | `?h.aparc.a2009s.stats` | `aparc.a2009s` |
| `aseg` | FreeSurfer subcortical segmentation | volumetric | ~45 | `aseg.stats` | — |

Register custom atlases at runtime:

```python
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

For surface atlases, the extractor uses **pre-computed stats files** as the primary
path (e.g. `lh.schaefer400-7.stats`, `lh.aparc.stats`). These files are produced by
`mris_anatomical_stats` and contain per-parcel ThickAvg, SurfArea, GrayVol, and
MeanCurv columns — all four morphometrics are extracted in a single pass.

If no stats file is found for an atlas, the extractor falls back to per-vertex
annotation parcellation using `.annot` files and raw surface metric files
(`lh.thickness`, `lh.area`, etc.).

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
| Atlas registry | ✅ Done |
| I/O helpers | ✅ Done |
| FreeSurfer extractor | ✅ Done |
| QSIRecon extractor | ✅ Done |
| Aggregator (`bb-aggregate`) | ⬜ Not started |
| Python API (`load_*`) | ⬜ Not started |
| Docker | ⬜ Stub only |
