"""Bootstrap: an ordinary item claimed by several entries freezes one citekey."""

import pytest

from chitragupta_importer.bootstrap import BootstrapRefused, bootstrap
from chitragupta_importer.inputs import seed_lock
from chitragupta_importer.model import Attachment, Creator, Item, Library

PDF = b"%PDF-1.4 twins\n"
ITEM_ID = "zotero:user/TWIN0001"


def twins_library(tmp_path, date="2024"):
    """One item, stem `smith_twins_<year>`, with the DOI 10.9999/twins and one PDF."""
    path = tmp_path / "storage" / "TWIN0001" / "main.pdf"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(PDF)
    item = Item(
        item_id=ITEM_ID,
        item_type="journalArticle",
        fields={"title": "Twins of the Tide", "date": date, "DOI": "10.9999/twins"},
        creators=(Creator("Smith", "Jo", False, "author"),),
        attachments=(Attachment("application/pdf", path, "main.pdf"),),
        collection_ids=(),
        tags=(),
        date_added="2020-01-01 00:00:00",
    )
    return Library(items=(item,), collections=(), skipped_libraries=())


def existing_bib(tmp_path, *entries):
    """Each entry is `(citekey, extra fields)`; every entry carries the item's DOI."""
    path = tmp_path / "existing" / "references.bib"
    path.parent.mkdir(parents=True, exist_ok=True)
    (path.parent / "twins.pdf").write_bytes(PDF)
    path.write_text(
        "".join(
            f"@article{{{citekey},\n  doi = {{10.9999/twins}},\n"
            + "".join(f"  {name} = {{{value}}},\n" for name, value in fields.items())
            + "}\n"
            for citekey, fields in entries
        ),
        encoding="utf-8",
    )
    return path


def test_two_entries_for_ordinary_item_stem_frozen(tmp_path):
    bib = existing_bib(tmp_path, ("smith_twins_2024-1", {}), ("smith_twins_2024", {}))
    result = bootstrap(bib, twins_library(tmp_path))
    assert result.lock == {ITEM_ID: "smith_twins_2024"}
    assert result.dropped == ("smith_twins_2024-1",)


def test_dropped_citekey_retired_in_lock(tmp_path):
    bib = existing_bib(tmp_path, ("smith_twins_2024", {}), ("smith_twins_2024-1", {}))
    lock, result = seed_lock(tmp_path / "citekeys.lock", twins_library(tmp_path), bib, {})
    assert result.dropped == ("smith_twins_2024-1",)
    assert lock == {ITEM_ID: "smith_twins_2024", "dropped:smith_twins_2024-1": "smith_twins_2024-1"}


def test_three_entries_stem_frozen(tmp_path):
    citekeys = ("smith_twins_nodate-1", "smith_twins_2024", "smith_twins_nodate")
    bib = existing_bib(tmp_path, *((citekey, {}) for citekey in citekeys))
    result = bootstrap(bib, twins_library(tmp_path))
    assert result.lock == {ITEM_ID: "smith_twins_2024"}
    assert result.dropped == ("smith_twins_nodate", "smith_twins_nodate-1")


def test_unsuffixed_frozen_when_no_entry_has_the_stem(tmp_path):
    citekeys = ("smith_twins_nodate-1", "smith_twins_nodate")
    bib = existing_bib(tmp_path, *((citekey, {}) for citekey in citekeys))
    result = bootstrap(bib, twins_library(tmp_path))
    assert result.lock == {ITEM_ID: "smith_twins_nodate"}
    assert result.dropped == ("smith_twins_nodate-1",)


def test_entry_with_the_items_pdf_wins_over_stem(tmp_path):
    with_pdf = {"file": "Full Text:twins.pdf:application/pdf"}
    bib = existing_bib(tmp_path, ("smith_twins_2024", {}), ("smith_twins_2024-1", with_pdf))
    result = bootstrap(bib, twins_library(tmp_path))
    assert result.lock == {ITEM_ID: "smith_twins_2024-1"}
    assert result.dropped == ("smith_twins_2024",)


def test_duplicate_citekey_in_bibliography_still_refused(tmp_path):
    bib = existing_bib(tmp_path, ("smith_twins_2024", {}), ("smith_twins_2024", {}))
    with pytest.raises(BootstrapRefused, match="duplicate citekey smith_twins_2024"):
        bootstrap(bib, twins_library(tmp_path))
