"""Grouping by URL and extra groups, the survivor with a PDF, and the merged attachments."""

from chitragupta_importer.duplicates import (
    duplicate_groups,
    merge_duplicates,
    oldest_added,
    pdf_then_oldest,
)
from chitragupta_importer.model import Attachment, Item, Library
from chitragupta_importer.pdfs import main_pdf

URL = "https://example.org/smith-twins"


def item(key, title="Smith Twins", item_type="journalArticle", **changes):
    values = {
        "item_id": f"zotero:user/{key}",
        "item_type": item_type,
        "fields": {"title": title, "url": URL},
        "creators": (),
        "attachments": (),
        "collection_ids": (),
        "tags": (),
        "date_added": "2020-01-01 00:00:00",
    }
    values.update(changes)
    return Item(**values)


def pdf(directory, name, content=b"%PDF-1.4 smith twins\n"):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(content)
    return Attachment("application/pdf", path, name)


def library(*items):
    return Library(items=items, collections=(), skipped_libraries=())


def test_same_type_title_and_url_merged():
    lib = library(
        item("AAAA"),
        item("BBBB", title="smith twins!"),
        item("CCCC", title="Other Twins"),
        item("DDDD", item_type="book"),
        item("EEEE", fields={"title": "Smith Twins", "url": URL + "/"}),
    )
    merged, duplicates = merge_duplicates(lib, oldest_added)
    assert duplicates == {"zotero:user/BBBB": "zotero:user/AAAA"}
    assert len(merged.items) == 4


def test_extra_group_merges_different_types_and_titles():
    lib = library(
        item("AAAA", fields={"title": "Twins, part one"}),
        item("BBBB", item_type="report", fields={"title": "Twins deliverable"}),
        item("CCCC", fields={"title": "Unrelated"}),
    )
    extra = [{"zotero:user/BBBB", "zotero:user/AAAA"}]
    assert not merge_duplicates(lib, oldest_added)[1]
    _, duplicates = merge_duplicates(lib, oldest_added, extra)
    assert duplicates == {"zotero:user/BBBB": "zotero:user/AAAA"}


def test_survivor_is_copy_with_pdf(tmp_path):
    older = item("AAAA", date_added="2019-01-01 00:00:00")
    missing = Attachment("application/pdf", tmp_path / "gone.pdf", "gone.pdf")
    older_missing = item("BBBB", attachments=(missing,), date_added="2019-06-01 00:00:00")
    newer = item("CCCC", attachments=(pdf(tmp_path / "c", "c.pdf"),))
    _, duplicates = merge_duplicates(library(older, older_missing, newer), pdf_then_oldest)
    assert set(duplicates.values()) == {"zotero:user/CCCC"}


def test_pdf_then_oldest_among_copies_with_pdf(tmp_path):
    no_pdf = item("AAAA", date_added="2018-01-01 00:00:00")
    newer = item("BBBB", attachments=(pdf(tmp_path, "b.pdf"),), date_added="2022-01-01 00:00:00")
    tie_d = item("DDDD", attachments=(pdf(tmp_path, "d.pdf"),), date_added="2021-01-01 00:00:00")
    tie_c = item("CCCC", attachments=(pdf(tmp_path, "c.pdf"),), date_added="2021-01-01 00:00:00")
    assert pdf_then_oldest([no_pdf, newer, tie_d, tie_c]) is tie_c
    assert pdf_then_oldest([newer, no_pdf, item("EEEE")]) is newer
    assert pdf_then_oldest([item("FFFF"), no_pdf]) is no_pdf


def test_merged_keeps_only_survivor_attachments_when_it_has_pdf(tmp_path):
    note = Attachment("text/plain", None, "notes.txt")
    own = pdf(tmp_path / "a", "a.pdf", b"%PDF own")
    survivor = item("AAAA", attachments=(note, own), date_added="2019-01-01 00:00:00")
    member = item("BBBB", attachments=(pdf(tmp_path / "b", "0.pdf", b"%PDF other"),))
    merged, _ = merge_duplicates(library(member, survivor), pdf_then_oldest)
    (result,) = merged.items
    assert result.attachments == (note, own)
    assert main_pdf(result) == own.path


def test_merged_takes_member_attachments_when_survivor_has_no_pdf(tmp_path):
    note = Attachment("text/plain", None, "notes.txt")
    survivor = item("AAAA", attachments=(note,), date_added="2019-01-01 00:00:00")
    member_pdf = pdf(tmp_path / "b", "b.pdf")
    merged, _ = merge_duplicates(
        library(survivor, item("BBBB", attachments=(member_pdf,))), oldest_added
    )
    (result,) = merged.items
    assert result.attachments == (note, member_pdf)
    assert main_pdf(result) == member_pdf.path


def test_duplicate_groups_listing_sorted():
    lib = library(
        item("FFFF", fields={"title": "Second", "url": "https://example.org/second"}),
        item("EEEE", fields={"title": "Second", "url": "https://example.org/second"}),
        item("CCCC"),
        item("AAAA"),
        item("DDDD", fields={"title": "Alone"}),
        item("BBBB", fields={"title": "Lonely"}),
    )
    assert duplicate_groups(lib) == [
        ("zotero:user/AAAA", "zotero:user/CCCC"),
        ("zotero:user/EEEE", "zotero:user/FFFF"),
    ]
    extra = [{"zotero:user/DDDD", "zotero:user/BBBB"}, {"zotero:user/FFFF", "zotero:user/CCCC"}]
    assert duplicate_groups(lib, extra) == [
        ("zotero:user/AAAA", "zotero:user/CCCC", "zotero:user/EEEE", "zotero:user/FFFF"),
        ("zotero:user/BBBB", "zotero:user/DDDD"),
    ]
