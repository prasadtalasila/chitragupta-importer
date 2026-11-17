"""The `chitragupta-importer` command line."""

from pathlib import Path

import click

from chitragupta_importer.bootstrap import BootstrapRefused
from chitragupta_importer.citekeys import UnsafeCitekey
from chitragupta_importer.run import ImportRefused, format_summary, import_zotero
from chitragupta_importer.sources.zotero import UnknownSchema


@click.group()
@click.version_option(package_name="chitragupta-importer")
def main() -> None:
    """Import a reference manager's library into a papers/ directory."""


@main.command("zotero")
@click.option(
    "--data-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Zotero data directory (holds zotero.sqlite and storage/); only read.",
)
@click.option(
    "--out",
    required=True,
    type=click.Path(file_okay=False, path_type=Path),
    help="Papers directory to write.",
)
@click.option(
    "--bootstrap",
    "bootstrap_from",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Existing bibliography whose citekeys to freeze in a new citekey lock.",
)
@click.option(
    "--merge-duplicates",
    is_flag=True,
    help="Merge each duplicate group into one item instead of refusing.",
)
@click.option("--dry-run", is_flag=True, help="Print the summary but write nothing.")
def zotero(
    data_dir: Path, out: Path, bootstrap_from: Path | None, merge_duplicates: bool, dry_run: bool
) -> None:
    """Import the personal Zotero library into a papers directory."""
    try:
        summary = import_zotero(data_dir, out, bootstrap_from, merge_duplicates, dry_run)
    except (UnknownSchema, UnsafeCitekey, BootstrapRefused, ImportRefused) as error:
        raise click.ClickException(str(error)) from error
    click.echo(format_summary(summary), nl=False)


if __name__ == "__main__":  # pragma: no cover
    main()
