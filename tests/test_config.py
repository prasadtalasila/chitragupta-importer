"""Locations read from config.toml instead of --data-dir and --out."""

import pytest
from click.testing import CliRunner
from run_fixture import row
from test_cli import zotero_data_dir

from chitragupta_importer.__main__ import main

KEY_FILE = "ostrander_calibrating_2024.pdf"


def write_config(directory, text):
    path = directory / "config.toml"
    path.write_text(text)
    return path


def test_config_option_supplies_both_locations(tmp_path):
    data_dir = zotero_data_dir(tmp_path)
    config = write_config(tmp_path, f'data_dir = "{data_dir}"\nout = "{tmp_path / "out"}"\n')
    result = CliRunner().invoke(main, ["zotero", "--config", str(config)])
    assert result.exit_code == 0, result.output
    assert row(result.stdout, "included", 1)
    assert (tmp_path / "out" / "files" / KEY_FILE).is_file()


def test_config_toml_in_working_directory_is_read_by_default(tmp_path, monkeypatch):
    data_dir = zotero_data_dir(tmp_path)
    write_config(tmp_path, f'data_dir = "{data_dir}"\nout = "papers"\n')
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(main, ["zotero"])
    assert result.exit_code == 0, result.output
    assert (tmp_path / "papers" / "files" / KEY_FILE).is_file()


def test_option_on_the_command_line_beats_the_config(tmp_path):
    data_dir = zotero_data_dir(tmp_path)
    config = write_config(tmp_path, f'data_dir = "{data_dir}"\nout = "from-config"\n')
    out = tmp_path / "from-flag"
    result = CliRunner().invoke(main, ["zotero", "--config", str(config), "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert (out / "files" / KEY_FILE).is_file()
    assert not (tmp_path / "from-config").exists()


def test_relative_paths_are_taken_from_the_config_files_directory(tmp_path, monkeypatch):
    settings = tmp_path / "settings"
    settings.mkdir()
    data_dir = zotero_data_dir(settings)
    config = write_config(settings, f'data_dir = "{data_dir.name}"\nout = "papers"\n')
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(main, ["zotero", "--config", str(config)])
    assert result.exit_code == 0, result.output
    assert (settings / "papers" / "files" / KEY_FILE).is_file()


def test_tilde_is_expanded_to_the_home_directory(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    data_dir = zotero_data_dir(home)
    monkeypatch.setenv("HOME", str(home))
    config = write_config(tmp_path, f'data_dir = "~/{data_dir.name}"\nout = "~/papers"\n')
    result = CliRunner().invoke(main, ["zotero", "--config", str(config)])
    assert result.exit_code == 0, result.output
    assert (home / "papers" / "files" / KEY_FILE).is_file()


def test_missing_location_is_still_a_usage_error(tmp_path):
    config = write_config(tmp_path, 'out = "papers"\n')
    result = CliRunner().invoke(main, ["zotero", "--config", str(config)])
    assert result.exit_code == 2
    assert "--data-dir" in result.output


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("data_dir = [\n", "cannot read the config"),
        ('outt = "x"\n', "unknown key: outt"),
        ("out = 3\n", "out must be a string"),
    ],
)
def test_bad_config_is_a_usage_error_naming_the_file(tmp_path, text, message):
    config = write_config(tmp_path, text)
    result = CliRunner().invoke(main, ["zotero", "--config", str(config)])
    assert result.exit_code == 2
    assert message in " ".join(result.output.split())
    assert "config.toml" in result.output


def test_config_file_that_does_not_exist_is_a_usage_error(tmp_path):
    result = CliRunner().invoke(main, ["zotero", "--config", str(tmp_path / "none.toml")])
    assert result.exit_code == 2
