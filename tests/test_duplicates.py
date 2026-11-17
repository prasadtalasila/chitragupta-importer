"""Grouping duplicate items of one library and merging each group into its survivor."""

from chitragupta_importer.duplicates import merge_duplicates, oldest_added
from chitragupta_importer.model import Attachment, Collection, Creator, Item, Library
from chitragupta_importer.pdfs import main_pdf

COLLECTIONS = (Collection("zotero:user/COLLAAAA", None, "Twins"),)


def item(key, title="A Twin", item_type="journalArticle", **changes):
    values = {
        "item_id": f"zotero:user/{key}",
        "item_type": item_type,
        "fields": {"title": title},
        "creators": (),
        "attachments": (),
        "collection_ids": (),
        "tags": (),
        "date_added": "2020-01-01 00:00:00",
    }
    values.update(changes)
    return Item(**values)


def with_doi(key, doi, **changes):
    return item(key, fields={"title": "A Twin", "DOI": doi}, **changes)


def pdf(directory, name, content=b"%PDF-1.4 twin\n"):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(content)
    return Attachment("application/pdf", path, name)


def library(*items):
    return Library(items=items, collections=COLLECTIONS, skipped_libraries=("zotero:group-1",))


def ids(lib):
    return [i.item_id for i in lib.items]


def test_same_type_title_and_doi_merged():
    lib = library(with_doi("AAAA", "10.1/A"), with_doi("BBBB", "https://doi.org/10.1/a"))
    merged, duplicates = merge_duplicates(lib, oldest_added)
    assert ids(merged) == ["zotero:user/AAAA"]
    assert duplicates == {"zotero:user/BBBB": "zotero:user/AAAA"}


def test_doi_in_extra_is_shared_identifier():
    other = item("BBBB", fields={"title": "A Twin", "extra": "PMID: 1\nDOI: 10.1/a"})
    _, duplicates = merge_duplicates(library(with_doi("AAAA", "10.1/a"), other), oldest_added)
    assert duplicates == {"zotero:user/BBBB": "zotero:user/AAAA"}


def test_same_type_title_and_pdf_bytes_merged(tmp_path):
    lib = library(
        item("AAAA", title="A twin!", attachments=(pdf(tmp_path / "a", "a.pdf"),)),
        item("BBBB", title="a TWIN", attachments=(pdf(tmp_path / "b", "other.pdf"),)),
    )
    _, duplicates = merge_duplicates(lib, oldest_added)
    assert duplicates == {"zotero:user/BBBB": "zotero:user/AAAA"}


def test_grouping_is_transitive(tmp_path):
    shared = pdf(tmp_path / "c", "c.pdf")
    lib = library(
        with_doi("AAAA", "10.1/a"),
        with_doi("BBBB", "10.1/a", attachments=(pdf(tmp_path / "b", "b.pdf"),)),
        item("CCCC", attachments=(shared,)),
    )
    merged, duplicates = merge_duplicates(lib, oldest_added)
    assert ids(merged) == ["zotero:user/AAAA"]
    assert duplicates == {
        "zotero:user/BBBB": "zotero:user/AAAA",
        "zotero:user/CCCC": "zotero:user/AAAA",
    }


def test_same_title_without_shared_identifier_not_merged(tmp_path):
    lib = library(
        with_doi("AAAA", "10.1/a"),
        with_doi("BBBB", "10.1/b"),
        item("CCCC", attachments=(pdf(tmp_path / "c", "c.pdf", b"one"),)),
        item("DDDD", attachments=(pdf(tmp_path / "d", "d.pdf", b"two"),)),
        item("EEEE"),
        item("FFFF"),
    )
    merged, duplicates = merge_duplicates(lib, oldest_added)
    assert merged.items == lib.items and not duplicates


def test_missing_pdf_and_non_pdf_attachments_are_not_identifiers(tmp_path):
    note = tmp_path / "note.txt"
    note.write_bytes(b"same")
    lib = library(
        item("AAAA", attachments=(Attachment("text/plain", note, "note.txt"),)),
        item("BBBB", attachments=(Attachment("text/plain", note, "note.txt"),)),
        item("CCCC", attachments=(Attachment("application/pdf", tmp_path / "x.pdf", "x.pdf"),)),
        item("DDDD", attachments=(Attachment("application/pdf", tmp_path / "x.pdf", "x.pdf"),)),
    )
    assert not merge_duplicates(lib, oldest_added)[1]


