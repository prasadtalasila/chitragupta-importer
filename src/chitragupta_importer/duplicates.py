"""Group the duplicate items of one library and merge each group into its survivor.

A duplicate group is items with the same item type, the same normalised
title and, transitively, a shared DOI, URL or identical PDF bytes; extra
groups given by the caller join whatever items they name. The grouping
takes any `Item` records and any survivor rule.
"""

from collections import defaultdict
from collections.abc import Callable, Sequence, Set
from dataclasses import replace

from chitragupta_importer.model import Item, Library
from chitragupta_importer.normalise import item_dois, item_pdf_hashes, normal_title
from chitragupta_importer.pdfs import is_pdf

Survivor = Callable[[Sequence[Item]], Item]


def oldest_added(items: Sequence[Item]) -> Item:
    """The item added first; ties go to the smaller item ID."""
    return min(items, key=lambda item: (item.date_added, item.item_id))


def _has_own_pdf(item: Item) -> bool:
    """Whether the item has a PDF attachment that is a file on disk."""
    return any(is_pdf(a) and a.path is not None and a.path.is_file() for a in item.attachments)


def pdf_then_oldest(items: Sequence[Item]) -> Item:
    """The oldest item with its own PDF on disk; if none has one, the oldest item."""
    return oldest_added([item for item in items if _has_own_pdf(item)] or items)


def merge_duplicates(
    library: Library, survivor: Survivor, extra_groups: Sequence[Set[str]] = ()
) -> tuple[Library, dict[str, str]]:
    """Replace each duplicate group by its merged survivor.

    `extra_groups` are sets of item IDs that are each one duplicate group
    too. Returns the merged library and a map from each non-survivor's item
    ID to its survivor's item ID.
    """
    merged: dict[str, Item] = {}
    duplicates: dict[str, str] = {}
    for group in _groups(library.items, extra_groups):
        kept = survivor(group)
        merged[kept.item_id] = _merge(kept, group)
        duplicates.update({m.item_id: kept.item_id for m in group if m.item_id != kept.item_id})
    items = [merged.get(i.item_id, i) for i in library.items if i.item_id not in duplicates]
    return replace(library, items=tuple(sorted(items, key=lambda i: i.item_id))), duplicates


def duplicate_groups(
    library: Library, extra_groups: Sequence[Set[str]] = ()
) -> list[tuple[str, ...]]:
    """The item IDs of each duplicate group, sorted, in sorted order."""
    groups = _groups(library.items, extra_groups)
    return sorted(tuple(item.item_id for item in group) for group in groups)


def _identifiers(item: Item) -> set[tuple[str, str]]:
    """The item's shared-identifier keys: DOI, URL and PDF hash."""
    keys = {("doi", d) for d in item_dois(item) - {""}}
    keys |= {("url", u) for u in {item.fields.get("url", "")} - {""}}
    return keys | {("pdf", h) for h in item_pdf_hashes(item)}


def _same_type_and_title(items: Sequence[Item]) -> list[list[Item]]:
    """Items sharing an item type and a non-empty normalised title, two or more per list."""
    same: defaultdict[tuple[str, str], list[Item]] = defaultdict(list)
    for item in items:
        title = normal_title(item.fields.get("title", ""))
        if title:
            same[item.item_type, title].append(item)
    return [candidates for candidates in same.values() if len(candidates) > 1]


def _groups(items: Sequence[Item], extra_groups: Sequence[Set[str]]) -> list[list[Item]]:
    """Union-find over all items; duplicate groups of two or more, each in item-ID order."""
    parent = {item.item_id: item.item_id for item in items}

    def root(item_id: str) -> str:
        while parent[item_id] != item_id:
            item_id = parent[item_id]
        return item_id

    def join(item_id: str, other: str) -> None:
        parent[root(item_id)] = root(other)

    for candidates in _same_type_and_title(items):
        first_with: dict[tuple[str, str], str] = {}
        for item in candidates:
            for key in _identifiers(item):
                join(item.item_id, first_with.setdefault(key, item.item_id))
    for extra in extra_groups:
        first, *rest = sorted(extra)
        for item_id in rest:
            join(item_id, first)
    groups: defaultdict[str, list[Item]] = defaultdict(list)
    for item in sorted(items, key=lambda i: i.item_id):
        groups[root(item.item_id)].append(item)
    return [group for group in groups.values() if len(group) > 1]


def _merge(kept: Item, group: Sequence[Item]) -> Item:
    """The survivor with the group's collections and tags.

    Attachments are the survivor's own if it has a PDF on disk; otherwise
    the survivor's followed by every other member's, in item-ID order.
    """
    others = sorted((m for m in group if m.item_id != kept.item_id), key=lambda i: i.item_id)
    members = [kept, *others]
    tags = {tag for m in members for tag in m.tags}
    attachments = [kept] if _has_own_pdf(kept) else members
    return replace(
        kept,
        attachments=tuple(a for m in attachments for a in m.attachments),
        collection_ids=tuple(sorted({c for m in members for c in m.collection_ids})),
        tags=tuple(sorted(tags, key=lambda tag: (tag.casefold(), tag))),
    )
