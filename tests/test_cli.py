"""The console entry point: version, help and `python -m`."""

import subprocess
import sys
from importlib.metadata import version

from click.testing import CliRunner

from chitragupta_importer.__main__ import main


def test_version_matches_metadata():
    result = CliRunner().invoke(main, ["--version"])
    assert result.exit_code == 0
    assert version("chitragupta-importer") in result.output


def test_no_arguments_prints_help():
    result = CliRunner().invoke(main, [])
    assert "Usage:" in result.output


def test_module_entry_point():
    done = subprocess.run(
        [sys.executable, "-m", "chitragupta_importer", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert version("chitragupta-importer") in done.stdout
