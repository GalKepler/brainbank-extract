# brainbank-extract — Design Document

A pip-installable Python package that extracts analysis-ready neuroimaging features from FreeSurfer and QSIRecon derivative directories, and aggregates them across an entire brain bank dataset into researcher-friendly formats.

## Problem

After running FreeSurfer, QSIPrep, and QSIRecon on brain bank MRI sessions, the outputs are scattered across deeply nested BIDS-derivative directories in pipeline-specific formats. A researcher who wants "cortical thickness by Schaefer parcel for all 300 subjects" currently needs to:

1. Know the directory layout of each pipeline
2. Write custom code to locate and parse the right files
3. Handle atlas-specific naming conventions
4. Concatenate across sessions with consistent identifiers
5. Deal with missing data, failed sessions, and edge cases

This is repeated by every researcher, for every analysis. `brainbank-extract` eliminates this by providing a single extraction + aggregation layer that turns pipeline outputs into standardized, loadable datasets.

## Scope

### In scope (v1)

- **FreeSurfer** morphometric extraction: cortical thickness, surface area, gray matter volume, curvature, sulcal depth — parcellated by arbitrary surface atlases (Schaefer, Desikan, Destrieux) and volumetric atlases (subcortical via aseg)
- **QSIRecon** diffusion extraction: parcellated scalar maps (FA, MD, RD, AD from DTI; ICVF/ISOVF/OD from NODDI; MK/AK/RK from DKI; RTOP/RTAP/RTPP from MAP-MRI), connectivity matrices, and tract profiles (from pyAFQ if available)
- **Aggregation** across sessions into consolidated per-metric files
- **Docker container** wrapping the extraction step for Slurm execution
- **Python API** for loading aggregated data in a single call

### Out of scope (v1)

