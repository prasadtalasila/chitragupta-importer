"""The safe-citekey rule, the key rule and the citekey lock that freezes citekeys."""

import re
import unicodedata
from collections.abc import Mapping, Set

from chitragupta_importer.model import Item

_FORBIDDEN = frozenset('/\\:*?"<>|')
_RESERVED = frozenset(
    ["CON", "PRN", "AUX", "NUL"]
    + [f"COM{n}" for n in range(1, 10)]
    + [f"LPT{n}" for n in range(1, 10)]
)
# Zotero's built-in exporter drops these words, and inline HTML tags, from the
# lower-cased title before taking its first word; \b is an ASCII word boundary.
_DROPPED_FROM_TITLE = re.compile(
    r"\b(a|an|the|some|from|on|in|to|of|do|with|der|die|das|ein|eine|einer|eines|einem"
    r"|einen|un|une|la|le|l'|el|las|los|al|uno|una|unos|unas|de|des|del|d')(\s+|\b)"
    r'|</?(i|b|sup|sub|sc|span style="small-caps"|span)>',
    re.ASCII,
)
_YEAR = re.compile(r"[0-9]{4}")
_OUTSIDE_KEY_ALPHABET = re.compile(r"[^a-z0-9_-]")
# The pseudo item ID prefix under which a dropped citekey is reserved in the lock.
DROPPED_PREFIX = "dropped:"


class UnsafeCitekey(ValueError):
    """A citekey that chitragupta's safe-citekey rule rejects."""


def citekey_problem(citekey: str) -> str | None:
    """Return why chitragupta would reject the citekey, or None if it is safe."""
    if not citekey.strip():
        return "citekey is empty"
    if citekey in (".", ".."):
        return f"citekey is {citekey!r}"
    bad = next((c for c in citekey if c in _FORBIDDEN or ord(c) < 0x20), None)
    if bad is not None:
        return f"citekey contains {bad!r}"
    if citekey[-1] in ". ":
        return f"citekey ends in {citekey[-1]!r}"
    if citekey.split(".", 1)[0].upper() in _RESERVED:
        return "citekey is a reserved Windows device name"
    return None


def _normalise(text: str) -> str:
    folded = unicodedata.normalize("NFKD", text)
    ascii_only = "".join(c for c in folded if not unicodedata.combining(c))
    return _OUTSIDE_KEY_ALPHABET.sub("", ascii_only.lower())


def _creator_part(item: Item) -> str:
    """The first creator's last name, whatever its role; spaces become `_`, commas go."""
    if not item.creators or not item.creators[0].last:
        return "noauthor"
    return _normalise(item.creators[0].last.lower().replace(" ", "_").replace(",", ""))


def _title_part(item: Item) -> str:
    """The first whitespace-separated word left once the dropped words are gone."""
    kept = _DROPPED_FROM_TITLE.sub("", item.fields.get("title", "").lower())
    return _normalise(re.split(r"\s+", kept)[0])


def _year_part(item: Item) -> str:
    year = _YEAR.search(item.fields.get("date", ""))
    return year.group() if year else "nodate"


def key_stem(item: Item) -> str:
    """Return `<creator>_<titleword>_<year>`, the stem of the item's proposed citekey."""
    return f"{_creator_part(item)}_{_title_part(item)}_{_year_part(item)}"


def parse_citekey_lock(text: str) -> dict[str, str]:
    """Read citekey lock text (`<item ID>\\t<citekey>` lines) into item ID -> citekey.

    A dropped citekey's line has the pseudo item ID `dropped:<citekey>`.
    Raises ValueError for a line without a tab or a citekey held by two item IDs.
    """
    lock: dict[str, str] = {}
    holders: dict[str, str] = {}
    for number, line in enumerate(text.splitlines(), start=1):
        if line.strip():
            item_id, tab, citekey = line.partition("\t")
            if not tab:
                raise ValueError(f"line {number}: expected <item ID><tab><citekey>")
            if holders.setdefault(citekey, item_id) != item_id:
                raise ValueError(
                    f"line {number}: citekey {citekey!r} is held by both "
                    f"{holders[citekey]} and {item_id}"
                )
            lock[item_id] = citekey
    return lock


def format_citekey_lock(lock: Mapping[str, str]) -> str:
    """Write the citekey lock as `<item ID>\\t<citekey>` lines sorted by item ID."""
    return "".join(f"{item_id}\t{lock[item_id]}\n" for item_id in sorted(lock))


def free_spelling(stem: str, used: Set[str]) -> str:
    """Return `stem`, or `stem-N` with the lowest N >= 1 not in `used` (a clash suffix)."""
    if stem not in used:
        return stem
    n = 1
    while f"{stem}-{n}" in used:
        n += 1
    return f"{stem}-{n}"


def assign_citekeys(
    stems: Mapping[str, str], lock: Mapping[str, str]
) -> tuple[dict[str, str], list[str]]:
    """Give each new item a citekey and return (updated lock, new item IDs in order).

    Items already in the citekey lock keep their citekey; lock entries are never
    removed. New items are taken in item-ID order: the first claimant of a stem
    keeps it bare, later ones get a clash suffix (-1, -2, ...) that skips every
    spelling in the lock (dormant and retired keys included) or assigned earlier.
    """
    updated = dict(lock)
    used = set(updated.values())
    new = []
    for item_id in sorted(set(stems) - set(lock)):
        citekey = free_spelling(stems[item_id], used)
        problem = citekey_problem(citekey)
        if problem is not None:
            raise UnsafeCitekey(f"new citekey {citekey!r} for item {item_id}: {problem}")
        updated[item_id] = citekey
        used.add(citekey)
        new.append(item_id)
    return updated, new
