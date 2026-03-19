"""CLI entry points for brainbank-extract."""

from __future__ import annotations

import sys
from pathlib import Path

import click


@click.command("bb-extract")
@click.option(
    "--freesurfer-dir",
    type=click.Path(),
    default=None,
    help=(
        "Path to a single FreeSurfer subject/session directory "
        "(flat layout: sub-XXX_ses-XXX/ containing surf/, label/, stats/). "
        "Use for single-session mode; requires --subject and --session."
    ),
)
@click.option(
    "--freesurfer-root",
    type=click.Path(),
    default=None,
    help=(
        "Root FreeSurfer derivatives directory containing flat session dirs "
        "(sub-XXX_ses-YYY/). Use for batch mode instead of --freesurfer-dir."
    ),
)
@click.option(
    "--qsirecon-dir",
    type=click.Path(),
    default=None,
    help=(
        "Path to the **root** QSIRecon derivatives directory "
        "(contains sub-*/ses-*/dwi/ and derivatives/qsirecon-*/). "
        "Used in both single-session and batch modes."
    ),
)
@click.option(
    "--output-dir",
    required=True,
    type=click.Path(),
    help=(
        "Output directory. In single-session mode: session output goes here directly. "
        "In batch mode: per-session outputs go to <output-dir>/sub-XXX/ses-YYY/."
    ),
)
@click.option(
    "--atlases",
    multiple=True,
    default=["schaefer400x7"],
    show_default=True,
    help=(
        "Atlas key(s) or suite name(s) to extract. May be specified multiple times. "
        "Suite names (core, extended, cortical, subcortical, full) are expanded "
        "to their constituent atlases."
    ),
)
@click.option(
    "--subject",
    default=None,
    help="BIDS subject identifier (e.g. sub-001). Required in single-session mode.",
)
@click.option(
    "--session",
    default=None,
    help="BIDS session identifier (e.g. ses-20240101). Required in single-session mode.",
)
@click.option(
    "--subjects",
    multiple=True,
    default=[],
    help=(
        "Batch mode: only process these subjects. "
        "May be specified multiple times. Default: all discovered subjects."
    ),
)
@click.option(
    "--sessions",
    multiple=True,
    default=[],
    help=(
        "Batch mode: only process these sessions. "
        "May be specified multiple times. Default: all discovered sessions."
    ),
)
@click.option(
    "--skip-existing",
    is_flag=True,
    default=False,
    help=(
        "Batch mode: skip any session whose output directory already exists "
        "(contains a _status.json file)."
    ),
)
@click.option(
    "--qsirecon-atlases-dir",
    type=click.Path(),
    default=None,
    help=(
        "Path to the QSIRecon atlases directory containing atlas-*/ subdirectories. "
        "Reserved for future subcortical volumetric extraction from Ext combined atlases."
    ),
)
@click.version_option(package_name="brainbank-extract")
def extract(
    freesurfer_dir: str | None,
    freesurfer_root: str | None,
    qsirecon_dir: str | None,
    output_dir: str,
    atlases: tuple[str, ...],
    subject: str | None,
    session: str | None,
    subjects: tuple[str, ...],
    sessions: tuple[str, ...],
    skip_existing: bool,
    qsirecon_atlases_dir: str | None,
) -> None:
    """Extract neuroimaging features from FreeSurfer and/or QSIRecon outputs.

    \b
    SINGLE-SESSION MODE (requires --subject and --session):
        bb-extract \\
          --freesurfer-dir /derivatives/freesurfer/sub-001_ses-20240101 \\
          --qsirecon-dir /derivatives/qsirecon \\
          --output-dir /derivatives/brainbank-extract/sub-001/ses-20240101 \\
          --atlases schaefer400x7 --atlases 4S156Parcels \\
          --subject sub-001 --session ses-20240101

    \b
    BATCH MODE (auto-discovers all sessions):
        bb-extract \\
          --freesurfer-root /derivatives/freesurfer \\
          --qsirecon-dir /derivatives/qsirecon \\
          --output-dir /derivatives/brainbank-extract \\
          --atlases extended \\
          --skip-existing
    """
    from brainbank_extract.atlases import resolve_atlases

    # Validate: at least one source must be provided
    if freesurfer_dir is None and freesurfer_root is None and qsirecon_dir is None:
        click.echo(
            "Error: at least one of --freesurfer-dir, --freesurfer-root, "
            "or --qsirecon-dir must be provided.",
            err=True,
        )
        sys.exit(1)

    # Expand atlas suites
    try:
        atlas_list = resolve_atlases(list(atlases))
    except ValueError as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    out_path = Path(output_dir)

    # -----------------------------------------------------------------
    # Mode detection
    # -----------------------------------------------------------------
    single_session_mode = subject is not None and session is not None

    if single_session_mode:
        if freesurfer_root is not None and freesurfer_dir is None:
            click.echo(
                "Error: --freesurfer-root is for batch mode. "
                "Use --freesurfer-dir with --subject/--session.",
                err=True,
            )
            sys.exit(1)
        _run_single_session(
            freesurfer_dir=Path(freesurfer_dir) if freesurfer_dir else None,
            qsirecon_dir=Path(qsirecon_dir) if qsirecon_dir else None,
            output_dir=out_path,
            atlas_list=atlas_list,
            subject=subject,
            session=session,
        )
    else:
        # Batch mode
        if subject is not None or session is not None:
            click.echo(
                "Error: provide both --subject and --session for single-session mode, "
                "or neither for batch mode.",
                err=True,
            )
            sys.exit(1)
        if freesurfer_dir is not None:
            click.echo(
                "Error: --freesurfer-dir is for single-session mode. "
                "Use --freesurfer-root for batch mode.",
                err=True,
            )
            sys.exit(1)
        _run_batch(
            freesurfer_root=Path(freesurfer_root) if freesurfer_root else None,
            qsirecon_dir=Path(qsirecon_dir) if qsirecon_dir else None,
            output_dir=out_path,
            atlas_list=atlas_list,
            subjects=list(subjects) or None,
            sessions=list(sessions) or None,
            skip_existing=skip_existing,
        )