- fMRIPrep / functional MRI extraction (future v2)
- CAT12 extraction (already handled by existing neuroalign-preprocessing loaders; migrate later)
- Atlas registration or resampling (assumes atlases are already in subject/standard space as provided by the upstream pipelines)
- QC or outlier detection (separate concern)
- Wide-format pivoting (researcher's job at analysis time)

---

## Architecture Overview

```
brainbank-extract
├── CLI entry points
│   ├── bb-extract        # Per-session extraction (runs in Docker/Slurm)
│   └── bb-aggregate      # Dataset-level aggregation (runs on head node / locally)
│
├── Extractors (per pipeline)
│   ├── freesurfer.py     # Reads stats files, annot-based parcellations
│   └── qsirecon.py       # Reads parcellated scalars, connectivity, tract profiles
│
├── Aggregator
│   └── aggregate.py      # Scans session outputs, concatenates, writes parquet
│
├── Atlas registry
│   └── atlases.py        # Atlas metadata: name → label file, type (surface/volume), parcels
│
├── IO / formats
│   └── io.py             # Parquet writers, numpy matrix IO, long-format helpers
│
└── API (for researchers)
    └── api.py            # load_morphometrics(), load_connectivity(), load_tract_profiles()
```

### Data flow

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

---

## Per-Session Extraction (`bb-extract`)

### CLI interface

```bash
bb-extract \
  --freesurfer-dir /derivatives/freesurfer/sub-001/ses-20240101 \
  --qsirecon-dir /derivatives/qsirecon/sub-001/ses-20240101 \
  --output-dir /derivatives/brainbank-extract/sub-001/ses-20240101 \
  --atlases schaefer400x7 tian_s2 brainnetome246 \
  --subject sub-001 \
  --session ses-20240101
```

### What it produces

For each (session × atlas) combination, the extraction step writes a structured output directory:

```
/derivatives/brainbank-extract/sub-001/ses-20240101/
├── anat/
│   ├── sub-001_ses-20240101_atlas-schaefer400x7_desc-thickness_morph.tsv
│   ├── sub-001_ses-20240101_atlas-schaefer400x7_desc-area_morph.tsv
│   ├── sub-001_ses-20240101_atlas-schaefer400x7_desc-volume_morph.tsv
│   ├── sub-001_ses-20240101_atlas-schaefer400x7_desc-curvature_morph.tsv
│   ├── sub-001_ses-20240101_atlas-schaefer400x7_desc-sulc_morph.tsv
│   ├── sub-001_ses-20240101_atlas-aseg_desc-subcortical_morph.tsv
│   └── sub-001_ses-20240101_desc-globalmetrics_morph.tsv   # TIV, eTIV, BrainSeg, etc.
│
└── dwi/
    ├── scalars/
    │   ├── sub-001_ses-20240101_atlas-schaefer400x7_model-DTI_param-FA_desc-parcellated_diffmetrics.tsv
    │   ├── sub-001_ses-20240101_atlas-schaefer400x7_model-DTI_param-MD_desc-parcellated_diffmetrics.tsv
    │   ├── sub-001_ses-20240101_atlas-schaefer400x7_model-NODDI_param-ICVF_desc-parcellated_diffmetrics.tsv
    │   └── ... (one file per atlas × model × parameter)
    │
    ├── connectivity/
    │   ├── sub-001_ses-20240101_atlas-schaefer400x7_desc-sift2_connmatrix.npy
    │   ├── sub-001_ses-20240101_atlas-schaefer400x7_desc-sift2_connmatrix-labels.json
    │   ├── sub-001_ses-20240101_atlas-schaefer400x7_desc-count_connmatrix.npy
    │   └── ... (one .npy per atlas × connectivity measure)
    │
    └── tractprofiles/   # only if pyAFQ outputs exist
        ├── sub-001_ses-20240101_tract-ArcuateL_desc-profile_tractmetrics.tsv
        └── ... (one file per tract)
```

### TSV column specs

**Morphometrics** (`_morph.tsv`):

| Column | Description |
|--------|-------------|
| `region_index` | Integer label in the atlas |
| `region_label` | Human-readable region name |
| `hemisphere` | `L`, `R`, or `bilateral` |
| `value` | The metric value |
| `metric` | What was measured: `thickness`, `area`, `volume`, `curvature`, `sulc` |

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

Note: If QSIRecon already produces parcellated TSVs with these columns, the extractor simply copies/renames them to match the naming convention. No recomputation needed.

**Global metrics** (`_globalmetrics_morph.tsv`):

| Column | Description |
|--------|-------------|
| `metric` | `eTIV`, `BrainSegVol`, `lhCortexVol`, `rhCortexVol`, `SubCortGrayVol`, ... |
| `value` | Numeric value |
| `source` | `freesurfer` |

**Connectivity matrices** (`_connmatrix.npy`):

- Shape: `(N_parcels, N_parcels)` — symmetric, float64
- Companion `_connmatrix-labels.json`: ordered list of region labels matching matrix rows/columns

**Tract profiles** (`_tractmetrics.tsv`):

| Column | Description |
|--------|-------------|
| `node` | Position along tract (0–99, or whatever pyAFQ uses) |
| `FA` | Fractional anisotropy at this node |
| `MD` | Mean diffusivity at this node |
| ... | Other scalars mapped onto the tract |

---

## Extraction Logic — FreeSurfer

### Cortical morphometrics (surface-based atlases)

FreeSurfer stores per-vertex data that can be parcellated using annotation files. For a given atlas (e.g., Schaefer 400):

1. Load the atlas annotation file (`.annot`) from `$SUBJECTS_DIR/sub-XXX/label/lh.Schaefer2018_400Parcels_7Networks_order.annot`
2. Load the per-vertex metric file (e.g., `?h.thickness` from `$SUBJECTS_DIR/sub-XXX/surf/`)
3. For each parcel in the annotation, extract all vertices belonging to that parcel and compute: mean, std, median, n_vertices
4. For **surface area**: use the white surface area file or compute from the surface mesh
5. For **volume**: use the ribbon-based volume or `aparc.stats`-style volume

If the atlas annotation is not present in the FreeSurfer subject directory (e.g., Schaefer is not run by default), the extractor should:
- Check if `fsatlas` has already produced the output TSVs and use those directly
- Otherwise, log a warning and skip that atlas for this session

### Subcortical volumes (aseg)

Parse `stats/aseg.stats` to extract subcortical volumes. These are atlas-independent (FreeSurfer's own segmentation). Output as a TSV with `atlas=aseg`.

### Global metrics

Parse `stats/aseg.stats` header lines to extract:
- `EstimatedTotalIntraCranialVol` (eTIV)
- `BrainSegVol`, `BrainSegVolNotVent`
- `lhCortexVol`, `rhCortexVol`
- `SubCortGrayVol`, `CerebralWhiteMatterVol`
- `MaskVol`

---

## Extraction Logic — QSIRecon

### Parcellated diffusion scalars

QSIRecon (especially with the 4S atlas set or custom atlases) produces parcellated TSV files in its output directory. The typical layout is:

```
qsirecon-<workflow>/sub-XXX/ses-XXX/dwi/
  sub-XXX_ses-XXX_space-T1w_atlas-<atlas>_model-<model>_param-<param>_desc-<desc>_parc.tsv
```

The extractor should:

1. Glob for `*_parc.tsv` files in the QSIRecon session directory
2. Parse BIDS entities from the filename (atlas, model, param, desc)
3. Copy/rename to the brainbank-extract output directory with the standardized naming convention
4. If the TSV lacks expected columns (e.g., `median`, `n_voxels`), compute them from the raw scalar maps + atlas if available; otherwise, output what's available

### Connectivity matrices

QSIRecon produces connectivity matrices typically as:

```
sub-XXX_ses-XXX_space-T1w_atlas-<atlas>_desc-<measure>_connectivity.csv
```

or in some workflows as `.npy` files. The extractor should:

1. Locate connectivity files for each atlas
2. If CSV: load as DataFrame, convert to numpy array, verify symmetry, save as `.npy`
3. If already `.npy`: copy with standardized name
4. Generate a companion `_connmatrix-labels.json` by reading the atlas label file or extracting from the CSV column/row headers
5. Supported connectivity measures: `sift2` (SIFT2-weighted streamline count), `count` (raw streamline count), `meanlength` (mean streamline length)

### Tract profiles (pyAFQ)

If QSIRecon was run with a pyAFQ recon spec, tract profile CSVs will exist. The extractor should:

1. Check for pyAFQ output directory within QSIRecon derivatives
2. Locate per-tract profile files
3. Standardize column names and output as `_tractmetrics.tsv`

If pyAFQ outputs don't exist for a session, skip silently (tract profiles are optional).

---

## Dataset Aggregation (`bb-aggregate`)

### CLI interface

```bash
bb-aggregate \
  --extract-dir /derivatives/brainbank-extract \
  --output-dir /derivatives/brainbank-extract/aggregated \
  --modalities anat dwi \
  --force   # optional: re-aggregate even if already done
```

### Aggregation strategy

The aggregator walks the `brainbank-extract` derivative tree and produces consolidated files.

#### Morphometrics → parquet

For each `(atlas, metric)` combination, concatenate all sessions' `_morph.tsv` files into a single long-format parquet:

```
aggregated/
├── anat/
│   ├── atlas-schaefer400x7_desc-thickness_morph.parquet
│   ├── atlas-schaefer400x7_desc-area_morph.parquet
│   ├── atlas-schaefer400x7_desc-volume_morph.parquet
│   ├── atlas-aseg_desc-subcortical_morph.parquet
│   └── desc-globalmetrics_morph.parquet
```

Each parquet has columns: `subject`, `session`, + all original TSV columns.

#### Diffusion scalars → parquet

Same pattern:

```
aggregated/
└── dwi/
    └── scalars/
        ├── atlas-schaefer400x7_model-DTI_param-FA_desc-parcellated_diffmetrics.parquet
        ├── atlas-schaefer400x7_model-NODDI_param-ICVF_desc-parcellated_diffmetrics.parquet
        └── ...
```

#### Connectivity matrices → stacked numpy

For each `(atlas, measure)` combination, stack all sessions' 2D matrices into a 3D array:

```
aggregated/
└── dwi/
    └── connectivity/
        ├── atlas-schaefer400x7_desc-sift2_connmatrix.npy      # shape: (N_sessions, N_parcels, N_parcels)
        ├── atlas-schaefer400x7_desc-sift2_connmatrix-meta.parquet  # session index → subject/session
        └── atlas-schaefer400x7_desc-sift2_connmatrix-labels.json
```

The companion `_connmatrix-meta.parquet` maps the first axis index to `(subject, session)`, so researchers can slice by session.

#### Tract profiles → parquet

```
aggregated/
└── dwi/
    └── tractprofiles/
        └── desc-profile_tractmetrics.parquet   # all tracts, all sessions, long format
```

Columns: `subject`, `session`, `tract`, `node`, `FA`, `MD`, ...

### Incremental aggregation

The aggregator maintains a sidecar file `aggregated/.completed_sessions.json` listing which `(subject, session)` pairs have been incorporated. On subsequent runs:

1. Read the sidecar
2. Scan the extract directory for new sessions not in the sidecar
3. If new sessions found: load existing parquet, append new data, rewrite
4. If `--force`: ignore sidecar, re-aggregate everything

For connectivity matrices (numpy), incremental aggregation means loading the existing 3D array, appending new 2D slices along axis 0, and updating the meta parquet.

---

## Python API (for researchers)

The API is the primary interface for downstream analysis. It should be importable as:

```python
import brainbank_extract as bb
```

### Core loading functions

```python
# Load cortical thickness for all sessions, Schaefer 400 atlas
ct = bb.load_morphometrics(
    extract_dir="/derivatives/brainbank-extract/aggregated",
    metric="thickness",
    atlas="schaefer400x7",
)
# Returns: pandas DataFrame in long format
# Columns: subject, session, region_index, region_label, hemisphere, value, metric

# Load connectivity matrices
conn, meta, labels = bb.load_connectivity(
    extract_dir="/derivatives/brainbank-extract/aggregated",
    atlas="schaefer400x7",
    measure="sift2",
)
# conn: np.ndarray, shape (N_sessions, N_parcels, N_parcels)
# meta: pd.DataFrame with subject, session columns (index matches axis 0)
# labels: list of region labels

# Load diffusion scalars
fa = bb.load_diffusion_scalars(
    extract_dir="/derivatives/brainbank-extract/aggregated",
    atlas="schaefer400x7",
    model="DTI",
    param="FA",
)
# Returns: pandas DataFrame, same shape as morphometrics

# Load tract profiles
profiles = bb.load_tract_profiles(
    extract_dir="/derivatives/brainbank-extract/aggregated",
    tract="ArcuateL",  # optional filter
)
# Returns: pandas DataFrame with subject, session, tract, node, FA, MD, ...

# Load global metrics (eTIV, brain volumes)
globals_df = bb.load_global_metrics(
    extract_dir="/derivatives/brainbank-extract/aggregated",
)
# Returns: DataFrame with subject, session, metric, value

# Convenience: list available atlases/metrics/models
bb.list_available(extract_dir="/derivatives/brainbank-extract/aggregated")
# Prints or returns a summary of what's been aggregated
```

### Pivot helper (optional convenience, not stored)

```python
# Researchers who want wide format for ML can do:
ct_wide = bb.to_wide(ct, index=["subject", "session"], columns="region_label", values="value")
# This is just pd.pivot_table under the hood — not a core feature, just a helper
```

---

## Atlas Registry

The package ships with a registry of known atlases and their metadata. This is used for label lookups and validation, not for registration.

```python
# atlases.py
ATLAS_REGISTRY = {
    "schaefer100x7": {
        "full_name": "Schaefer 2018, 100 parcels, 7 networks",
        "type": "surface",
        "n_parcels": 100,
        "freesurfer_annot_pattern": "?h.Schaefer2018_100Parcels_7Networks_order.annot",
        "qsirecon_name": "Schaefer100x7",  # how QSIRecon names it in filenames
    },
    "schaefer200x7": { ... },
    "schaefer400x7": { ... },
    "tian_s1": {
        "full_name": "Tian 2020, Scale I",
        "type": "volumetric",
        "n_parcels": 16,
        "qsirecon_name": "TianS1",
    },
    "tian_s2": { ... },
    "4S156Parcels": {
        "full_name": "4S 156 Parcels",
        "type": "combined",  # surface cortical + volumetric subcortical
        "n_parcels": 156,
        "qsirecon_name": "4S156Parcels",
    },
    # ... 4S256, 4S356, 4S456
    "brainnetome246": { ... },
    "aal116": { ... },
    "gordon333": { ... },
    "desikan": {
        "full_name": "Desikan-Killiany (FreeSurfer default)",
        "type": "surface",
        "n_parcels": 68,
        "freesurfer_annot_pattern": "?h.aparc.annot",
    },
    "destrieux": {
        "full_name": "Destrieux (a2009s)",
        "type": "surface",
        "n_parcels": 148,
        "freesurfer_annot_pattern": "?h.aparc.a2009s.annot",
    },
    "aseg": {
        "full_name": "FreeSurfer automatic subcortical segmentation",
        "type": "volumetric",
        "n_parcels": 45,  # approximately
    },
}
```

The registry is extensible: researchers can register custom atlases at runtime.

---

## Docker Container

### Purpose

The Docker container wraps `bb-extract` for reproducible execution on the Slurm cluster. It contains all Python dependencies (nibabel, numpy, pandas, pyarrow, etc.) but does NOT contain FreeSurfer or QSIRecon themselves — it only reads their outputs.

### Dockerfile sketch

```dockerfile
FROM python:3.11-slim

RUN pip install brainbank-extract

ENTRYPOINT ["bb-extract"]
```

The container is intentionally minimal — no neuroimaging tools, no large dependencies. It's a reader/parser, not a processor.

### Slurm integration

A typical Slurm job script:

```bash
#!/bin/bash
#SBATCH --job-name=bb-extract
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:30:00

apptainer run \
  --bind /derivatives:/derivatives \
  brainbank-extract.sif \
  bb-extract \
    --freesurfer-dir /derivatives/freesurfer/${SUBJECT}/${SESSION} \
    --qsirecon-dir /derivatives/qsirecon/${SUBJECT}/${SESSION} \
    --output-dir /derivatives/brainbank-extract/${SUBJECT}/${SESSION} \
    --atlases schaefer400x7 tian_s2 brainnetome246 \
    --subject ${SUBJECT} \
    --session ${SESSION}
```

This integrates naturally with the `snbb_scheduler` — the scheduler submits these jobs after QSIRecon completes.

---

## Package Structure

```
brainbank-extract/
├── pyproject.toml
├── README.md
├── Dockerfile
├── src/
│   └── brainbank_extract/
│       ├── __init__.py           # re-exports API functions
│       ├── cli.py                # click CLI: bb-extract, bb-aggregate
│       ├── extractors/
│       │   ├── __init__.py
│       │   ├── freesurfer.py     # FreeSurfer stats/surface extraction
│       │   └── qsirecon.py       # QSIRecon parcellation/connectivity extraction
│       ├── aggregator.py         # dataset-level concatenation
│       ├── atlases.py            # atlas registry and label lookups
│       ├── io.py                 # parquet/numpy read-write helpers
│       └── api.py                # researcher-facing load functions
├── tests/
│   ├── conftest.py               # fixtures: mock FreeSurfer/QSIRecon directory trees
│   ├── test_freesurfer.py
│   ├── test_qsirecon.py
│   ├── test_aggregator.py
│   └── test_api.py
└── examples/
    └── quickstart.ipynb          # "Load all cortical thickness data in 3 lines"
```

### Dependencies

```toml
[project]
dependencies = [
    "nibabel>=4.0",
    "numpy>=1.24",
    "pandas>=2.0",
    "pyarrow>=14.0",
    "click>=8.0",
]

[project.optional-dependencies]
dev = ["pytest", "pytest-tmp-files"]

[project.scripts]
bb-extract = "brainbank_extract.cli:extract"
bb-aggregate = "brainbank_extract.cli:aggregate"
```

No heavy neuroimaging dependencies (no nilearn, no dipy, no freesurfer-python). This package reads files, it doesn't process images.

---

## Integration with Existing Infrastructure

### snbb_scheduler

Add a new rule to `snbb_scheduler` that triggers `bb-extract` after both FreeSurfer and QSIRecon are complete for a session:

```python
def check_brainbank_extract(session: Session) -> bool:
    """Check if brainbank-extract has already run."""
    extract_dir = session.derivatives / "brainbank-extract" / session.subject / session.session
    return (extract_dir / "anat").exists() and (extract_dir / "dwi").exists()

def rule_brainbank_extract(session: Session) -> Optional[Task]:
    """Submit bb-extract if FreeSurfer + QSIRecon are done but extract hasn't run."""
    if not check_freesurfer_complete(session):
        return None
    if not check_qsirecon_complete(session):
        return None
    if check_brainbank_extract(session):
        return None
    return Task(procedure="brainbank-extract", session=session)
```

### fsatlas

`brainbank-extract` subsumes much of what `fsatlas` does for FreeSurfer morphometrics. The migration path:

1. v1: `brainbank-extract` can optionally read `fsatlas` output TSVs directly (if they already exist) instead of re-extracting from FreeSurfer surfaces
2. v2: The FreeSurfer extraction logic from `fsatlas` is incorporated into `brainbank-extract`, and `fsatlas` is retired or becomes a thin wrapper

### neuroalign-preprocessing

The existing aggregation loaders in `neuroalign-preprocessing` are replaced by `bb-aggregate` + the Python API. The `ParquetCache`, SQLite buffering, and complex loader classes become unnecessary.

---

## Error Handling and Edge Cases

### Missing data

- If FreeSurfer dir doesn't exist for a session → skip anatomical extraction, log warning
- If QSIRecon dir doesn't exist → skip diffusion extraction, log warning
- If a specific atlas annotation is missing → skip that atlas, log warning
- If a QSIRecon model/param combination doesn't exist (e.g., no NODDI) → skip, log warning
- All warnings are collected and written to `bb-extract.log` in the session output directory

### Validation

After extraction, validate:
- Each TSV has > 0 rows
- Connectivity matrices are square and symmetric (within tolerance)
- Region counts match expected parcel count from atlas registry
- No NaN-only columns

Write a `_status.json` sidecar per session:

```json
{
  "subject": "sub-001",
  "session": "ses-20240101",
  "extraction_date": "2026-03-08T12:00:00",
  "brainbank_extract_version": "0.1.0",
  "atlases_extracted": ["schaefer400x7", "aseg"],
  "atlases_skipped": ["tian_s2"],
  "modalities": {
    "anat": {"status": "complete", "n_files": 7},
    "dwi_scalars": {"status": "complete", "n_files": 12},
    "dwi_connectivity": {"status": "complete", "n_files": 4},
    "dwi_tractprofiles": {"status": "skipped", "reason": "no pyAFQ outputs"}
  },
  "warnings": ["Atlas tian_s2 annotation not found in FreeSurfer directory"]
}
```

---

## Implementation Order

### Phase 1: Core extraction — FreeSurfer

1. Set up package skeleton (`pyproject.toml`, `src` layout, CLI stubs)
2. Implement atlas registry
3. Implement FreeSurfer extractor:
   - `aseg.stats` parser (subcortical volumes + global metrics)
   - Surface annotation-based parcellation (read `.annot` + vertex data)
4. Write tests with mock FreeSurfer directory trees
5. Verify output TSVs match spec

### Phase 2: Core extraction — QSIRecon

1. Implement QSIRecon extractor:
   - Parcellated scalar TSV discovery and renaming
   - Connectivity matrix extraction and .npy conversion
   - Tract profile extraction (if pyAFQ outputs present)
2. Write tests with mock QSIRecon directory trees

### Phase 3: Aggregation

1. Implement `bb-aggregate` CLI
2. Parquet concatenation for morphometrics and diffusion scalars
3. 3D numpy stacking for connectivity matrices
4. Incremental aggregation with sidecar tracking
5. Write tests

### Phase 4: Python API

1. Implement `load_morphometrics()`, `load_connectivity()`, etc.
2. Implement `list_available()`
3. Write quickstart notebook

### Phase 5: Docker + integration

1. Dockerfile
2. Slurm job template
3. `snbb_scheduler` rule
4. Integration test with real data (1-2 sessions)

---

## Open Design Decisions

These are intentionally left for implementation time:

1. **Should `bb-extract` also compute distributional metrics (skewness, bimodality coefficient, Q-Q R²)?** These are relevant to the ROI summary statistics paper, but may belong in a separate analysis step rather than in the extraction layer.

2. **fsatlas integration strategy**: Should v1 call `fsatlas` as a dependency, read its outputs, or reimplement? Recommendation: read its outputs if they exist, implement a minimal fallback otherwise.

3. **Parallel extraction within a session**: Most sessions have multiple atlases. Should the extractor parallelize across atlases? Likely unnecessary at v1 — extraction is I/O-bound and fast per session.

4. **Atlas label file shipping**: Should the package ship its own copy of atlas label files (e.g., Schaefer `.annot` files), or require them to be present in the FreeSurfer subject directory? Shipping them increases package size but makes it self-contained.
