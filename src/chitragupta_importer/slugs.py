"""Segment slugs, slug paths, display paths and the collection lock that freezes slugs."""

import re
import unicodedata
from collections.abc import Callable, Iterable, Mapping, Sequence, Set
from dataclasses import dataclass, replace
from typing import Literal

from chitragupta_importer.citekeys import free_spelling
from chitragupta_importer.model import Collection

_OUTSIDE_SLUG_ALPHABET = re.compile(r"[^a-z0-9]+")
_LINE_BREAKERS = str.maketrans({"\t": " ", "\n": " ", "\r": " "})


@dataclass(frozen=True)
class CollectionRecord:
    """One collection lock line: a collection's frozen segment slug, parent and name."""

    collection_id: str
    parent_id: str | None
    slug: str
    name: str
    status: Literal["live", "retired"]


def segment_slug(name: str) -> str:
    """Return the lower-case `[a-z0-9-]` form of a collection name (`collection` if empty)."""
    folded = unicodedata.normalize("NFKD", name)
    ascii_only = "".join(c for c in folded if not unicodedata.combining(c))
    return _OUTSIDE_SLUG_ALPHABET.sub("-", ascii_only.lower()).strip("-") or "collection"


def _clean(name: str) -> str:
    return name.translate(_LINE_BREAKERS)


def parse_collection_lock(text: str) -> dict[str, CollectionRecord]:
    """Read collection lock text into collection ID -> record; ValueError if malformed."""
    records = {}
    for number, line in enumerate(text.split("\n"), start=1):
        if line.strip():
            fields = line.split("\t")
            if len(fields) != 5:
                raise ValueError(f"line {number}: expected 5 tab-separated fields")
            collection_id, parent_id, slug, name, status = fields
            if status not in ("live", "retired"):
                raise ValueError(f"line {number}: status {status!r} is not live or retired")
            parent = None if parent_id == "-" else parent_id
            records[collection_id] = CollectionRecord(collection_id, parent, slug, name, status)
    return records


def format_collection_lock(records: Mapping[str, CollectionRecord]) -> str:
    """Write the collection lock as tab-separated lines sorted by collection ID."""
    lines = []
    for key in sorted(records):
        r = records[key]
        parent = "-" if r.parent_id is None else r.parent_id
        lines.append(f"{key}\t{parent}\t{r.slug}\t{_clean(r.name)}\t{r.status}\n")
    return "".join(lines)


def _with_ancestors(start: Iterable[str], parents: Mapping[str, str | None]) -> set[str]:
    found: set[str] = set()
    for key in start:
        current: str | None = key
        while current is not None and current not in found:
            found.add(current)
            current = parents.get(current)
    return found


def _live(records: Mapping[str, CollectionRecord]) -> dict[str, CollectionRecord]:
    return {k: r for k, r in records.items() if r.status == "live"}


def _paths(
    records: Mapping[str, CollectionRecord], part: Callable[[CollectionRecord], str], sep: str
) -> dict[str, str]:
    live = _live(records)
    paths: dict[str, str] = {}

    def path(key: str) -> str:
        if key not in paths:
            record = live[key]
            own = part(record)
            parent = record.parent_id
            paths[key] = own if parent not in live else f"{path(parent)}{sep}{own}"
        return paths[key]

    for key in live:
        path(key)
    return paths


def slug_paths(records: Mapping[str, CollectionRecord]) -> dict[str, str]:
    """Return collection ID -> slug path (segment slugs from the root joined by `.`), live only."""
    return _paths(records, lambda r: r.slug, ".")


def display_paths(records: Mapping[str, CollectionRecord]) -> dict[str, str]:
    """Return collection ID -> display path (names from the root joined by ` / `), live only."""
    return _paths(records, lambda r: r.name, " / ")


def name_table_rows(
    records: Mapping[str, CollectionRecord], used: Set[str]
) -> list[tuple[str, str]]:
    """Return (slug path, own name) for each live collection in `used` or an ancestor of one."""
    live = _live(records)
    keys = _with_ancestors(set(used) & set(live), {k: r.parent_id for k, r in live.items()})
    paths = slug_paths(records)
    return sorted((paths[key], live[key].name) for key in keys)


