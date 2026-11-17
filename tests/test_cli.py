"""The console entry point: version, help and `python -m`."""

import subprocess
import sys
from importlib.metadata import version

from click.testing import CliRunner
from zotero_fixture import ZoteroFixture

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


def zotero_data_dir(tmp_path, schema_version=121):
    fixture = ZoteroFixture(tmp_path)
    fixture.add_item(
        "AAAA1111",
        fields={"title": "Characterizing the Digital Twin", "date": "2024"},
        creators=[("Richstein", "Rebecca", "author")],
        pdfs=[("paper.pdf", b"%PDF-1")],
    )
    return fixture.build(schema_version)


def test_zotero_command_prints_summary(tmp_path):
    out = tmp_path / "out"
    data_dir = zotero_data_dir(tmp_path)
    result = CliRunner().invoke(main, ["zotero", "--data-dir", str(data_dir), "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert result.stdout == "included: 1\nnew citekeys: 1\nunreferenced files: 0\n"
    assert (out / "files" / "richstein_characterizing_2024.pdf").is_file()


def test_zotero_command_bootstrap_option(tmp_path):
    existing = tmp_path / "references.bib"
    existing.write_text("@article{rr,\n  title = {Characterizing the digital twin},\n}\n")
    args = ["zotero", "--data-dir", str(zotero_data_dir(tmp_path)), "--out", str(tmp_path / "o")]
    result = CliRunner().invoke(main, [*args, "--bootstrap", str(existing)])
    assert result.exit_code == 0, result.output
    assert (
        "bootstrap: matched 1, unmatched 0, ambiguous 0, not included 0, dropped 0\n"
        in result.stdout
    )


def test_zotero_command_refusal_exits_nonzero(tmp_path):
    out = tmp_path / "out"
    data_dir = zotero_data_dir(tmp_path, schema_version=999)
    result = CliRunner().invoke(main, ["zotero", "--data-dir", str(data_dir), "--out", str(out)])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "Error:" in result.stderr and "999" in result.stderr
    assert not out.exists()