def _run_single_session(
    freesurfer_dir: Path | None,
    qsirecon_dir: Path | None,
    output_dir: Path,
    atlas_list: list[str],
    subject: str,
    session: str,
) -> None:
    """Run extraction for one session and print a summary."""
    _extract_session(
        freesurfer_dir=freesurfer_dir,
        qsirecon_dir=qsirecon_dir,
        output_dir=output_dir,
        atlas_list=atlas_list,
        subject=subject,
        session=session,
        verbose=True,
    )
    click.echo("Done.")


def _run_batch(
    freesurfer_root: Path | None,
    qsirecon_dir: Path | None,
    output_dir: Path,
    atlas_list: list[str],
    subjects: list[str] | None,
    sessions: list[str] | None,
    skip_existing: bool,
) -> None:
    """Discover all sessions and run extraction for each."""
    from brainbank_extract.discovery import discover_sessions

    all_sessions = discover_sessions(
        freesurfer_root=freesurfer_root,
        qsirecon_root=qsirecon_dir,
        subjects=subjects,
        sessions=sessions,
    )

    if not all_sessions:
        click.echo("No sessions discovered. Check --freesurfer-root / --qsirecon-dir paths.")
        return

    click.echo(f"Discovered {len(all_sessions)} session(s).")

    n_ok = 0
    n_skipped = 0
    n_failed = 0

    for info in all_sessions:
        session_out = output_dir / info.subject / info.session
        label = f"{info.subject}/{info.session}"

        if skip_existing and (session_out / "_status.json").exists():
            click.echo(f"  skip  {label} (output exists)")
            n_skipped += 1
            continue

        click.echo(f"  run   {label}")
        try:
            _extract_session(
                freesurfer_dir=info.freesurfer_dir,
                qsirecon_dir=info.qsirecon_dir,
                output_dir=session_out,
                atlas_list=atlas_list,
                subject=info.subject,
                session=info.session,
                verbose=False,
            )
            n_ok += 1
        except Exception as exc:
            click.echo(f"        FAILED: {exc}", err=True)
            n_failed += 1

    click.echo(
        f"\nDone. {n_ok} succeeded, {n_skipped} skipped, {n_failed} failed."
    )