def test_empty_title_never_groups():
    lib = library(
        item("AAAA", fields={"DOI": "10.1/a"}), item("BBBB", fields={"title": "", "DOI": "10.1/a"})
    )
    assert not merge_duplicates(lib, oldest_added)[1]


def test_different_type_not_merged():
    lib = library(with_doi("AAAA", "10.1/a"), with_doi("BBBB", "10.1/a", item_type="book"))
    assert not merge_duplicates(lib, oldest_added)[1]


def test_oldest_added_wins_ties_by_item_id():
    newer = item("AAAA", date_added="2021-01-01 00:00:00")
    tie_b = item("BBBB", date_added="2020-01-01 00:00:00")
    tie_c = item("CCCC", date_added="2020-01-01 00:00:00")
    assert oldest_added([newer, tie_c, tie_b]) is tie_b
    assert oldest_added([newer, item("DDDD", date_added="2019-12-31 23:59:59")]).item_id == (
        "zotero:user/DDDD"
    )


def test_merged_item_unions_attachments_collections_tags(tmp_path):
    shared = b"%PDF shared"
    survivor = item(
        "CCCC",
        fields={"title": "A Twin", "DOI": "10.1/a", "date": "2024"},
        creators=(Creator("Ng", "Andrew", False, "author"),),
        attachments=(pdf(tmp_path / "c", "c.pdf", shared),),
        collection_ids=("zotero:user/COLLCCCC",),
        tags=("twin",),
        date_added="2019-01-01 00:00:00",
    )
    first = item(
        "AAAA",
        fields={"title": "a twin", "date": "2023"},
        creators=(Creator("Other", "", True, "editor"),),
        attachments=(pdf(tmp_path / "a", "a.pdf", shared),),
        collection_ids=("zotero:user/COLLCCCC", "zotero:user/COLLAAAA"),
        tags=("Alpha", "twin"),
    )
    second = with_doi(
        "BBBB",
        "10.1/A",
        attachments=(pdf(tmp_path / "b", "b.pdf", b"other"),),
        collection_ids=("zotero:user/COLLBBBB",),
        tags=("beta", "Zeta"),
    )
    merged, _ = merge_duplicates(library(first, second, survivor), oldest_added)
    (result,) = merged.items
    assert result.item_id == "zotero:user/CCCC"
    assert result.item_type == survivor.item_type
    assert result.fields == survivor.fields and result.creators == survivor.creators
    assert result.date_added == survivor.date_added
    assert [a.file_name for a in result.attachments] == ["c.pdf", "a.pdf", "b.pdf"]
    assert result.collection_ids == (
        "zotero:user/COLLAAAA",
        "zotero:user/COLLBBBB",
        "zotero:user/COLLCCCC",
    )
    assert result.tags == ("Alpha", "beta", "twin", "Zeta")


def test_survivor_inherits_member_pdf(tmp_path):
    older = with_doi("AAAA", "10.1/a")
    newer = with_doi(
        "BBBB",
        "10.1/a",
        attachments=(pdf(tmp_path / "b", "b.pdf"),),
        date_added="2022-01-01 00:00:00",
    )
    merged, _ = merge_duplicates(library(older, newer), oldest_added)
    assert main_pdf(merged.items[0]) == tmp_path / "b" / "b.pdf"


def test_returns_non_survivor_map_and_sorted_items():
    other = item("BBBB", title="Another")
    lib = library(
        with_doi("AAAA", "10.1/a", date_added="2021-01-01 00:00:00"),
        other,
        with_doi("CCCC", "10.1/a"),
        item("DDDD", title="Last"),
    )
    merged, duplicates = merge_duplicates(lib, oldest_added)
    assert ids(merged) == ["zotero:user/BBBB", "zotero:user/CCCC", "zotero:user/DDDD"]
    assert duplicates == {"zotero:user/AAAA": "zotero:user/CCCC"}
    assert merged.items[0] is other
    assert merged.collections == lib.collections
    assert merged.skipped_libraries == lib.skipped_libraries


def test_custom_survivor_rule_is_used():
    lib = library(with_doi("AAAA", "10.1/a"), with_doi("BBBB", "10.1/a"))
    merged, duplicates = merge_duplicates(lib, lambda items: max(items, key=lambda i: i.item_id))
    assert ids(merged) == ["zotero:user/BBBB"]
    assert duplicates == {"zotero:user/AAAA": "zotero:user/BBBB"}
