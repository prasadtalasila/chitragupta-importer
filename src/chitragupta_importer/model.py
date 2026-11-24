"""Plain records a source reader produces: items, creators, attachments, collections."""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Creator:
    """One creator of an item; a single-field name is held in `last`."""

    last: str
    first: str
    single_field: bool
    role: str


@dataclass(frozen=True)
class Attachment:
    """One attachment of an item; `path` is absolute, or None when unresolvable."""

    content_type: str | None
    path: Path | None
    file_name: str


@dataclass(frozen=True)
class Collection:
    collection_id: str
    parent_id: str | None
    name: str


@dataclass(frozen=True)
class Item:  # pylint: disable=too-many-instance-attributes
    """One item; `fields` is keyed by the reference manager's field name.

    `date_added` is when the item was added, as `YYYY-MM-DD HH:MM:SS`;
    `replaces` holds the item IDs of the items a merge folded into this one.
    """

    item_id: str
    item_type: str
    fields: Mapping[str, str]
    creators: tuple[Creator, ...]
    attachments: tuple[Attachment, ...]
    collection_ids: tuple[str, ...]
    tags: tuple[str, ...]
    date_added: str = ""
    replaces: tuple[str, ...] = ()


@dataclass(frozen=True)
class Library:
    """One library: items sorted by item ID, collections by collection ID."""

    items: tuple[Item, ...]
    collections: tuple[Collection, ...]
    skipped_libraries: tuple[str, ...]
