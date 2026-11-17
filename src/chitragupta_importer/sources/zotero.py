"""Read a Zotero data directory's personal library into plain records.

The reader copies `zotero.sqlite`, and its `-journal` or `-wal` file when
present, into a temporary directory and opens only the copy, so the
originals are never opened at all. SQLite rolls a copied hot journal back
when it opens the copy. A database that changes size or modification time
while it is copied is copied again, at most `_COPY_ATTEMPTS` times in all.
"""

import re
import shutil
import sqlite3
import tempfile
from collections import defaultdict
from pathlib import Path

from chitragupta_importer.model import Attachment, Collection, Creator, Item, Library

KNOWN_SCHEMA_VERSIONS = frozenset({121})

_DATABASE = "zotero.sqlite"
_SIDE_FILES = ("-journal", "-wal")
_COPY_ATTEMPTS = 3
_STORAGE_PREFIX = "storage:"
_PATH_PREFIX = re.compile(r"^(storage|attachments):")
_ABSOLUTE_PATH = re.compile(r"^(/|[A-Za-z]:[\\/])")
_NOT_ITEMS = ("attachment", "note", "annotation")

_ITEMS = f"""
    SELECT i.itemID, i.key, t.typeName, i.dateAdded FROM items i JOIN itemTypes t USING (itemTypeID)
    WHERE i.libraryID = ? AND t.typeName NOT IN ({", ".join("?" for _ in _NOT_ITEMS)})
      AND i.itemID NOT IN (SELECT itemID FROM deletedItems)"""
_FIELDS = """
    SELECT d.itemID, f.fieldName, v.value
    FROM itemData d JOIN fields f USING (fieldID) JOIN itemDataValues v USING (valueID)
    ORDER BY d.itemID, f.fieldName"""
_CREATORS = """
    SELECT ic.itemID, c.lastName, c.firstName, c.fieldMode, t.creatorType
    FROM itemCreators ic JOIN creators c USING (creatorID) JOIN creatorTypes t USING (creatorTypeID)
    ORDER BY ic.itemID, ic.orderIndex"""
_TAGS = "SELECT it.itemID, t.name FROM itemTags it JOIN tags t USING (tagID)"
_ATTACHMENTS = """
    SELECT a.parentItemID, i.key, a.contentType, a.path
    FROM itemAttachments a JOIN items i USING (itemID)
    WHERE a.parentItemID IS NOT NULL AND a.itemID NOT IN (SELECT itemID FROM deletedItems)
    ORDER BY a.parentItemID, i.key"""
_LIVE_COLLECTIONS = "c.collectionID NOT IN (SELECT collectionID FROM deletedCollections)"
_COLLECTIONS = f"""
    SELECT c.key, p.key, c.collectionName
    FROM collections c LEFT JOIN collections p ON p.collectionID = c.parentCollectionID
    WHERE c.libraryID = ? AND {_LIVE_COLLECTIONS}"""
_MEMBERSHIPS = f"""
    SELECT ci.itemID, c.key FROM collectionItems ci JOIN collections c USING (collectionID)
    WHERE {_LIVE_COLLECTIONS}"""


class UnreadableLibrary(Exception):
    """A Zotero data directory whose personal library cannot be read."""


class UnknownSchema(Exception):
    """The Zotero database has a `userdata` schema version this reader does not know."""


def read_library(data_dir: Path) -> Library:
    """Read the personal library of the Zotero data directory `data_dir`."""
    data_dir = Path(data_dir).absolute()
    database = data_dir / _DATABASE
    if not database.is_file():
        raise UnreadableLibrary(f"{database}: no Zotero database found")
    with tempfile.TemporaryDirectory() as copy_dir:
        conn = sqlite3.connect(_copy_database(data_dir, Path(copy_dir)))
        try:
            _check_schema(conn)
            return _read(conn, data_dir)
        except sqlite3.DatabaseError as error:
            raise UnreadableLibrary(
                f"{database}: not a readable Zotero database ({error})"
            ) from error
        finally:
            conn.close()


def _copy_database(data_dir: Path, copy_dir: Path) -> Path:
    """Copy the database and its side files until the database stays unchanged throughout."""
    database = data_dir / _DATABASE
    for _ in range(_COPY_ATTEMPTS):
        before = _signature(database)
        shutil.copyfile(database, copy_dir / _DATABASE)
        for suffix in _SIDE_FILES:
            _copy_side_file(data_dir / f"{_DATABASE}{suffix}", copy_dir)
        if _signature(database) == before:
            return copy_dir / _DATABASE
    raise UnreadableLibrary(
        f"{database}: kept changing while it was copied ({_COPY_ATTEMPTS} attempts);"
        " try again when Zotero is idle"
    )


