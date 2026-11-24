"""Reading a Zotero data directory into plain records."""

import sqlite3
from pathlib import Path

import pytest
from zotero_fixture import ZoteroFixture

from chitragupta_importer.model import Attachment, Collection, Creator
from chitragupta_importer.sources.zotero import UnknownSchema, read_library


def _set_attachment_path(data_dir, path):
    conn = sqlite3.connect(data_dir / "zotero.sqlite")
    conn.execute("UPDATE itemAttachments SET path = ?", (path,))
    conn.commit()
    conn.close()


def test_reads_item_fields_creators_tags_and_collections(tmp_path):
    fx = ZoteroFixture(tmp_path)
    fx.add_collection("COLLAAAA", "Tide Pools")
    fx.add_collection("COLLBBBB", "TP Gauges", parent_key="COLLAAAA")
    fx.add_item(
        "ITEMAAAA",
        fields={"title": "A Twin", "date": "2024-02-01"},
        creators=[("Ostrander", "Ingrid", "author")],
        pdfs=[("a.pdf", b"%PDF-1")],
        collections=["COLLBBBB"],
        tags=["twin"],
    )
    lib = read_library(fx.build())
    item = lib.items[0]
    assert item.item_id == "zotero:user/ITEMAAAA"
    assert item.item_type == "journalArticle"
    assert item.fields["title"] == "A Twin"
    assert item.creators == (Creator("Ostrander", "Ingrid", False, "author"),)
    assert item.collection_ids == ("zotero:user/COLLBBBB",)
    assert item.tags == ("twin",)
    assert item.attachments[0].path.name == "a.pdf" and item.attachments[0].path.exists()
    assert item.attachments[0].content_type == "application/pdf"
    assert lib.collections[0] == Collection("zotero:user/COLLAAAA", None, "Tide Pools")
    assert lib.collections[1] == Collection(
        "zotero:user/COLLBBBB", "zotero:user/COLLAAAA", "TP Gauges"
    )
    assert not lib.skipped_libraries


def test_orders_items_creators_tags_and_memberships(tmp_path):
    fx = ZoteroFixture(tmp_path)
    fx.add_collection("COLLZZZZ", "Zeta")
    fx.add_collection("COLLAAAA", "Alpha")
    fx.add_item("ITEMZZZZ", fields={"title": "Z"}, collections=["COLLZZZZ", "COLLAAAA"])
    fx.add_item(
        "ITEMAAAA",
        creators=[("Ng", "Andrew", "author"), ("IEEE", None, "editor")],
        tags=["beta", "Alpha", "gamma"],
    )
    lib = read_library(fx.build())
    assert [item.item_id for item in lib.items] == ["zotero:user/ITEMAAAA", "zotero:user/ITEMZZZZ"]
    assert [c.collection_id for c in lib.collections] == [
        "zotero:user/COLLAAAA",
        "zotero:user/COLLZZZZ",
    ]
    first, second = lib.items
    assert first.creators == (
        Creator("Ng", "Andrew", False, "author"),
        Creator("IEEE", "", True, "editor"),
    )
    assert first.tags == ("Alpha", "beta", "gamma")
    assert second.collection_ids == ("zotero:user/COLLAAAA", "zotero:user/COLLZZZZ")
    assert not first.fields and not first.attachments


def test_skips_notes_and_annotations(tmp_path):
    fx = ZoteroFixture(tmp_path)
    fx.add_item("NOTEAAAA", item_type="note")
    fx.add_item("ANNOAAAA", item_type="annotation")
    fx.add_item("ITEMAAAA", item_type="book")
    lib = read_library(fx.build())
    assert [(item.item_id, item.item_type) for item in lib.items] == [
        ("zotero:user/ITEMAAAA", "book")
    ]


def test_skips_deleted_items_and_collections(tmp_path):
    fx = ZoteroFixture(tmp_path)
    fx.add_collection("COLLAAAA", "Kept")
    fx.add_collection("COLLDDDD", "Trashed", deleted=True)
    fx.add_item("ITEMDDDD", deleted=True, collections=["COLLAAAA"])
    fx.add_item("ITEMAAAA", collections=["COLLAAAA", "COLLDDDD"])
    lib = read_library(fx.build())
    assert [item.item_id for item in lib.items] == ["zotero:user/ITEMAAAA"]
    assert [c.collection_id for c in lib.collections] == ["zotero:user/COLLAAAA"]
    assert lib.items[0].collection_ids == ("zotero:user/COLLAAAA",)


def test_skips_deleted_attachments(tmp_path):
    fx = ZoteroFixture(tmp_path)
    fx.add_item("ITEMAAAA", pdfs=[("a.pdf", b"%PDF-1"), ("b.pdf", b"%PDF-1")])
    data_dir = fx.build()
    conn = sqlite3.connect(data_dir / "zotero.sqlite")
    conn.execute(
        "INSERT INTO deletedItems (itemID) "
        "SELECT itemID FROM itemAttachments WHERE path = 'storage:a.pdf'"
    )
    conn.commit()
    conn.close()
    lib = read_library(data_dir)
    assert [a.file_name for a in lib.items[0].attachments] == ["b.pdf"]


@pytest.mark.parametrize("version", [120, 132])
def test_refuses_unknown_schema(tmp_path, version):
    fx = ZoteroFixture(tmp_path)
    with pytest.raises(UnknownSchema, match=str(version)):
        read_library(fx.build(schema_version=version))


