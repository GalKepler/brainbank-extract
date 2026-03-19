"""Dataset-level aggregation of per-session extraction outputs."""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from brainbank_extract.io import (
    read_labels_json,
    read_npy,
    read_parquet,
    write_labels_json,
    write_npy,
    write_parquet,
)

logger = logging.getLogger(__name__)

_BIDS_ENTITY_RE = re.compile(r"_([a-zA-Z]+)-([^_\.]+)")


class Aggregator:
    """Aggregates per-session brainbank-extract outputs into consolidated files.

    Parameters
    ----------
    extract_dir:
        Root directory containing per-session extraction outputs
        (``sub-*/ses-*`` subdirectories).
    output_dir:
        Directory where aggregated parquet/npy files will be written.
    modalities:
        List of modalities to aggregate: ``"anat"`` and/or ``"dwi"``.
    force:
        If True, re-aggregate all sessions even if previously processed.
    """

    SIDECAR_FILENAME = ".completed_sessions.json"

    def __init__(
        self,
        extract_dir: Path,
        output_dir: Path,
        modalities: Optional[list[str]] = None,
        force: bool = False,
    ) -> None:
        self.extract_dir = Path(extract_dir)
        self.output_dir = Path(output_dir)
        self.modalities = modalities or ["anat", "dwi"]
        self.force = force

    def run(self) -> dict:
        """Run the full aggregation pipeline.

        Returns
        -------
        dict with key ``new_sessions`` (int): number of sessions processed.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)

        completed = set() if self.force else self._load_completed_sessions()
        all_sessions = self._discover_sessions()

        new_sessions = [
            (sub, ses, path)
            for sub, ses, path in all_sessions
            if (sub, ses) not in completed
        ]

        if not new_sessions:
            logger.info("No new sessions to aggregate.")
            return {"new_sessions": 0}

        if "anat" in self.modalities:
            self._aggregate_anat(new_sessions)
        if "dwi" in self.modalities:
            self._aggregate_dwi_scalars(new_sessions)
            self._aggregate_dwi_connectivity(new_sessions)

        completed.update((sub, ses) for sub, ses, _ in new_sessions)
        self._save_completed_sessions(completed)

        return {"new_sessions": len(new_sessions)}

    # ------------------------------------------------------------------
    # Anat aggregation
    # ------------------------------------------------------------------

    def _aggregate_anat(self, sessions: list[tuple[str, str, Path]]) -> None:
        groups: dict[tuple, list[dict]] = defaultdict(list)
        for subject, session, ses_dir in sessions:
            for rec in self._find_anat_tsvs(ses_dir):
                rec["subject"] = subject
                rec["session"] = session
                groups[rec["key"]].append(rec)

        anat_out = self.output_dir / "anat"
        for key, records in groups.items():
            fname = self._anat_parquet_name(key)
            out_path = anat_out / fname
            new_df = self._concat_tsvs(records)
            df = self._merge_incremental(out_path, new_df)
            write_parquet(df, out_path)
            logger.info("Wrote %s (%d rows)", out_path.name, len(df))

    def _find_anat_tsvs(self, ses_dir: Path) -> list[dict]:
        records = []
        anat_dir = ses_dir / "anat"
        if not anat_dir.exists():
            return records
        for path in sorted(anat_dir.glob("**/*_morph.tsv")):
            name = path.name
            entities = _parse_bids_entities(name)
            desc = entities.get("desc", "")
            atlas = entities.get("atlas")
            if desc == "globalmetrics":
                key = ("globalmetrics",)
            elif atlas == "aseg":
                key = ("aseg", desc)
            else:
                key = (atlas, desc)
            records.append({"path": path, "key": key})
        return records

    @staticmethod
    def _anat_parquet_name(key: tuple) -> str:
        if key == ("globalmetrics",):
            return "desc-globalmetrics_morph.parquet"
        if len(key) == 2 and key[0] == "aseg":
            return f"atlas-aseg_desc-{key[1]}_morph.parquet"
        atlas, desc = key
        return f"atlas-{atlas}_desc-{desc}_morph.parquet"

    # ------------------------------------------------------------------
    # DWI scalar aggregation
    # ------------------------------------------------------------------

    def _aggregate_dwi_scalars(self, sessions: list[tuple[str, str, Path]]) -> None:
        groups: dict[tuple, list[dict]] = defaultdict(list)
        for subject, session, ses_dir in sessions:
            for rec in self._find_scalar_tsvs(ses_dir):
                rec["subject"] = subject
                rec["session"] = session
                groups[rec["key"]].append(rec)

        scalars_out = self.output_dir / "dwi" / "scalars"
        for key, records in groups.items():
            pipeline, atlas, model, param = key
            fname = (
                f"pipeline-{pipeline}_atlas-{atlas}"
                f"_model-{model}_param-{param}"
                f"_desc-parcellated_diffmetrics.parquet"
            )
            out_path = scalars_out / fname
            new_df = self._concat_tsvs(records)
            df = self._merge_incremental(out_path, new_df)
            write_parquet(df, out_path)
            logger.info("Wrote %s (%d rows)", out_path.name, len(df))

    def _find_scalar_tsvs(self, ses_dir: Path) -> list[dict]:
        records = []
        scalars_dir = ses_dir / "dwi" / "scalars"
        if not scalars_dir.exists():
            return records
        for path in sorted(scalars_dir.glob("**/*_diffmetrics.tsv")):
            # Extract atlas and pipeline from directory names to handle underscores in values
            # Layout: scalars/pipeline-{pipeline}/atlas-{atlas}/{filename}
            atlas_dir = path.parent
            pipeline_dir = atlas_dir.parent
            atlas = atlas_dir.name.removeprefix("atlas-") if atlas_dir.name.startswith("atlas-") else None
            pipeline = pipeline_dir.name.removeprefix("pipeline-") if pipeline_dir.name.startswith("pipeline-") else None
            # model and param must come from the filename (no ambiguity — no underscores)
            entities = _parse_bids_entities(path.name)
            model = entities.get("model")
            param = entities.get("param")
            if not all([atlas, pipeline, model, param]):
                logger.warning("Skipping scalar TSV with missing entities: %s", path)
                continue
            records.append({
                "path": path,
                "key": (pipeline, atlas, model, param),
            })
        return records

    # ------------------------------------------------------------------
    # DWI connectivity aggregation
    # ------------------------------------------------------------------

    def _aggregate_dwi_connectivity(self, sessions: list[tuple[str, str, Path]]) -> None:
        groups: dict[tuple, list[dict]] = defaultdict(list)
        for subject, session, ses_dir in sessions:
            for rec in self._find_connectivity_npys(ses_dir):
                rec["subject"] = subject
                rec["session"] = session
                groups[rec["key"]].append(rec)

        conn_out = self.output_dir / "dwi" / "connectivity"
        for key, records in groups.items():
            pipeline, atlas, desc = key
            base = f"pipeline-{pipeline}_atlas-{atlas}_desc-{desc}_connmatrix"
            npy_path = conn_out / f"{base}.npy"
            meta_path = conn_out / f"{base}-meta.parquet"
            labels_path = conn_out / f"{base}-labels.json"

            reference_labels = read_labels_json(records[0]["labels_path"])

            new_matrices = []
            new_meta_rows = []
            for rec in records:
                session_labels = read_labels_json(rec["labels_path"])
                if session_labels != reference_labels:
                    logger.warning(
                        "Label mismatch for %s/%s atlas-%s — skipping",
                        rec["subject"], rec["session"], atlas,
                    )
                    continue
                matrix = read_npy(rec["path"])
                if matrix.shape[0] != matrix.shape[1]:
                    logger.warning(
                        "Non-square matrix for %s/%s atlas-%s — skipping",
                        rec["subject"], rec["session"], atlas,
                    )
                    continue
                if not np.allclose(matrix, matrix.T, atol=1e-6):
                    logger.warning(
                        "Asymmetric matrix for %s/%s atlas-%s — proceeding anyway",
                        rec["subject"], rec["session"], atlas,
                    )
                new_matrices.append(matrix)
                new_meta_rows.append({"subject": rec["subject"], "session": rec["session"]})

            if not new_matrices:
                continue

            new_stack = np.stack(new_matrices)

            if npy_path.exists():
                existing = read_npy(npy_path)
                existing_meta = read_parquet(meta_path)
                start_idx = len(existing_meta)
                stacked = np.concatenate([existing, new_stack], axis=0)
                new_meta_df = pd.DataFrame(new_meta_rows)
                new_meta_df.insert(
                    0, "session_index",
                    range(start_idx, start_idx + len(new_meta_rows))
                )
                meta_df = pd.concat([existing_meta, new_meta_df], ignore_index=True)
            else:
                stacked = new_stack
                meta_df = pd.DataFrame(new_meta_rows)
                meta_df.insert(0, "session_index", range(len(new_meta_rows)))

            conn_out.mkdir(parents=True, exist_ok=True)
            write_npy(stacked, npy_path)
            write_parquet(meta_df, meta_path)
            write_labels_json(reference_labels, labels_path)
            logger.info("Wrote %s: shape %s", npy_path.name, stacked.shape)

    def _find_connectivity_npys(self, ses_dir: Path) -> list[dict]:
        records = []
        conn_dir = ses_dir / "dwi" / "connectivity"
        if not conn_dir.exists():
            return records
        for path in sorted(conn_dir.glob("**/*_connmatrix.npy")):
            labels_path = path.with_name(
                path.name.replace("_connmatrix.npy", "_connmatrix-labels.json")
            )
            if not labels_path.exists():
                logger.warning("No labels JSON for %s — skipping", path)
                continue
            # Extract atlas and pipeline from directory names (handles underscores in values)
            # Layout: connectivity/pipeline-{pipeline}/atlas-{atlas}/{filename}
            atlas_dir = path.parent
            pipeline_dir = atlas_dir.parent
            atlas = atlas_dir.name.removeprefix("atlas-") if atlas_dir.name.startswith("atlas-") else None
            pipeline = pipeline_dir.name.removeprefix("pipeline-") if pipeline_dir.name.startswith("pipeline-") else None
            # desc from filename (no underscores in measure names like "sift2", "count")
            entities = _parse_bids_entities(path.name)
            desc = entities.get("desc")
            if not all([atlas, pipeline, desc]):
                logger.warning("Skipping connectivity npy with missing entities: %s", path)
                continue
            records.append({
                "path": path,
                "labels_path": labels_path,
                "key": (pipeline, atlas, desc),
            })
        return records

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _concat_tsvs(records: list[dict]) -> pd.DataFrame:
        """Read TSVs from records and concat with subject/session columns prepended."""
        frames = []
        for rec in records:
            df = pd.read_csv(rec["path"], sep="\t")
            df.insert(0, "session", rec["session"])
            df.insert(0, "subject", rec["subject"])
            frames.append(df)
        return pd.concat(frames, ignore_index=True)

    @staticmethod
    def _merge_incremental(out_path: Path, new_df: pd.DataFrame) -> pd.DataFrame:
        """If an existing parquet exists, append new rows to it."""
        if out_path.exists():
            existing = read_parquet(out_path)
            return pd.concat([existing, new_df], ignore_index=True)
        return new_df

    def _load_completed_sessions(self) -> set[tuple[str, str]]:
        """Load the set of already-aggregated (subject, session) pairs."""
        sidecar = self.output_dir / self.SIDECAR_FILENAME
        if not sidecar.exists():
            return set()
        with open(sidecar) as f:
            data = json.load(f)
        return {tuple(pair) for pair in data}

    def _save_completed_sessions(self, completed: set[tuple[str, str]]) -> None:
        """Persist the set of aggregated (subject, session) pairs."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        sidecar = self.output_dir / self.SIDECAR_FILENAME
        with open(sidecar, "w") as f:
            json.dump(sorted(completed), f, indent=2)

    def _discover_sessions(self) -> list[tuple[str, str, Path]]:
        """Walk the extract directory and return (subject, session, path) tuples."""
        sessions = []
        if not self.extract_dir.exists():
            return sessions
        for sub_dir in sorted(self.extract_dir.glob("sub-*")):
            if not sub_dir.is_dir():
                continue
            for ses_dir in sorted(sub_dir.glob("ses-*")):
                if not ses_dir.is_dir():
                    continue
                sessions.append((sub_dir.name, ses_dir.name, ses_dir))
        return sessions


def _parse_bids_entities(filename: str) -> dict[str, str]:
    """Extract BIDS key-value entities from a filename."""
    return dict(_BIDS_ENTITY_RE.findall(filename))
