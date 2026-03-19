# Plan: Auto-Discovery of Subjects/Sessions for `bb-extract`

## Context

Currently `bb-extract` processes a single subject/session per invocation, requiring explicit `--freesurfer-dir`, `--qsirecon-dir`, `--subject`, and `--session` flags. To process an entire dataset, users must script external loops. This change adds batch mode as the default behavior: point at root directories and extract all available sessions automatically.

## Key Observations

- **FreeSurfer** uses flat dirs: `<root>/sub-XXX_ses-YYY/` for cross-sectional participants (also has `sub-XXX/` template dirs to exclude). For longitudinal participants, we should use the `sub-XXX/ses-YYY.long.*` dirs (since they contain the longitudinal stats).
- **QSIRecon** uses BIDS hierarchy: `<root>/sub-XXX/ses-YYY/dwi/`
- The `QSIReconExtractor` already takes the root dir (not session-level), while `FreeSurferExtractor` takes a session-level dir
- Extractors are instantiated per-session — this doesn't change

## Changes

### 1. New module: `src/brainbank_extract/discovery.py`

```python
def discover_freesurfer_sessions(fs_root: Path) -> dict[tuple[str, str], Path]:
    """Glob sub-*_ses-*, exclude *.long.*, parse (subject, session) -> session_dir."""

def discover_qsirecon_sessions(qsirecon_root: Path) -> dict[tuple[str, str], Path]:
    """Glob sub-*/ses-*/, parse (subject, session) -> qsirecon_root (constant)."""

def discover_sessions(
    freesurfer_root: Path | None,
    qsirecon_root: Path | None,
) -> list[SessionInfo]:
    """Union sessions from both pipelines. Returns list of dataclass/NamedTuple with:
    subject, session, freesurfer_dir (Path|None), qsirecon_dir (Path|None)."""
```

FreeSurfer parsing: split dirname on `_ses-` → `(sub-XXX, ses-YYY)`, map to full path.
QSIRecon parsing: `sub-*/ses-*/` from root, the qsirecon_dir for the extractor is always the root.

### 2. CLI changes: `src/brainbank_extract/cli.py`

Add new options to `bb-extract`:

| Option | Purpose |
|--------|---------|
| `--freesurfer-root` | Root FreeSurfer derivatives dir (replaces `--freesurfer-dir` in batch mode) |
| `--subjects` | Filter: only these subjects (multiple allowed, optional) |
| `--sessions` | Filter: only these sessions (multiple allowed, optional) |
| `--skip-existing` | Skip sessions with existing output dirs |

**Mode detection:**
- `--subject` + `--session` provided → **single-session mode** (current behavior, unchanged)
- Otherwise → **batch mode** using `--freesurfer-root` and/or `--qsirecon-dir`

Note: `--qsirecon-dir` already points to the root, so no rename needed. Only FreeSurfer needs a new `--freesurfer-root` option. Keep `--freesurfer-dir` for single-session mode.

**Batch mode output:** `--output-dir` becomes the root; per-session outputs go to `output_dir/sub-XXX/ses-YYY/`.

**Batch loop:** iterate sessions, run extraction per session, catch exceptions per session (never stop on failure), collect statuses, print summary at end.

### 3. Tests: `tests/test_discovery.py`

- Test `discover_freesurfer_sessions`: creates flat dirs including `.long.` and template dirs, verifies only session dirs returned
- Test `discover_qsirecon_sessions`: creates BIDS hierarchy, verifies all sessions found
- Test `discover_sessions`: both pipelines, verifies union behavior (sessions in one but not other)
- Test subject/session filtering
- Test CLI batch mode integration (mock extractors, verify all sessions processed)

### 4. Files Modified

| File | Change |
|------|--------|
| `src/brainbank_extract/discovery.py` | **New** — session discovery logic |
| `src/brainbank_extract/cli.py` | Add batch mode options and loop |
| `tests/test_discovery.py` | **New** — discovery + batch CLI tests |

No changes to extractors, atlases, or existing test files.

## Verification

1. `uv run pytest tests/test_discovery.py -v` — new discovery tests pass
2. `uv run pytest` — all existing tests still pass (no regressions)
3. Smoke test single-session mode still works:
   ```bash
   uv run bb-extract --freesurfer-dir data/freesurfer/sub-CLMC10_ses-202407110849 \
     --qsirecon-dir data/qsirecon --output-dir /tmp/bb-single \
     --atlases schaefer400x7 --subject sub-CLMC10 --session ses-202407110849
   ```
4. Smoke test batch mode:
   ```bash
   uv run bb-extract --freesurfer-root data/freesurfer \
     --qsirecon-dir data/qsirecon --output-dir /tmp/bb-batch \
     --atlases schaefer400x7 --skip-existing
   ```
