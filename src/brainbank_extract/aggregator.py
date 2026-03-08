"""Dataset-level aggregation of per-session extraction outputs."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


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

    def run(self) -> None:
        """Run the full aggregation pipeline.

        Raises
        ------
        NotImplementedError
            Until aggregation is implemented.
        """
        raise NotImplementedError(
            "Aggregator.run() is not yet implemented. "
            "This will scan the extract directory and produce consolidated parquet/npy files."
        )

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
        for sub_dir in sorted(self.extract_dir.glob("sub-*")):
            if not sub_dir.is_dir():
                continue
            for ses_dir in sorted(sub_dir.glob("ses-*")):
                if not ses_dir.is_dir():
                    continue
                sessions.append((sub_dir.name, ses_dir.name, ses_dir))
        return sessions
