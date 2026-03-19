"""Tests for session auto-discovery."""

from __future__ import annotations

from pathlib import Path

import pytest

from brainbank_extract.discovery import (
    SessionInfo,
    _parse_flat_session_dir,
    discover_freesurfer_sessions,
    discover_qsirecon_sessions,
    discover_sessions,
)


# ---------------------------------------------------------------------------
# _parse_flat_session_dir
# ---------------------------------------------------------------------------


def test_parse_valid_flat_dir() -> None:
    subject, session = _parse_flat_session_dir("sub-001_ses-20240101")
    assert subject == "sub-001"
    assert session == "ses-20240101"


def test_parse_valid_flat_dir_complex_session() -> None:
    subject, session = _parse_flat_session_dir("sub-CLMC10_ses-202407110849")
    assert subject == "sub-CLMC10"
    assert session == "ses-202407110849"


def test_parse_invalid_no_session() -> None:
    subject, session = _parse_flat_session_dir("sub-001")
    assert subject is None
    assert session is None


def test_parse_invalid_fsaverage() -> None:
    subject, session = _parse_flat_session_dir("fsaverage")
    assert subject is None
    assert session is None


def test_parse_longitudinal_matches_but_caller_filters() -> None:
    # The regex matches (ses-.+ captures the full longitudinal suffix),
    # but discover_freesurfer_sessions excludes .long. dirs before calling this.
    subject, session = _parse_flat_session_dir("sub-001_ses-20240101.long.sub-001")
    assert subject == "sub-001"
    assert "20240101" in session  # session contains the .long. suffix


# ---------------------------------------------------------------------------
# discover_freesurfer_sessions
# ---------------------------------------------------------------------------


@pytest.fixture
def fs_root(tmp_path: Path) -> Path:
    root = tmp_path / "freesurfer"
    root.mkdir()
    # Valid session dirs
    (root / "sub-001_ses-20240101").mkdir()
    (root / "sub-001_ses-20240601").mkdir()
    (root / "sub-002_ses-20240101").mkdir()
    # Longitudinal dirs — should be excluded
    (root / "sub-001_ses-20240101.long.sub-001").mkdir()
    # Template dirs (no ses component) — should be excluded
    (root / "sub-001").mkdir()
    # Non-subject dirs — should be excluded
    (root / "fsaverage").mkdir()
    (root / "fsaverage6").mkdir()
    # A file (not a dir) — should be ignored
    (root / "README.txt").write_text("ignore me")
    return root


def test_discover_freesurfer_sessions_finds_valid(fs_root: Path) -> None:
    result = discover_freesurfer_sessions(fs_root)
    assert ("sub-001", "ses-20240101") in result
    assert ("sub-001", "ses-20240601") in result
    assert ("sub-002", "ses-20240101") in result


def test_discover_freesurfer_sessions_count(fs_root: Path) -> None:
    result = discover_freesurfer_sessions(fs_root)
    assert len(result) == 3


def test_discover_freesurfer_sessions_excludes_longitudinal(fs_root: Path) -> None:
    result = discover_freesurfer_sessions(fs_root)
    assert all(".long." not in str(p) for p in result.values())


def test_discover_freesurfer_sessions_excludes_template(fs_root: Path) -> None:
    result = discover_freesurfer_sessions(fs_root)
    assert ("sub-001", None) not in result
    for key in result:
        assert key[1] is not None


def test_discover_freesurfer_sessions_excludes_non_subject(fs_root: Path) -> None:
    result = discover_freesurfer_sessions(fs_root)
    for subject, _ in result:
        assert subject.startswith("sub-")


def test_discover_freesurfer_sessions_paths_are_dirs(fs_root: Path) -> None:
    result = discover_freesurfer_sessions(fs_root)
    for path in result.values():
        assert path.is_dir()


def test_discover_freesurfer_sessions_paths_match_keys(fs_root: Path) -> None:
    result = discover_freesurfer_sessions(fs_root)
    for (subject, session), path in result.items():
        assert path.name == f"{subject}_{session}"


def test_discover_freesurfer_sessions_empty_dir(tmp_path: Path) -> None:
    root = tmp_path / "empty_fs"
    root.mkdir()
    result = discover_freesurfer_sessions(root)
    assert result == {}


