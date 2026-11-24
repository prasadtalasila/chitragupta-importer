"""The `chitragupta-importer` command line."""

from pathlib import Path

import rich_click as click
from rich.console import Console
from rich.text import Text

from chitragupta_importer.bootstrap import BootstrapRefused
from chitragupta_importer.citekeys import UnsafeCitekey
from chitragupta_importer.config import load_config
from chitragupta_importer.console import print_error, print_summary
from chitragupta_importer.run import ImportRefused, WriteFailed, import_zotero
from chitragupta_importer.sources.zotero import UnknownSchema, UnreadableLibrary

REFUSALS = (
    UnknownSchema,
    UnreadableLibrary,
    UnsafeCitekey,
    BootstrapRefused,
    ImportRefused,
    WriteFailed,
)

EXAMPLES = Text.from_markup(
    """[b]Examples[/]

First import run, checked before anything is written:
  chitragupta-importer zotero --data-dir ~/Zotero --out papers \\
      --bootstrap old.bib --merge-duplicates --dry-run

The same first import run, for real:
  chitragupta-importer zotero --data-dir ~/Zotero --out papers \\
      --bootstrap old.bib --merge-duplicates

Every later import run (no --bootstrap; the locks hold the citekeys):
  chitragupta-importer zotero --data-dir ~/Zotero --out papers \\
      --merge-duplicates"""
)


@click.group(epilog=EXAMPLES)
@click.version_option(package_name="chitragupta-importer")
def main() -> None:
    """Import a reference manager's library into a papers/ directory for chitragupta."""


@main.command("zotero", epilog=EXAMPLES)
@click.option_panel("Locations", options=["--config", "--data-dir", "--out", "--bootstrap"])
@click.option_panel("Behaviour", options=["--merge-duplicates", "--dry-run"])
@click.option(
    "--config",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    is_eager=True,
    expose_value=False,
    callback=load_config,
    help="TOML file with data_dir and out, used when those options are left out;"
    " config.toml in the working directory by default.",
)
@click.option(
    "--data-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Zotero data directory, holding zotero.sqlite and storage/; only read. Zotero shows"
    " it under Zotero Settings → Advanced → Files and Folders.",
)
@click.option(
    "--out",
    required=True,
    type=click.Path(file_okay=False, path_type=Path),
    help="Papers directory to write; created if missing. Nothing is written outside it.",
)
@click.option(
    "--bootstrap",
    "bootstrap_from",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Existing bibliography whose citekeys to freeze in a new citekey lock;"
    " first import run only.",
)
@click.option(
    "--merge-duplicates",
    is_flag=True,
    help="Merge each duplicate group into one item instead of refusing the import run.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Print the summary a real import run would print, but write nothing.",
)
def zotero(
    data_dir: Path, out: Path, bootstrap_from: Path | None, merge_duplicates: bool, dry_run: bool
) -> None:
    """Import the personal Zotero library into a papers directory.

    Reads zotero.sqlite read-only, writes the bibliography, the locks and the
    main PDFs under --out, and prints a summary. A refused import run writes
    nothing and exits 1.
    """
    try:
        summary = import_zotero(
            data_dir, out, bootstrap_from, merge_duplicates=merge_duplicates, dry_run=dry_run
        )
    except REFUSALS as error:
        print_error(str(error), Console(stderr=True))
        raise SystemExit(1) from error
    print_summary(summary, Console())


if __name__ == "__main__":  # pragma: no cover
    main()
