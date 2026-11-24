"""Build a synthetic Zotero data directory: `zotero.sqlite` plus `storage/`."""

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA = Path(__file__).parent / "fixtures" / "zotero_schema.sql"
USER_LIBRARY = 1


@dataclass
class _Rows:
    """Lookup tables keyed by value, so each row is inserted once."""

    ids: dict[tuple[str, tuple], int] = field(default_factory=dict)
    attachments: int = 0

    def id_of(self, conn: sqlite3.Connection, table: str, columns: str, *values) -> int:
        if (table, values) not in self.ids:
            marks = ", ".join("?" for _ in values)
            cursor = conn.execute(f"INSERT INTO {table} ({columns}) VALUES ({marks})", values)
            self.ids[table, values] = cursor.lastrowid
        return self.ids[table, values]

    def next_attachment_key(self) -> str:
        self.attachments += 1
        return f"ATTA{self.attachments:04d}"


class ZoteroFixture:
    """Collect collections, items and group libraries; `build` writes them out."""

    def __init__(self, root: Path):
        self.data_dir = root / "zotero"
        self._collections: list[tuple] = []
        self._items: list[dict] = []
        self._groups: list[tuple[int, str]] = []

    def add_collection(self, key, name, parent_key=None, deleted=False):
        self._collections.append((key, name, parent_key, deleted))

    def add_item(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        key,
        item_type="journalArticle",
        fields=None,
        creators=(),
        pdfs=(),
        collections=(),
        tags=(),
        deleted=False,
        date_added="2020-01-01 00:00:00",
        replaces=(),
    ):
        self._items.append(
            {
                "key": key,
                "type": item_type,
                "fields": fields or {},
                "creators": creators,
                "pdfs": pdfs,
                "collections": collections,
                "tags": tags,
                "deleted": deleted,
                "date_added": date_added,
                "replaces": replaces,
            }
        )

    def add_group_library(self, group_id, name):
        self._groups.append((group_id, name))

    def build(self, schema_version=121) -> Path:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.data_dir / "zotero.sqlite")
        conn.executescript(SCHEMA.read_text(encoding="utf-8"))
        conn.execute("INSERT INTO version VALUES ('userdata', ?)", (schema_version,))
        conn.execute(
            "INSERT INTO libraries (libraryID, type, editable, filesEditable) "
            "VALUES (?, 'user', 1, 1)",
            (USER_LIBRARY,),
        )
        rows = _Rows()
        self._write_groups(conn)
        collection_ids = self._write_collections(conn)
        for item in self._items:
            self._write_item(conn, rows, item, collection_ids)
        conn.commit()
        conn.close()
        return self.data_dir

    def _write_groups(self, conn):
        for group_id, name in self._groups:
            cursor = conn.execute(
                "INSERT INTO libraries (type, editable, filesEditable) VALUES ('group', 1, 1)"
            )
            conn.execute(
                "INSERT INTO groups VALUES (?, ?, ?, '', 0)", (group_id, cursor.lastrowid, name)
            )

    def _write_collections(self, conn) -> dict[str, int]:
        ids: dict[str, int] = {}
        for key, name, parent_key, deleted in self._collections:
            cursor = conn.execute(
                "INSERT INTO collections (collectionName, parentCollectionID, libraryID, key) "
                "VALUES (?, ?, ?, ?)",
                (name, ids.get(parent_key), USER_LIBRARY, key),
            )
            ids[key] = cursor.lastrowid
            if deleted:
                conn.execute(
                    "INSERT INTO deletedCollections (collectionID) VALUES (?)", (ids[key],)
                )
        return ids

    def _write_item(self, conn, rows, item, collection_ids):
        item_id = _insert_item(conn, rows, item["key"], item["type"], item["date_added"])
        if item["deleted"]:
            conn.execute("INSERT INTO deletedItems (itemID) VALUES (?)", (item_id,))
        for name, value in item["fields"].items():
            conn.execute(
                "INSERT INTO itemData VALUES (?, ?, ?)",
                (
                    item_id,
                    rows.id_of(conn, "fields", "fieldName", name),
                    rows.id_of(conn, "itemDataValues", "value", value),
                ),
            )
        for index, creator in enumerate(item["creators"]):
            _insert_creator(conn, rows, item_id, index, creator)
        for file_name, content in item["pdfs"]:
            self._write_pdf(conn, rows, item_id, file_name, content)
        for key in item["collections"]:
            conn.execute(
                "INSERT INTO collectionItems VALUES (?, ?, 0)", (collection_ids[key], item_id)
            )
        for tag in item["tags"]:
            tag_id = rows.id_of(conn, "tags", "name", tag)
            conn.execute("INSERT INTO itemTags VALUES (?, ?, 0)", (item_id, tag_id))
        _insert_replaces(conn, rows, item_id, item["replaces"])

    def _write_pdf(self, conn, rows, parent_id, file_name, content):
        key = rows.next_attachment_key()
        item_id = _insert_item(conn, rows, key, "attachment")
        conn.execute(
            "INSERT INTO itemAttachments (itemID, parentItemID, linkMode, contentType, path) "
            "VALUES (?, ?, 1, 'application/pdf', ?)",
            (item_id, parent_id, f"storage:{file_name}"),
        )
        if content is not None:
            folder = self.data_dir / "storage" / key
            folder.mkdir(parents=True, exist_ok=True)
            (folder / file_name).write_bytes(content)


def _insert_item(conn, rows, key, item_type, date_added="2020-01-01 00:00:00") -> int:
    type_id = rows.id_of(conn, "itemTypes", "typeName", item_type)
    cursor = conn.execute(
        "INSERT INTO items (itemTypeID, libraryID, key, dateAdded) VALUES (?, ?, ?, ?)",
        (type_id, USER_LIBRARY, key, date_added),
    )
    return cursor.lastrowid


def _insert_creator(conn, rows, item_id, index, creator):
    """`creator` is `(last, first, role)`; a `first` of None makes a single-field name."""
    last, first, role = creator
    single = first is None
    creator_id = rows.id_of(
        conn,
        "creators",
        "firstName, lastName, fieldMode",
        "" if single else first,
        last,
        int(single),
    )
    role_id = rows.id_of(conn, "creatorTypes", "creatorType", role)
    conn.execute(
        "INSERT INTO itemCreators VALUES (?, ?, ?, ?)", (item_id, creator_id, role_id, index)
    )


def _insert_replaces(conn, rows, item_id, uris):
    """One `dc:replaces` relation from the item to each URI, as a Zotero merge writes."""
    for uri in uris:
        predicate = rows.id_of(conn, "relationPredicates", "predicate", "dc:replaces")
        conn.execute("INSERT INTO itemRelations VALUES (?, ?, ?)", (item_id, predicate, uri))