# ---------------------------------------------------------------------------
# discover_qsirecon_sessions
# ---------------------------------------------------------------------------


@pytest.fixture
def qsi_root(tmp_path: Path) -> Path:
    root = tmp_path / "qsirecon"
    root.mkdir()
    # Valid sessions: sub-*/ses-*/dwi exists
    (root / "sub-001" / "ses-20240101" / "dwi").mkdir(parents=True)
    (root / "sub-001" / "ses-20240601" / "dwi").mkdir(parents=True)
    (root / "sub-002" / "ses-20240101" / "dwi").mkdir(parents=True)
    # Session dir without dwi — should be excluded
    (root / "sub-003" / "ses-20240101").mkdir(parents=True)
    # derivatives/ dir — should be ignored (no ses-* inside sub-*)
    (root / "derivatives").mkdir()
    return root


def test_discover_qsirecon_sessions_finds_valid(qsi_root: Path) -> None:
    result = discover_qsirecon_sessions(qsi_root)
    assert ("sub-001", "ses-20240101") in result
    assert ("sub-001", "ses-20240601") in result
    assert ("sub-002", "ses-20240101") in result


def test_discover_qsirecon_sessions_count(qsi_root: Path) -> None:
    result = discover_qsirecon_sessions(qsi_root)
    assert len(result) == 3


def test_discover_qsirecon_sessions_excludes_no_dwi(qsi_root: Path) -> None:
    result = discover_qsirecon_sessions(qsi_root)
    assert ("sub-003", "ses-20240101") not in result


def test_discover_qsirecon_sessions_returns_root(qsi_root: Path) -> None:
    """Values must be the root dir, not the session-level dir."""
    result = discover_qsirecon_sessions(qsi_root)
    for path in result.values():
        assert path == qsi_root


def test_discover_qsirecon_sessions_empty_dir(tmp_path: Path) -> None:
    root = tmp_path / "empty_qsi"
    root.mkdir()
    result = discover_qsirecon_sessions(root)
    assert result == {}


# ---------------------------------------------------------------------------
# discover_sessions — union behaviour
# ---------------------------------------------------------------------------


@pytest.fixture
def both_roots(tmp_path: Path) -> tuple[Path, Path]:
    """FS has 3 sessions; QSI has 2 overlapping + 1 QSI-only."""
    fs_root = tmp_path / "freesurfer"
    fs_root.mkdir()
    (fs_root / "sub-001_ses-20240101").mkdir()
    (fs_root / "sub-001_ses-20240601").mkdir()
    (fs_root / "sub-002_ses-20240101").mkdir()

    qsi_root = tmp_path / "qsirecon"
    qsi_root.mkdir()
    (qsi_root / "sub-001" / "ses-20240101" / "dwi").mkdir(parents=True)
    (qsi_root / "sub-002" / "ses-20240101" / "dwi").mkdir(parents=True)
    # QSI-only session
    (qsi_root / "sub-003" / "ses-20240101" / "dwi").mkdir(parents=True)

    return fs_root, qsi_root


def test_discover_sessions_union(both_roots: tuple[Path, Path]) -> None:
    fs_root, qsi_root = both_roots
    result = discover_sessions(fs_root, qsi_root)
    keys = {(s.subject, s.session) for s in result}
    assert ("sub-001", "ses-20240101") in keys
    assert ("sub-001", "ses-20240601") in keys  # FS-only
    assert ("sub-002", "ses-20240101") in keys
    assert ("sub-003", "ses-20240101") in keys  # QSI-only


def test_discover_sessions_total_count(both_roots: tuple[Path, Path]) -> None:
    fs_root, qsi_root = both_roots
    result = discover_sessions(fs_root, qsi_root)
    assert len(result) == 4


def test_discover_sessions_fs_only_has_no_qsi(both_roots: tuple[Path, Path]) -> None:
    fs_root, qsi_root = both_roots
    result = discover_sessions(fs_root, qsi_root)
    fs_only = next(s for s in result if s.subject == "sub-001" and s.session == "ses-20240601")
    assert fs_only.freesurfer_dir is not None
    assert fs_only.qsirecon_dir is None


