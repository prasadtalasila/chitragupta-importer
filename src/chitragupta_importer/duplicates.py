"""Group the duplicate items of one library and merge each group into its survivor.

A duplicate group is items with the same item type, the same normalised
title and, transitively, a shared DOI or identical PDF bytes. The grouping
takes any `Item` records and any survivor rule.
"""

from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import replace

from chitragupta_importer.model import Item, Library
from chitragupta_importer.normalise import item_dois, item_pdf_hashes, normal_title

Survivor = Callable[[Sequence[Item]], Item]


def oldest_added(items: Sequence[Item]) -> Item:
    """The item added first; ties go to the smaller item ID."""
    return min(items, key=lambda item: (item.date_added, item.item_id))


def merge_duplicates(library: Library, survivor: Survivor) -> tuple[Library, dict[str, str]]:
    """Replace each duplicate group by its merged survivor.

    Returns the merged library and a map from each non-survivor's item ID
    to its survivor's item ID.
    """
    merged: dict[str, Item] = {}
    duplicates: dict[str, str] = {}
    for group in _groups(library.items):
        kept = survivor(group)
        merged[kept.item_id] = _merge(kept, group)
        duplicates.update({m.item_id: kept.item_id for m in group if m is not kept})
    items = [merged.get(i.item_id, i) for i in library.items if i.item_id not in duplicates]
    return replace(library, items=tuple(sorted(items, key=lambda i: i.item_id))), duplicates


def _groups(items: Iterable[Item]) -> list[list[Item]]:
    """Duplicate groups of two or more, each in item-ID order."""
    candidates: defaultdict[tuple[str, str], list[Item]] = defaultdict(list)
    for item in items:
        title = normal_title(item.fields.get("title", ""))
        if title:
            candidates[item.item_type, title].append(item)
    return [
        group
        for same_title in candidates.values()
        if len(same_title) > 1
        for group in _shared_identifier_groups(same_title)
        if len(group) > 1
    ]


def _shared_identifier_groups(items: list[Item]) -> list[list[Item]]:
    """Union-find over items joined by a shared DOI or PDF hash."""
    parent = list(range(len(items)))

    def root(index: int) -> int:
        while parent[index] != index:
            index = parent[index]
        return index

    first_with: dict[tuple[str, str], int] = {}
    for index, item in enumerate(items):
        keys = {("doi", d) for d in item_dois(item) - {""}}
        keys |= {("pdf", h) for h in item_pdf_hashes(item)}
        for key in keys:
            parent[root(index)] = root(first_with.setdefault(key, index))
    groups: defaultdict[int, list[Item]] = defaultdict(list)
    for index, item in enumerate(items):
        groups[root(index)].append(item)
    return [sorted(group, key=lambda i: i.item_id) for group in groups.values()]


def _merge(kept: Item, group: Sequence[Item]) -> Item:
    """The survivor with every member's attachments, collections and tags."""
    others = sorted((m for m in group if m is not kept), key=lambda i: i.item_id)
    members = [kept, *others]
    tags = {tag for m in members for tag in m.tags}
    return replace(
        kept,
        attachments=tuple(a for m in members for a in m.attachments),
        collection_ids=tuple(sorted({c for m in members for c in m.collection_ids})),
        tags=tuple(sorted(tags, key=lambda tag: (tag.casefold(), tag))),
    )
