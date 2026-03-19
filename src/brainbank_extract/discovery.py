"""Session auto-discovery for batch extraction.

Scans FreeSurfer and QSIRecon derivative directories to enumerate all
available (subject, session) pairs without requiring the caller to script
external loops.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SessionInfo:
    """Holds paths and identifiers for one extractable session.

    Attributes
    ----------
    subject:
        BIDS subject identifier (e.g. ``"sub-001"``).
    session:
        BIDS session identifier (e.g. ``"ses-20240101"``).
    freesurfer_dir:
        Path to the FreeSurfer subject/session directory, or ``None`` if
        FreeSurfer outputs are not available for this session.
    qsirecon_dir:
        Path to the **root** QSIRecon derivatives directory (passed to
        ``QSIReconExtractor``), or ``None`` if QSIRecon outputs are not
        available for this session.
    """

    subject: str
    session: str
    freesurfer_dir: Path | None = field(default=None)
    qsirecon_dir: Path | None = field(default=None)


def discover_freesurfer_sessions(
    fs_root: Path,
) -> dict[tuple[str, str], Path]:
    """Discover all cross-sectional FreeSurfer session directories.

    Scans ``fs_root`` for flat session directories of the form
    ``sub-XXX_ses-YYY/``.  Longitudinal directories (``*.long.*``),
    template directories (``sub-XXX/`` with no session component), and
    non-subject entries (e.g. ``fsaverage``) are excluded.

    Parameters
    ----------
    fs_root:
        Root FreeSurfer derivatives directory (contains session dirs directly).

    Returns
    -------
    dict mapping ``(subject, session)`` tuples to their full directory paths.
    """
    result: dict[tuple[str, str], Path] = {}
    for d in sorted(fs_root.iterdir()):
        if not d.is_dir():
            continue
        name = d.name
        # Exclude non-subject dirs (fsaverage, fsaverage6, ...)
        if not name.startswith("sub-"):
            continue
        # Exclude longitudinal dirs (sub-XXX_ses-YYY.long.sub-XXX)
        if ".long." in name:
            continue
        # Require a session component (exclude template dirs like sub-XXX)
        if "_ses-" not in name:
            continue
        subject, session = _parse_flat_session_dir(name)
        if subject and session:
            result[(subject, session)] = d
    return result


def discover_qsirecon_sessions(
    qsirecon_root: Path,
) -> dict[tuple[str, str], Path]:
    """Discover all QSIRecon sessions in a BIDS-layout root directory.

    Scans ``qsirecon_root/sub-*/ses-*/dwi/`` for valid session directories.
    The returned path is always ``qsirecon_root`` (not the session-level
    directory) because ``QSIReconExtractor`` takes the root as input.

    Parameters
    ----------
    qsirecon_root:
        Root QSIRecon derivatives directory.

    Returns
    -------
    dict mapping ``(subject, session)`` tuples to ``qsirecon_root``.
    """
    result: dict[tuple[str, str], Path] = {}
    for sub_dir in sorted(qsirecon_root.glob("sub-*")):
        if not sub_dir.is_dir():
            continue
        subject = sub_dir.name
        for ses_dir in sorted(sub_dir.glob("ses-*")):
            if not ses_dir.is_dir():
                continue
            # Only include if a dwi directory exists (confirms QSIRecon ran)
            if not (ses_dir / "dwi").exists():
                continue
            session = ses_dir.name
            result[(subject, session)] = qsirecon_root
    return result


def discover_sessions(
    freesurfer_root: Path | None,
    qsirecon_root: Path | None,
    subjects: list[str] | None = None,
    sessions: list[str] | None = None,
) -> list[SessionInfo]:
    """Discover all available sessions across FreeSurfer and QSIRecon outputs.

    Takes the union of sessions found in either (or both) pipelines.  A
    session that exists in only one pipeline will have ``None`` for the
    missing pipeline's directory.

    Parameters
    ----------
    freesurfer_root:
        Root FreeSurfer derivatives directory, or ``None`` to skip.
    qsirecon_root:
        Root QSIRecon derivatives directory, or ``None`` to skip.
    subjects:
        If provided, only include sessions for these subject identifiers
        (e.g. ``["sub-001", "sub-002"]``).
    sessions:
        If provided, only include these session identifiers
        (e.g. ``["ses-20240101"]``).

    Returns
    -------
    list of :class:`SessionInfo`, sorted by ``(subject, session)``.
    """
    fs_sessions: dict[tuple[str, str], Path] = {}
    qsi_sessions: dict[tuple[str, str], Path] = {}

    if freesurfer_root is not None and freesurfer_root.exists():
        fs_sessions = discover_freesurfer_sessions(freesurfer_root)

    if qsirecon_root is not None and qsirecon_root.exists():
        qsi_sessions = discover_qsirecon_sessions(qsirecon_root)

    all_keys = sorted(set(fs_sessions) | set(qsi_sessions))

    result: list[SessionInfo] = []
    for subject, session in all_keys:
        if subjects and subject not in subjects:
            continue
        if sessions and session not in sessions:
            continue
        result.append(
            SessionInfo(
                subject=subject,
                session=session,
                freesurfer_dir=fs_sessions.get((subject, session)),
                qsirecon_dir=qsi_sessions.get((subject, session)),
            )
        )
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FLAT_SESSION_RE = re.compile(r"^(sub-[^_]+)_(ses-.+)$")


def _parse_flat_session_dir(name: str) -> tuple[str, str] | tuple[None, None]:
    """Parse ``sub-XXX_ses-YYY`` dirname into ``(subject, session)``."""
    m = _FLAT_SESSION_RE.match(name)
    if m:
        return m.group(1), m.group(2)
    return None, None
