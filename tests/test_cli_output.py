"""The command line's help, its rich summary and its refusals, as plain text off a terminal."""

import pytest
from click.testing import CliRunner
from run_fixture import NEWER, OLDER, SMITH, build, row
from zotero_fixture import ZoteroFixture

from chitragupta_importer.__main__ import main

ANSI = "\x1b["


@pytest.fixture(autouse=True)
def _no_forced_colour(monkeypatch):
    for name in ("FORCE_COLOR", "TTY_COMPATIBLE", "TTY_INTERACTIVE"):
        monkeypatch.delenv(name, raising=False)


def test_group_help_shows_examples():
    result = CliRunner().invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "Examples" in result.output and "--bootstrap" in result.output
    assert ANSI not in result.output


def test_zotero_help_shows_examples_and_option_groups():
    result = CliRunner().invoke(main, ["zotero", "--help"])
    assert result.exit_code == 0
    output = result.output
    assert ANSI not in output
    assert "Examples" in output
    assert "--merge-duplicates --dry-run" in output
    assert "Settings → Advanced → Files and Folders" in output
    locations, behaviour = output.index("Locations"), output.index("Behaviour")
    for option in ("--data-dir", "--out", "--bootstrap"):
        assert locations < output.index(option, locations) < behaviour
    for option in ("--merge-duplicates", "--dry-run"):
        assert behaviour < output.index(option, behaviour) < output.index("Examples")


def existing_two_keys(tmp_path):
    path = tmp_path / "existing" / "references.bib"
    path.parent.mkdir()
    path.write_text(
        "".join(
            f"@article{{{key},\n  title = {{Calibrating the digital twin}},\n}}\n"
            for key in ("ostrander_calibrating_2024-1", "ostrander_calibrating_2024")
        ),
        encoding="utf-8",
    )
    return path


def test_summary_table(tmp_path):
    data_dir = build(tmp_path, NEWER, OLDER, {**SMITH, "key": "DDDD4444"}, {"key": "CCCC3333"})
    args = ["zotero", "--data-dir", str(data_dir), "--out", str(tmp_path / "out")]
    result = CliRunner().invoke(
        main, [*args, "--bootstrap", str(existing_two_keys(tmp_path)), "--merge-duplicates"]
    )
    assert result.exit_code == 0, result.output
    output = result.stdout
    assert ANSI not in output and result.stderr == ""
    assert row(output, "included", 2)
    assert row(output, "left out (no attachment)", 1)
    assert row(output, "new citekeys", 1)
    assert row(output, "duplicates", 1)
    assert row(output, "dropped citekeys", 1)
    assert row(output, "citekey renames", 1)
    assert row(output, "unreferenced files", 0)
    lines = output.splitlines()
    assert "new tide-pools" in lines
    assert "duplicate zotero:user/BBBB2222 of zotero:user/AAAA1111" in lines
    assert "dropped citekey: ostrander_calibrating_2024-1" in lines
    assert "renamed citekey: ostrander_calibrating_2024-1 -> ostrander_calibrating_2024" in lines


def test_dry_run_and_skipped_library_lines(tmp_path):
    fixture = ZoteroFixture(tmp_path)
    fixture.add_group_library(7, "Shared")
    data_dir = fixture.build()
    args = ["zotero", "--data-dir", str(data_dir), "--out", str(tmp_path / "out"), "--dry-run"]
    result = CliRunner().invoke(main, args)
    assert result.exit_code == 0, result.output
    lines = result.stdout.splitlines()
    assert lines[0] == "dry run: nothing written"
    assert "skipped library: zotero:group-7" in lines


def test_refusal_lists_one_problem_per_line(tmp_path):
    existing = tmp_path / "references.bib"
    existing.write_text(
        "".join(
            f"@article{{{key},\n  title = {{Digital platforms}},\n}}\n"
            for key in ("io", "io", "a:b")
        ),
        encoding="utf-8",
    )
    args = ["zotero", "--data-dir", str(build(tmp_path, SMITH)), "--out", str(tmp_path / "out")]
    result = CliRunner().invoke(main, [*args, "--bootstrap", str(existing)])
    assert result.exit_code == 1 and result.stdout == ""
    assert ANSI not in result.stderr and "Traceback" not in result.stderr
    lines = result.stderr.splitlines()
    assert lines[0] == "Error: bootstrap refused:"
    assert lines[1].strip() == "duplicate citekey io in existing bibliography"
    assert lines[2].strip() == "unsafe citekey 'a:b': citekey contains ':'"
    assert len(lines) == 3


def test_duplicate_groups_refusal_one_group_per_line(tmp_path):
    data_dir = build(tmp_path, NEWER, OLDER)
    result = CliRunner().invoke(
        main, ["zotero", "--data-dir", str(data_dir), "--out", str(tmp_path)]
    )
    assert result.exit_code == 1
    lines = result.stderr.splitlines()
    assert lines[0].startswith("Error: 1 duplicate groups found")
    assert lines[1].strip().startswith("duplicate group: zotero:user/AAAA1111 (")
