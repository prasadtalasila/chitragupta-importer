"""Citekey renames: the rename lock, its chains and the `cg-renames` block.

A rename records that the paper an old citekey stood for now has another
citekey, its successor. `renames.lock` keeps every rename ever found; the
bibliography's `cg-renames v1` block tells chitragupta which ones apply.
"""

from collections.abc import Iterable, Mapping, Sequence, Set
from dataclasses import dataclass, field

from chitragupta_importer.citekeys import citekey_problem, shorten_long_citekeys
from chitragupta_importer.model import Library


def parse_renames_lock(text: str) -> dict[str, str]:
    """Read rename lock text (`<old>\\t<successor>` lines) into old -> successor.

    Raises ValueError for a line without a tab or an old citekey listed twice.
    """
    renames: dict[str, str] = {}
    for number, line in enumerate(text.splitlines(), start=1):
        if line.strip():
            old, tab, new = line.partition("\t")
            if not tab:
                raise ValueError(f"line {number}: expected <old citekey><tab><citekey>")
            if old in renames:
                raise ValueError(f"line {number}: citekey {old!r} is renamed twice")
            renames[old] = new
    return renames


def format_renames_lock(renames: Mapping[str, str]) -> str:
    """Write the rename lock as `<old>\\t<successor>` lines sorted by old citekey."""
    return "".join(f"{old}\t{renames[old]}\n" for old in sorted(renames))


def add_renames(
    renames: Mapping[str, str], rows: Iterable[tuple[str, str]]
) -> tuple[dict[str, str], list[tuple[str, str]]]:
    """Add `(old, successor)` rows; return the updated lock and the rows added, in order.

    A row for an old citekey already in the lock, or renaming a key to itself,
    is skipped: the first row recorded for a citekey wins.
    """
    updated = dict(renames)
    added = []
    for old, new in rows:
        if old != new and old not in updated:
            updated[old] = new
            added.append((old, new))
    return updated, added


def _last_successor(renames: Mapping[str, str], old: str) -> str | None:
    """The end of `old`'s chain of renames, or None when the chain loops."""
    seen = {old}
    key = renames[old]
    while key in renames and key not in seen:
        seen.add(key)
        key = renames[key]
    return None if key in seen else key


def block_rows(renames: Mapping[str, str], entry_keys: Set[str]) -> list[tuple[str, str]]:
    """The `(old, last successor)` rows chitragupta can apply, sorted by old citekey.

    A row is kept when its last successor is an entry's citekey, the old
    citekey is not, and both pass the safe-citekey rule.
    """
    rows = []
    for old in sorted(renames):
        new = _last_successor(renames, old)
        if new in entry_keys and old not in entry_keys and _safe(old) and _safe(new):
            rows.append((old, new))
    return rows


def _safe(citekey: str) -> bool:
    return citekey_problem(citekey) is None


def render_renames_block(rows: Sequence[tuple[str, str]]) -> str:
    """The `cg-renames v1` comment block of `(old, successor)` rows; "" for none."""
    if not rows:
        return ""
    body = "".join(f"{old}\t{new}\n" for old, new in rows)
    return f"@comment{{cg-renames v1\n{body}}}\n"


def merge_renames(duplicates: Mapping[str, str], lock: Mapping[str, str]) -> list[tuple[str, str]]:
    """Renames from items merged into a survivor: merged item's key -> survivor's key."""
    return [
        (lock[merged], lock[kept])
        for merged, kept in sorted(duplicates.items())
        if merged in lock and kept in lock
    ]


def zotero_merge_renames(library: Library, lock: Mapping[str, str]) -> list[tuple[str, str]]:
    """Renames from merges in Zotero: a gone item's key -> the key of the item replacing it."""
    live = {item.item_id for item in library.items}
    return [
        (lock[gone], lock[item.item_id])
        for item in library.items
        for gone in item.replaces
        if gone in lock and gone not in live and item.item_id in lock
    ]


@dataclass(frozen=True)
class RenameSources:
    """What an import run knows about retired citekeys.

    `duplicates` maps each item merged here to its survivor; `successors`
    maps each citekey a bootstrap dropped to the one frozen for its item.
    """

    library: Library
    duplicates: Mapping[str, str] = field(default_factory=dict)
    successors: Mapping[str, str] = field(default_factory=dict)


def plan_renames(
    renames: Mapping[str, str],
    lock: Mapping[str, str],
    stems: Mapping[str, str],
    sources: RenameSources,
) -> tuple[dict[str, str], dict[str, str], list[tuple[str, str]]]:
    """The citekey lock, the rename lock and the renames this run adds.

    Renames come from a bootstrap's dropped citekeys, merges here and in
    Zotero, then citekeys too long to keep; `stems` holds the key-rule stems
    of the included items.
    """
    found = [
        *sorted(sources.successors.items()),
        *merge_renames(sources.duplicates, lock),
        *zotero_merge_renames(sources.library, lock),
    ]
    lock, shortened = shorten_long_citekeys(stems, lock)
    renames, added = add_renames(renames, [*found, *shortened])
    return lock, renames, added
