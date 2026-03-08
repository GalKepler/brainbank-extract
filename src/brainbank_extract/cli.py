"""CLI entry points for brainbank-extract."""

from __future__ import annotations

import sys

import click


@click.command("bb-extract")
@click.option(
    "--freesurfer-dir",
    type=click.Path(),
    default=None,
    help="Path to the FreeSurfer subject/session directory.",
)
@click.option(
    "--qsirecon-dir",
    type=click.Path(),
    default=None,
    help="Path to the QSIRecon subject/session directory.",
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
@click.version_option(package_name="brainbank-extract")
def extract(
    freesurfer_dir: str | None,
    qsirecon_dir: str | None,
    output_dir: str,
    atlases: tuple[str, ...],
    subject: str,
    session: str,
) -> None:
    """Extract neuroimaging features for a single subject/session.

    At least one of --freesurfer-dir or --qsirecon-dir must be provided.

    Example:

    \b
        bb-extract \\
          --freesurfer-dir /derivatives/freesurfer/sub-001/ses-20240101 \\
          --qsirecon-dir /derivatives/qsirecon/sub-001/ses-20240101 \\
          --output-dir /derivatives/brainbank-extract/sub-001/ses-20240101 \\
          --atlases schaefer400x7 \\
          --atlases tian_s2 \\
          --subject sub-001 \\
          --session ses-20240101
    """
    if freesurfer_dir is None and qsirecon_dir is None:
        click.echo(
            "Error: at least one of --freesurfer-dir or --qsirecon-dir must be provided.",
            err=True,
        )
        sys.exit(1)

    click.echo("bb-extract: not yet implemented.")
    click.echo(f"  subject:       {subject}")
    click.echo(f"  session:       {session}")
    click.echo(f"  freesurfer:    {freesurfer_dir}")
    click.echo(f"  qsirecon:      {qsirecon_dir}")
    click.echo(f"  output:        {output_dir}")
    click.echo(f"  atlases:       {', '.join(atlases)}")
    sys.exit(0)


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
