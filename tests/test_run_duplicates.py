"""Import runs with --merge-duplicates: duplicate items merged before anything else."""

import pytest
from run_fixture import NEWER, OLDER, build, snapshot

from chitragupta_importer.run import ImportRefused, format_summary, import_zotero

DUPLICATE_LINE = "duplicate zotero:user/BBBB2222 of zotero:user/AAAA1111\n"


def existing_with_two_keys(tmp_path):
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


def test_duplicates_merged_before_import(tmp_path):
    out = tmp_path / "out"
    summary = import_zotero(build(tmp_path, NEWER, OLDER), out, merge_duplicates=True)
    assert summary.included == 1
    assert summary.duplicates == {"zotero:user/BBBB2222": "zotero:user/AAAA1111"}
    assert (out / "citekeys.lock").read_text(encoding="utf-8") == (
        "zotero:user/AAAA1111\tostrander_calibrating_2024\n"
    )
    assert (out / "bibliography.bib").read_text(encoding="utf-8").count("@article{") == 1
    assert format_summary(summary) == (
        f"included: 1\n{DUPLICATE_LINE}new citekeys: 1\nnew tide-pools\nunreferenced files: 0\n"
    )


def test_bootstrap_with_duplicates_freezes_one_key(tmp_path):
    out = tmp_path / "out"
    data_dir = build(tmp_path, NEWER, OLDER)
    summary = import_zotero(data_dir, out, existing_with_two_keys(tmp_path), merge_duplicates=True)
    assert summary.bootstrap.dropped == ("ostrander_calibrating_2024-1",)
    assert (out / "citekeys.lock").read_text(encoding="utf-8") == (
        "zotero:user/AAAA1111\tostrander_calibrating_2024\n"
    )
    assert format_summary(summary).endswith(
        "bootstrap: matched 1, unmatched 0, ambiguous 0, not included 0, dropped 1\n"
        "dropped citekey: ostrander_calibrating_2024-1\n"
    )


def test_later_zotero_merge_keeps_key(tmp_path):
    out = tmp_path / "out"
    import_zotero(build(tmp_path / "v1", NEWER, OLDER), out, merge_duplicates=True)
    lock = (out / "citekeys.lock").read_text(encoding="utf-8")
    merged_in_zotero = {**OLDER, "pdfs": [*OLDER["pdfs"], *NEWER["pdfs"]]}
    summary = import_zotero(build(tmp_path / "v2", merged_in_zotero), out)
    assert (out / "citekeys.lock").read_text(encoding="utf-8") == lock
    assert summary.new_citekeys == summary.collection_changes == ()
    assert summary.duplicates == {}
    assert not summary.unreferenced


def test_rerun_with_duplicates_is_byte_identical(tmp_path):
    data_dir, out = build(tmp_path, NEWER, OLDER), tmp_path / "out"
    import_zotero(data_dir, out, merge_duplicates=True)
    first = snapshot(out)
    summary = import_zotero(data_dir, out, merge_duplicates=True)
    assert snapshot(out) == first
    assert summary.duplicates == {"zotero:user/BBBB2222": "zotero:user/AAAA1111"}


def test_unreadable_pdf_while_merging_names_the_pdf(tmp_path, monkeypatch):
    data_dir, out = build(tmp_path, NEWER, OLDER), tmp_path / "out"
    pdf = next((data_dir / "storage").rglob("paper.pdf"))

    def refuse(path):
        raise PermissionError(13, "Permission denied", str(path))

    monkeypatch.setattr("chitragupta_importer.normalise.hash_file", refuse)
    with pytest.raises(ImportRefused, match="while merging duplicate items") as refused:
        import_zotero(data_dir, out, merge_duplicates=True)
    assert str(pdf) in str(refused.value)
    assert not out.exists()


def test_oserror_without_filename_while_merging_shows_the_error(tmp_path, monkeypatch):
    def fail(path):
        raise OSError(f"device gone while reading {path.name}")

    monkeypatch.setattr("chitragupta_importer.normalise.hash_file", fail)
    with pytest.raises(
        ImportRefused, match="while merging duplicate items: device gone"
    ) as refused:
        import_zotero(build(tmp_path, NEWER, OLDER), tmp_path / "out", merge_duplicates=True)
    assert "None" not in str(refused.value)
    assert not (tmp_path / "out").exists()
