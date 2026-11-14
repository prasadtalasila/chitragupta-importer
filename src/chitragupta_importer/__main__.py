"""The `chitragupta-importer` command line."""

import click


@click.group()
@click.version_option(package_name="chitragupta-importer")
def main() -> None:
    """Import a reference manager's library into a papers/ directory."""


if __name__ == "__main__":  # pragma: no cover
    main()
