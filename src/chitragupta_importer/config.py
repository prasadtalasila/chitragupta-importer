"""Locations read from a `config.toml` file, used when the command line leaves them out."""

import tomllib
from pathlib import Path

import click

DEFAULT_CONFIG = Path("config.toml")
KEYS = ("data_dir", "out")


def read_config(path: Path) -> dict[str, str]:
    """The `data_dir` and `out` settings of the config at `path`, as absolute paths.

    A relative path is taken from the config file's directory and `~` is
    expanded. Raises click.UsageError for a file that is not valid TOML, has
    a key other than `data_dir` and `out`, or has a value that is not a string.
    """
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise click.UsageError(f"{path}: cannot read the config ({error})") from error
    unknown = sorted(set(data) - set(KEYS))
    if unknown:
        raise click.UsageError(f"{path}: unknown key: {', '.join(unknown)} (expected {KEYS})")
    return {key: _absolute(path, key, value) for key, value in data.items()}


def _absolute(config: Path, key: str, value: object) -> str:
    """`value` as an absolute path string, relative paths taken from `config`'s directory."""
    if not isinstance(value, str):
        raise click.UsageError(f"{config}: {key} must be a string")
    return str((config.parent / Path(value).expanduser()).absolute())


def load_config(ctx: click.Context, _param: click.Parameter, value: Path | None) -> None:
    """Make the config's settings the defaults of the other options.

    Reads `value`, else `config.toml` in the working directory when there is one.
    """
    path = value or (DEFAULT_CONFIG if DEFAULT_CONFIG.is_file() else None)
    if path is not None:
        ctx.default_map = {**(ctx.default_map or {}), **read_config(path)}