def _siblings(
    records: Mapping[str, CollectionRecord], parent_id: str | None
) -> list[CollectionRecord]:
    return sorted(
        (r for r in records.values() if r.parent_id == parent_id), key=lambda r: r.collection_id
    )


def _relocated_slug(records: Mapping[str, CollectionRecord], record: CollectionRecord) -> str:
    """Keep a moved or returning collection's slug unless a live sibling holds it."""
    siblings = _siblings(records, record.parent_id)
    if record.slug not in {r.slug for r in siblings if r.status == "live"}:
        return record.slug
    return free_spelling(record.slug, {r.slug for r in siblings})


def _new_slug(records: Mapping[str, CollectionRecord], collection: Collection) -> str:
    """Take back a same-named retired sibling's free slug, else a slug with a clash suffix."""
    siblings = _siblings(records, collection.parent_id)
    live_slugs = {r.slug for r in siblings if r.status == "live"}
    for r in siblings:
        if r.status == "retired" and r.name == collection.name and r.slug not in live_slugs:
            return r.slug
    return free_spelling(segment_slug(collection.name), {r.slug for r in siblings})


def _library(collections: Sequence[Collection]) -> dict[str, Collection]:
    """Index the library's collections, treating a parent outside it as no parent."""
    ids = {c.collection_id for c in collections}
    return {
        c.collection_id: Collection(
            c.collection_id, c.parent_id if c.parent_id in ids else None, _clean(c.name)
        )
        for c in collections
    }


def _changes(
    lock: Mapping[str, CollectionRecord], records: Mapping[str, CollectionRecord]
) -> list[str]:
    old_paths, new_paths = slug_paths(lock), slug_paths(records)
    lines = []
    for key, record in records.items():
        old = lock.get(key)
        if record.status == "retired":
            if old is not None and old.status == "live":
                lines.append(f"retired {old_paths[key]}")
        elif old is None or old.status == "retired":
            lines.append(f"new {new_paths[key]}")
        else:
            if old.name != record.name:
                lines.append(f"renamed {old.name} -> {record.name}")
            if old.parent_id != record.parent_id:
                lines.append(f"moved {old_paths[key]} -> {new_paths[key]}")
    return sorted(lines)


def update_collections(
    lock: Mapping[str, CollectionRecord], collections: Sequence[Collection], used: Set[str]
) -> tuple[dict[str, CollectionRecord], list[str]]:
    """Bring the collection lock up to date with the library; return (new lock, change lines).

    `used` holds the collection IDs directly holding an included item. Every
    collection in `used` or already in the lock, and all their ancestors, gets a
    live record; a locked collection gone from the library is retired. Segment
    slugs never change, except that a moved or returning collection whose slug a
    live sibling holds takes a clash suffix. Gone collections are retired first,
    so their slugs are free to re-created and moved collections in the same run.
    New collections are taken in collection-ID order.
    """
    library = _library(collections)
    parents = {k: c.parent_id for k, c in library.items()}
    needed = _with_ancestors((set(used) | set(lock)) & set(library), parents)
    records = dict(lock)
    for key in set(lock) - set(library):
        records[key] = replace(lock[key], status="retired")
    relocated = []
    for key in sorted(needed & set(lock)):
        old, now = lock[key], library[key]
        record = CollectionRecord(key, now.parent_id, old.slug, now.name, "live")
        if old.status == "retired" or old.parent_id != now.parent_id:
            relocated.append(record)
            del records[key]
        else:
            records[key] = record
    for record in relocated:
        records[record.collection_id] = replace(record, slug=_relocated_slug(records, record))
    for key in sorted(needed - set(lock)):
        collection = library[key]
        slug = _new_slug(records, collection)
        records[key] = CollectionRecord(key, collection.parent_id, slug, collection.name, "live")
    return records, _changes(lock, records)
