"""Import runs with and without --merge-duplicates, and with --dry-run."""

import shutil
from dataclasses import replace

import pytest
from run_fixture import NEWER, OLDER, OSTRANDER, SMITH, build, existing_bibliography, snapshot

from chitragupta_importer.run import DuplicatesFound, ImportRefused, format_summary, import_zotero

PLATFORMS = {
    **SMITH,
    "key": "CCCC3333",
    "fields": {"title": "Digital Platforms", "date": "2020", "DOI": "10.9999/platforms"},
}
PLATFORMS_COPY = {
    **PLATFORMS,
    "key": "DDDD4444",
    "fields": {"title": "Digital platforms", "date": "2020", "DOI": "10.9999/platforms"},
    "pdfs": [],
}
URL = "https://example.org/twins"
TWINS_PAPER = {**OSTRANDER, "fields": {"title": "Twins, part one", "date": "2024", "url": URL}}
TWINS_REPORT = {
    **SMITH,
    "item_type": "report",
    "fields": {"title": "Twins deliverable", "date": "2024", "url": URL},
}


def twins_bib(tmp_path):
    path = tmp_path / "existing" / "references.bib"
    path.parent.mkdir()
    path.write_text(f"@article{{tw,\n  title = {{Twins}},\n  url = {{{URL}}},\n}}\n")
    return path


def test_duplicates_without_flag_refuse_and_list(tmp_path):
    out = tmp_path / "out"
    import_zotero(build(tmp_path / "v1", OSTRANDER), out)
    before = snapshot(out)
    data_dir = build(tmp_path / "v2", NEWER, OLDER, PLATFORMS, PLATFORMS_COPY)
    with pytest.raises(DuplicatesFound) as refused:
        import_zotero(data_dir, out)
    assert isinstance(refused.value, ImportRefused)
    assert str(refused.value) == (
        "2 duplicate groups found; rerun with --merge-duplicates to merge them\n"
        "duplicate group: zotero:user/AAAA1111 (Calibrating the Digital Twin), "
        "zotero:user/BBBB2222 (Calibrating the digital twin)\n"
        "duplicate group: zotero:user/CCCC3333 (Digital Platforms), "
        "zotero:user/DDDD4444 (Digital platforms)"
    )
    assert snapshot(out) == before


def test_url_tie_groups_listed_without_flag_when_bootstrapping(tmp_path):
    data_dir, bib = build(tmp_path, TWINS_PAPER, TWINS_REPORT), twins_bib(tmp_path)
    with pytest.raises(DuplicatesFound, match="duplicate group: zotero:user/AAAA1111 "):
        import_zotero(data_dir, tmp_path / "out", bootstrap_from=bib)
    assert not (tmp_path / "out").exists()
    summary = import_zotero(data_dir, tmp_path / "out", bib, merge_duplicates=True)
    assert summary.duplicates == {"zotero:user/BBBB2222": "zotero:user/AAAA1111"}
    assert summary.bootstrap.lock == {"zotero:user/AAAA1111": "tw"}


def test_url_tie_groups_need_bootstrapping(tmp_path):
    summary = import_zotero(build(tmp_path, TWINS_PAPER, TWINS_REPORT), tmp_path / "out")
    assert summary.included == 2 and summary.duplicates == {}


def test_merge_flag_merges(tmp_path):
    out = tmp_path / "out"
    doi = "10.9999/twin"
    with_pdf = {**NEWER, "fields": {**NEWER["fields"], "DOI": doi}}
    without_pdf = {**OLDER, "fields": {**OLDER["fields"], "DOI": doi}, "pdfs": []}
    summary = import_zotero(build(tmp_path, with_pdf, without_pdf), out, merge_duplicates=True)
    assert summary.duplicates == {"zotero:user/AAAA1111": "zotero:user/BBBB2222"}
    assert (out / "citekeys.lock").read_text(encoding="utf-8") == (
        "zotero:user/BBBB2222\tostrander_calibrating_2024\n"
    )


def test_no_duplicates_flag_irrelevant(tmp_path):
    data_dir = build(tmp_path, OSTRANDER, SMITH)
    plain = import_zotero(data_dir, tmp_path / "plain")
    flagged = import_zotero(data_dir, tmp_path / "flagged", merge_duplicates=True)
    assert plain == flagged
    assert snapshot(tmp_path / "plain") == snapshot(tmp_path / "flagged")


def test_dry_run_writes_nothing(tmp_path):
    out, real = tmp_path / "out", tmp_path / "real"
    import_zotero(build(tmp_path / "v1", OSTRANDER), out)
    (out / "files" / "stray.pdf").write_bytes(b"%PDF-9")
    shutil.copytree(out, real)
    before = snapshot(out)
    data_dir = build(tmp_path / "v2", OSTRANDER, SMITH)
    summary = import_zotero(data_dir, out, dry_run=True)
    assert snapshot(out) == before
    expected = import_zotero(data_dir, real)
    assert summary.dry_run and not expected.dry_run
    assert replace(summary, dry_run=False) == expected
    assert format_summary(summary) == "dry run: nothing written\n" + format_summary(expected)


def test_dry_run_creates_nothing(tmp_path):
    out, data_dir = tmp_path / "out", build(tmp_path, OSTRANDER)
    before = sorted(tmp_path.rglob("*"))
    bib = existing_bibliography(tmp_path)
    summary = import_zotero(data_dir, out, bootstrap_from=bib, dry_run=True)
    assert not out.exists()
    assert sorted(tmp_path.rglob("*")) == sorted([*before, bib.parent, bib])
    assert summary.included == 1
    assert summary.bootstrap.lock == {"zotero:user/AAAA1111": "io2024"}


def test_dry_run_without_flag_still_lists_and_fails(tmp_path):
    with pytest.raises(DuplicatesFound, match="^1 duplicate groups found"):
        import_zotero(build(tmp_path, NEWER, OLDER), tmp_path / "out", dry_run=True)
    assert not (tmp_path / "out").exists()


def test_dry_run_still_refuses_bootstrap_with_existing_lock(tmp_path):
    out, data_dir = tmp_path / "out", build(tmp_path, OSTRANDER)
    import_zotero(data_dir, out)
    with pytest.raises(ImportRefused, match="citekeys.lock"):
        import_zotero(data_dir, out, existing_bibliography(tmp_path), dry_run=True)


def test_flags_are_keyword_only(tmp_path):
    data_dir, out = build(tmp_path, OSTRANDER), tmp_path / "out"
    with pytest.raises(TypeError):
        import_zotero(data_dir, out, None, True)  # pylint: disable=too-many-function-args
    assert not out.exists()