def _extract_session(
    freesurfer_dir: Path | None,
    qsirecon_dir: Path | None,
    output_dir: Path,
    atlas_list: list[str],
    subject: str,
    session: str,
    verbose: bool,
) -> None:
    """Run FreeSurfer and/or QSIRecon extraction for one session."""
    if freesurfer_dir is not None:
        from brainbank_extract.extractors.freesurfer import FreeSurferExtractor

        fs_extractor = FreeSurferExtractor(
            freesurfer_dir=freesurfer_dir,
            output_dir=output_dir,
            subject=subject,
            session=session,
            atlases=atlas_list,
        )
        if verbose:
            click.echo(f"Extracting FreeSurfer features from: {freesurfer_dir}")
        fs_status = fs_extractor.extract()
        if verbose:
            anat_n = fs_status.get("modalities", {}).get("anat", {}).get("n_files", 0)
            click.echo(f"  anat: {anat_n} file(s) written")
            for w in fs_status.get("warnings", []):
                click.echo(f"  WARNING: {w}", err=True)

    if qsirecon_dir is not None:
        from brainbank_extract.extractors.qsirecon import QSIReconExtractor

        qsi_extractor = QSIReconExtractor(
            qsirecon_dir=qsirecon_dir,
            output_dir=output_dir,
            subject=subject,
            session=session,
            atlases=atlas_list,
        )
        if verbose:
            click.echo(f"Extracting QSIRecon features from: {qsirecon_dir}")
        qsi_status = qsi_extractor.extract()
        if verbose:
            scalars_n = qsi_status.get("modalities", {}).get("dwi_scalars", {}).get("n_files", 0)
            conn_n = qsi_status.get("modalities", {}).get("dwi_connectivity", {}).get("n_files", 0)
            click.echo(f"  dwi scalars: {scalars_n} file(s) written")
            click.echo(f"  dwi connectivity: {conn_n} file(s) written")
            for w in qsi_status.get("warnings", []):
                click.echo(f"  WARNING: {w}", err=True)


@click.command("bb-aggregate")
@click.option(
    "--extract-dir",
    required=True,
    type=click.Path(),
    help="Root directory containing per-session brainbank-extract outputs.",
)
@click.option(
    "--output-dir",
    required=True,
    type=click.Path(),
    help="Output directory for aggregated files.",
)
@click.option(
    "--modalities",
    multiple=True,
    default=["anat", "dwi"],
    show_default=True,
    help="Modalities to aggregate: anat and/or dwi. May be specified multiple times.",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Re-aggregate all sessions even if previously processed.",
)
@click.version_option(package_name="brainbank-extract")
def aggregate(
    extract_dir: str,
    output_dir: str,
    modalities: tuple[str, ...],
    force: bool,
) -> None:
    """Aggregate per-session extractions into dataset-level consolidated files.

    Produces long-format parquet files for morphometrics and diffusion scalars,
    and stacked numpy arrays for connectivity matrices.

    Example:

    \b
        bb-aggregate \\
          --extract-dir /derivatives/brainbank-extract \\
          --output-dir /derivatives/brainbank-extract/aggregated \\
          --modalities anat \\
          --modalities dwi
    """
    click.echo("bb-aggregate: not yet implemented.")
    click.echo(f"  extract-dir:   {extract_dir}")
    click.echo(f"  output-dir:    {output_dir}")
    click.echo(f"  modalities:    {', '.join(modalities)}")
    click.echo(f"  force:         {force}")
    sys.exit(0)