@pytest.mark.parametrize("version", [121, 122, 130, 131])
def test_reads_zotero_7_to_9_schemas(tmp_path, version):
    # Zotero's userdata migrations 122-131 only add columns, indexes and settings
    # the reader never selects; 128 rewrites storage paths to `storage:<name>`.
    fx = ZoteroFixture(tmp_path)
    fx.add_item("ITEMAAAA", pdfs=[("a.pdf", b"%PDF-1")])
    assert read_library(fx.build(schema_version=version)).items[0].item_id == "zotero:user/ITEMAAAA"


def test_lists_group_libraries_as_skipped(tmp_path):
    fx = ZoteroFixture(tmp_path)
    fx.add_group_library(42, "Lab")
    fx.add_item("ITEMAAAA")
    lib = read_library(fx.build())
    assert lib.skipped_libraries == ("zotero:group-42",)
    assert [item.item_id for item in lib.items] == ["zotero:user/ITEMAAAA"]


def test_reads_only_the_user_library(tmp_path):
    fx = ZoteroFixture(tmp_path)
    fx.add_group_library(42, "Lab")
    fx.add_item("ITEMAAAA")
    data_dir = fx.build()
    conn = sqlite3.connect(data_dir / "zotero.sqlite")
    group_library = conn.execute("SELECT libraryID FROM groups").fetchone()[0]
    conn.execute(
        "INSERT INTO items (itemTypeID, libraryID, key) VALUES (1, ?, 'GROUPITM')",
        (group_library,),
    )
    conn.execute(
        "INSERT INTO collections (collectionName, libraryID, key) VALUES ('G', ?, 'GROUPCOL')",
        (group_library,),
    )
    conn.commit()
    conn.close()
    lib = read_library(data_dir)
    assert [item.item_id for item in lib.items] == ["zotero:user/ITEMAAAA"]
    assert not lib.collections


def test_reads_copy_including_wal(tmp_path):
    fx = ZoteroFixture(tmp_path)
    fx.add_item("ITEMAAAA")
    data_dir = fx.build()
    database = data_dir / "zotero.sqlite"
    writer = sqlite3.connect(database)
    writer.execute("PRAGMA journal_mode = WAL")
    writer.execute("PRAGMA wal_autocheckpoint = 0")
    writer.execute("UPDATE items SET key = 'ITEMWWWW'")
    writer.commit()
    try:
        wal = data_dir / "zotero.sqlite-wal"
        assert wal.exists()
        before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in (database, wal)}
        lib = read_library(data_dir)
        after = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in (database, wal)}
    finally:
        writer.close()
    assert [item.item_id for item in lib.items] == ["zotero:user/ITEMWWWW"]
    assert after == before


def test_attachment_without_file_keeps_its_path(tmp_path):
    fx = ZoteroFixture(tmp_path)
    fx.add_item("ITEMAAAA", pdfs=[("gone.pdf", None)])
    data_dir = fx.build()
    (attachment,) = read_library(data_dir).items[0].attachments
    assert attachment.path.is_absolute() and not attachment.path.exists()
    assert attachment.path.parent.parent == data_dir.absolute() / "storage"


def test_unresolvable_attachment_path_is_none(tmp_path):
    fx = ZoteroFixture(tmp_path)
    fx.add_item("ITEMAAAA", pdfs=[("x.pdf", None)])
    data_dir = fx.build()
    _set_attachment_path(data_dir, "attachments:sub/x.pdf")
    (attachment,) = read_library(data_dir).items[0].attachments
    assert attachment == Attachment("application/pdf", None, "x.pdf")


@pytest.mark.parametrize(
    ("raw", "file_name"),
    [("/home/p/papers/x.pdf", "x.pdf"), ("C:\\Users\\p\\y.pdf", "y.pdf"), ("D:/z.pdf", "z.pdf")],
)
def test_absolute_attachment_path_is_kept(tmp_path, raw, file_name):
    fx = ZoteroFixture(tmp_path)
    fx.add_item("ITEMAAAA", pdfs=[("x.pdf", None)])
    data_dir = fx.build()
    _set_attachment_path(data_dir, raw)
    (attachment,) = read_library(data_dir).items[0].attachments
    assert attachment.path == Path(raw) and attachment.file_name == file_name


def test_attachment_without_path_is_none(tmp_path):
    fx = ZoteroFixture(tmp_path)
    fx.add_item("ITEMAAAA", pdfs=[("x.pdf", None)])
    data_dir = fx.build()
    _set_attachment_path(data_dir, None)
    (attachment,) = read_library(data_dir).items[0].attachments
    assert attachment == Attachment("application/pdf", None, "")


def test_reader_reads_date_added(tmp_path):
    fx = ZoteroFixture(tmp_path)
    fx.add_item("ITEMAAAA", date_added="2019-05-06 07:08:09")
    fx.add_item("ITEMBBBB")
    lib = read_library(fx.build())
    assert [item.date_added for item in lib.items] == ["2019-05-06 07:08:09", "2020-01-01 00:00:00"]


def _replaces_of(tmp_path, uris):
    fx = ZoteroFixture(tmp_path)
    fx.add_item("ITEMAAAA", fields={"title": "A Twin"}, replaces=uris)
    return read_library(fx.build()).items[0].replaces


def test_item_lists_the_items_it_replaced(tmp_path):
    uris = [
        "http://zotero.org/users/local/abCD1234/items/OLD00002",
        "http://zotero.org/users/12345/items/OLD00001",
    ]
    assert _replaces_of(tmp_path, uris) == ("zotero:user/OLD00001", "zotero:user/OLD00002")


def test_replaced_group_item_or_odd_uri_is_ignored(tmp_path):
    assert _replaces_of(tmp_path, ["http://zotero.org/groups/7/items/GRP00001", "urn:x"]) == ()