def test_discover_sessions_qsi_only_has_no_fs(both_roots: tuple[Path, Path]) -> None:
    fs_root, qsi_root = both_roots
    result = discover_sessions(fs_root, qsi_root)
    qsi_only = next(s for s in result if s.subject == "sub-003")
    assert qsi_only.freesurfer_dir is None
    assert qsi_only.qsirecon_dir is not None


def test_discover_sessions_overlap_has_both(both_roots: tuple[Path, Path]) -> None:
    fs_root, qsi_root = both_roots
    result = discover_sessions(fs_root, qsi_root)
    overlap = next(s for s in result if s.subject == "sub-001" and s.session == "ses-20240101")
    assert overlap.freesurfer_dir is not None
    assert overlap.qsirecon_dir is not None


def test_discover_sessions_sorted(both_roots: tuple[Path, Path]) -> None:
    fs_root, qsi_root = both_roots
    result = discover_sessions(fs_root, qsi_root)
    keys = [(s.subject, s.session) for s in result]
    assert keys == sorted(keys)


def test_discover_sessions_fs_only(both_roots: tuple[Path, Path]) -> None:
    fs_root, _ = both_roots
    result = discover_sessions(fs_root, None)
    assert len(result) == 3
    for s in result:
        assert s.qsirecon_dir is None


def test_discover_sessions_qsi_only(both_roots: tuple[Path, Path]) -> None:
    _, qsi_root = both_roots
    result = discover_sessions(None, qsi_root)
    assert len(result) == 3
    for s in result:
        assert s.freesurfer_dir is None


def test_discover_sessions_both_none(tmp_path: Path) -> None:
    result = discover_sessions(None, None)
    assert result == []


# ---------------------------------------------------------------------------
# discover_sessions — subject/session filtering
# ---------------------------------------------------------------------------


def test_discover_sessions_filter_subjects(both_roots: tuple[Path, Path]) -> None:
    fs_root, qsi_root = both_roots
    result = discover_sessions(fs_root, qsi_root, subjects=["sub-001"])
    assert all(s.subject == "sub-001" for s in result)
    assert len(result) == 2  # ses-20240101 and ses-20240601


def test_discover_sessions_filter_sessions(both_roots: tuple[Path, Path]) -> None:
    fs_root, qsi_root = both_roots
    result = discover_sessions(fs_root, qsi_root, sessions=["ses-20240601"])
    assert all(s.session == "ses-20240601" for s in result)
    assert len(result) == 1


def test_discover_sessions_filter_both(both_roots: tuple[Path, Path]) -> None:
    fs_root, qsi_root = both_roots
    result = discover_sessions(
        fs_root, qsi_root, subjects=["sub-001"], sessions=["ses-20240101"]
    )
    assert len(result) == 1
    assert result[0].subject == "sub-001"
    assert result[0].session == "ses-20240101"


def test_discover_sessions_filter_no_match(both_roots: tuple[Path, Path]) -> None:
    fs_root, qsi_root = both_roots
    result = discover_sessions(fs_root, qsi_root, subjects=["sub-999"])
    assert result == []


def test_discover_sessions_nonexistent_root(tmp_path: Path) -> None:
    """Non-existent roots are silently ignored."""
    result = discover_sessions(
        tmp_path / "nonexistent_fs",
        tmp_path / "nonexistent_qsi",
    )
    assert result == []


# ---------------------------------------------------------------------------
# SessionInfo dataclass
# ---------------------------------------------------------------------------


def test_session_info_defaults() -> None:
    info = SessionInfo(subject="sub-001", session="ses-20240101")
    assert info.freesurfer_dir is None
    assert info.qsirecon_dir is None


def test_session_info_with_paths(tmp_path: Path) -> None:
    info = SessionInfo(
        subject="sub-001",
        session="ses-20240101",
        freesurfer_dir=tmp_path / "fs",
        qsirecon_dir=tmp_path / "qsi",
    )
    assert info.freesurfer_dir == tmp_path / "fs"
    assert info.qsirecon_dir == tmp_path / "qsi"