def _signature(path: Path) -> tuple[int, int]:
    status = path.stat()
    return status.st_size, status.st_mtime_ns


def _copy_side_file(side: Path, copy_dir: Path) -> None:
    """Copy `side` into `copy_dir`; when it is gone, drop any copy from an earlier attempt."""
    try:
        shutil.copyfile(side, copy_dir / side.name)
    except FileNotFoundError:
        (copy_dir / side.name).unlink(missing_ok=True)


def _check_schema(conn: sqlite3.Connection) -> None:
    row = conn.execute("SELECT version FROM version WHERE schema = 'userdata'").fetchone()
    found = row[0] if row else None
    if found not in KNOWN_SCHEMA_VERSIONS:
        known = ", ".join(str(v) for v in sorted(KNOWN_SCHEMA_VERSIONS))
        raise UnknownSchema(
            f"Zotero userdata schema version {found} is not known (known versions: {known})"
        )


def _read(conn: sqlite3.Connection, data_dir: Path) -> Library:
    row = conn.execute("SELECT libraryID FROM libraries WHERE type = 'user'").fetchone()
    if row is None:
        raise UnreadableLibrary(f"{data_dir / _DATABASE}: no personal library (type 'user') found")
    (library_id,) = row
    groups = conn.execute("SELECT groupID FROM groups ORDER BY groupID").fetchall()
    return Library(
        items=_items(conn, data_dir, library_id),
        collections=_collections(conn, library_id),
        skipped_libraries=tuple(f"zotero:group-{group_id}" for (group_id,) in groups),
    )


def _items(conn: sqlite3.Connection, data_dir: Path, library_id: int) -> tuple[Item, ...]:
    fields = _by_item(conn, _FIELDS)
    creators = _by_item(conn, _CREATORS)
    tags = _by_item(conn, _TAGS)
    attachments = _by_item(conn, _ATTACHMENTS)
    memberships = _by_item(conn, _MEMBERSHIPS)
    items = [
        Item(
            item_id=_user_id(key),
            item_type=item_type,
            fields={name: str(value) for name, value in fields[item_id]},
            creators=tuple(_creator(*row) for row in creators[item_id]),
            attachments=tuple(_attachment(data_dir, *row) for row in attachments[item_id]),
            collection_ids=tuple(sorted(_user_id(key) for (key,) in memberships[item_id])),
            tags=tuple(sorted((name for (name,) in tags[item_id]), key=_tag_order)),
            date_added=date_added or "",
        )
        for item_id, key, item_type, date_added in conn.execute(_ITEMS, (library_id, *_NOT_ITEMS))
    ]
    return tuple(sorted(items, key=lambda item: item.item_id))


def _collections(conn: sqlite3.Connection, library_id: int) -> tuple[Collection, ...]:
    collections = [
        Collection(_user_id(key), _user_id(parent_key) if parent_key else None, name)
        for key, parent_key, name in conn.execute(_COLLECTIONS, (library_id,))
    ]
    return tuple(sorted(collections, key=lambda collection: collection.collection_id))


def _by_item(conn: sqlite3.Connection, query: str) -> defaultdict[int, list[tuple]]:
    """Group a query's rows by their first column, an itemID, keeping row order."""
    grouped: defaultdict[int, list[tuple]] = defaultdict(list)
    for item_id, *rest in conn.execute(query):
        grouped[item_id].append(tuple(rest))
    return grouped


def _user_id(key: str) -> str:
    return f"zotero:user/{key}"


def _tag_order(name: str) -> tuple[str, str]:
    return (name.casefold(), name)


def _creator(last: str | None, first: str | None, field_mode: int, role: str) -> Creator:
    return Creator(last or "", first or "", field_mode == 1, role)


def _attachment(data_dir: Path, key: str, content_type: str | None, raw: str | None) -> Attachment:
    """Resolve Zotero's stored attachment path: `storage:NAME`, absolute, or neither."""
    if raw is None:
        return Attachment(content_type, None, "")
    rest = _PATH_PREFIX.sub("", raw)
    file_name = re.split(r"[\\/]", rest)[-1]
    if raw.startswith(_STORAGE_PREFIX):
        path = data_dir / "storage" / key / rest
    elif _ABSOLUTE_PATH.match(raw):
        path = Path(raw)
    else:
        path = None
    return Attachment(content_type, path, file_name)
