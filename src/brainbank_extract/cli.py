"""CLI entry points for brainbank-extract."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click


@click.command("bb-extract")
@click.option(
    "--freesurfer-dir",
    type=click.Path(),
    default=None,
    help=(
        "Path to the FreeSurfer subject/session directory "
        "(flat layout: sub-XXX_ses-XXX/ containing surf/, label/, stats/)."
    ),
)
@click.option(
    "--qsirecon-dir",
    type=click.Path(),
    default=None,
    help=(
        "Path to the **root** QSIRecon derivatives directory "
        "(contains sub-*/ses-*/dwi/ and derivatives/qsirecon-*/). "
        "Do NOT point to a session-level directory."
    ),
)
@click.option(
    "--output-dir",
    required=True,
    type=click.Path(),
    help="Output directory for extracted files.",
)
@click.option(
    "--atlases",
    multiple=True,
    default=["schaefer400x7"],
    show_default=True,
    help="Atlas key(s) to extract. May be specified multiple times.",
)
@click.option(
    "--subject",
    required=True,
    help="BIDS subject identifier (e.g. sub-001).",
)
@click.option(
    "--session",
    required=True,
    help="BIDS session identifier (e.g. ses-20240101).",
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
    qsirecon_dir: str | None,
    output_dir: str,
    atlases: tuple[str, ...],
    subject: str,
    session: str,
    qsirecon_atlases_dir: str | None,
) -> None:
    """Extract neuroimaging features for a single subject/session.

    At least one of --freesurfer-dir or --qsirecon-dir must be provided.

    Example:

    \b
        bb-extract \\
          --freesurfer-dir /derivatives/freesurfer/sub-001_ses-20240101 \\
          --qsirecon-dir /derivatives/qsirecon \\
          --output-dir /derivatives/brainbank-extract/sub-001/ses-20240101 \\
          --atlases schaefer400x7 \\
          --atlases 4S156Parcels \\
          --subject sub-001 \\
          --session ses-20240101
    """
    if freesurfer_dir is None and qsirecon_dir is None:
        click.echo(
            "Error: at least one of --freesurfer-dir or --qsirecon-dir must be provided.",
            err=True,
        )
        sys.exit(1)

    out_path = Path(output_dir)
    atlas_list = list(atlases)
    combined_status: dict = {}

    # FreeSurfer extraction
    if freesurfer_dir is not None:
        from brainbank_extract.extractors.freesurfer import FreeSurferExtractor

        fs_extractor = FreeSurferExtractor(
            freesurfer_dir=Path(freesurfer_dir),
            output_dir=out_path,
            subject=subject,
            session=session,
            atlases=atlas_list,
        )
        click.echo(f"Extracting FreeSurfer features from: {freesurfer_dir}")
        fs_status = fs_extractor.extract()
        combined_status["freesurfer"] = fs_status
        anat_n = fs_status.get("modalities", {}).get("anat", {}).get("n_files", 0)
        click.echo(f"  anat: {anat_n} file(s) written")
        if fs_status.get("warnings"):
            for w in fs_status["warnings"]:
                click.echo(f"  WARNING: {w}", err=True)

    # QSIRecon extraction
    if qsirecon_dir is not None:
        from brainbank_extract.extractors.qsirecon import QSIReconExtractor

        qsi_extractor = QSIReconExtractor(
            qsirecon_dir=Path(qsirecon_dir),
            output_dir=out_path,
            subject=subject,
            session=session,
            atlases=atlas_list,
        )
        click.echo(f"Extracting QSIRecon features from: {qsirecon_dir}")
        qsi_status = qsi_extractor.extract()
        combined_status["qsirecon"] = qsi_status
        dwi_scalars_n = qsi_status.get("modalities", {}).get("dwi_scalars", {}).get("n_files", 0)
        dwi_conn_n = qsi_status.get("modalities", {}).get("dwi_connectivity", {}).get("n_files", 0)
        click.echo(f"  dwi scalars: {dwi_scalars_n} file(s) written")
        click.echo(f"  dwi connectivity: {dwi_conn_n} file(s) written")
        if qsi_status.get("warnings"):
            for w in qsi_status["warnings"]:
                click.echo(f"  WARNING: {w}", err=True)

    click.echo("Done.")


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
