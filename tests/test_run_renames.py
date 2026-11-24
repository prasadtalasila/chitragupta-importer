"""Import runs that record citekey renames in renames.lock and the bibliography."""

import pytest
from run_fixture import NEWER, OLDER, OSTRANDER, SMITH, build, snapshot

from chitragupta_importer.renames import parse_renames_lock
from chitragupta_importer import run
from chitragupta_importer.run import ImportRefused, WriteFailed, import_zotero

# A frozen citekey longer than 30 characters, and the key the key rule gives its item.
LONG = "ostrander_calibrating_the_digital_twin_2024"
SHORT = "ostrander_calib_2024"


def existing(tmp_path, *keys):
    path = tmp_path / "existing" / "references.bib"
    path.parent.mkdir()
    path.write_text(
        "".join(
            f"@article{{{key},\n  title = {{Calibrating the digital twin}},\n}}\n" for key in keys
        ),
        encoding="utf-8",
    )
    return path


def read(out, name):
    return (out / name).read_text(encoding="utf-8")


def block(out):
    text = read(out, "bibliography.bib")
    start = text.index("@comment{cg-renames v1\n") + len("@comment{cg-renames v1\n")
    return parse_renames_lock(text[start : text.index("}\n", start)])


def test_bootstrap_dropped_key_gets_a_row(tmp_path):
    out = tmp_path / "out"
    bib = existing(tmp_path, "ostrander_calibrating_2024-1", "ostrander_calibrating_2024")
    summary = import_zotero(build(tmp_path, NEWER, OLDER), out, bib, merge_duplicates=True)
    row = "ostrander_calibrating_2024-1\tostrander_calibrating_2024\n"
    assert f"@comment{{cg-renames v1\n{row}}}\n" in read(out, "bibliography.bib")
    assert read(out, "renames.lock") == row
    assert summary.renames == (("ostrander_calibrating_2024-1", "ostrander_calibrating_2024"),)


def test_long_frozen_key_is_renamed_and_chain_collapses(tmp_path):
    out = tmp_path / "out"
    bib = existing(tmp_path, f"{LONG}-1", LONG)
    import_zotero(build(tmp_path, NEWER, OLDER), out, bib, merge_duplicates=True)
    lock = read(out, "citekeys.lock")
    assert f"zotero:user/AAAA1111\t{SHORT}\n" in lock
    assert f"renamed:{LONG}\t{LONG}\n" in lock
    assert block(out) == {f"{LONG}-1": SHORT, LONG: SHORT}
    assert (out / "files" / f"{SHORT}.pdf").exists()
    assert not (out / "files" / f"{LONG}.pdf").exists()


def test_zotero_merge_after_first_run_gets_a_row(tmp_path):
    out = tmp_path / "out"
    import_zotero(build(tmp_path / "v1", OSTRANDER, SMITH), out)
    uri = "http://zotero.org/users/local/abCD1234/items/BBBB2222"
    summary = import_zotero(build(tmp_path / "v2", {**OSTRANDER, "replaces": [uri]}), out)
    assert block(out) == {"smith_digital_2020": SHORT}
    assert summary.renames == (("smith_digital_2020", SHORT),)


def test_second_run_is_byte_identical_with_no_new_rows(tmp_path):
    out = tmp_path / "out"
    bib = existing(tmp_path, f"{LONG}-1", LONG)
    import_zotero(build(tmp_path / "v1", NEWER, OLDER), out, bib, merge_duplicates=True)
    before = snapshot(out)
    summary = import_zotero(build(tmp_path / "v2", NEWER, OLDER), out, merge_duplicates=True)
    assert snapshot(out) == before and summary.renames == ()


def test_no_renames_no_block_no_file(tmp_path):
    out = tmp_path / "out"
    import_zotero(build(tmp_path, OSTRANDER, SMITH), out)
    assert "cg-renames" not in read(out, "bibliography.bib")
    assert not (out / "renames.lock").exists()


def test_malformed_renames_lock_refuses(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    (out / "renames.lock").write_text("x y\n", encoding="utf-8")
    with pytest.raises(ImportRefused, match="renames.lock: malformed lock file"):
        import_zotero(build(tmp_path, OSTRANDER), out)


def test_renames_lock_is_written_before_the_citekey_lock(tmp_path, monkeypatch):
    out = tmp_path / "out"
    bib = existing(tmp_path, f"{LONG}-1", LONG)
    write = run.atomic_write

    def failing_write(path, text):
        if path.name == "citekeys.lock":
            raise OSError(28, "No space left on device", str(path))
        write(path, text)

    monkeypatch.setattr(run, "atomic_write", failing_write)
    with pytest.raises(WriteFailed):
        import_zotero(build(tmp_path, NEWER, OLDER), out, bib, merge_duplicates=True)
    assert parse_renames_lock(read(out, "renames.lock")) == {f"{LONG}-1": LONG, LONG: SHORT}
