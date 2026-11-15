"""The safe-citekey rule and the key rule that proposes a citekey stem for an item."""

import re
import unicodedata

from chitragupta_importer.model import Item

_FORBIDDEN = frozenset('/\\:*?"<>|')
_RESERVED = frozenset(
    ["CON", "PRN", "AUX", "NUL"]
    + [f"COM{n}" for n in range(1, 10)]
    + [f"LPT{n}" for n in range(1, 10)]
)
_STOP_WORDS = frozenset(
    "a an the some from on in to of do with der die das ein eine einer eines einem"
    " einen un une la le l el las los al uno una unos unas de des del d".split()
)
_WORD = re.compile(r"\w[\w-]*")
_YEAR = re.compile(r"[0-9]{4}")
_OUTSIDE_KEY_ALPHABET = re.compile(r"[^a-z0-9-]")


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
    authors = [c for c in item.creators if c.role == "author"]
    chosen = authors or list(item.creators)
    return _normalise(chosen[0].last) if chosen else "noauthor"


def _title_part(item: Item) -> str:
    words = _WORD.findall(item.fields.get("title", ""))
    kept = [w for w in words if w.casefold() not in _STOP_WORDS]
    return _normalise(kept[0]) if kept else ""


def _year_part(item: Item) -> str:
    year = _YEAR.search(item.fields.get("date", ""))
    return year.group() if year else "nodate"


def key_stem(item: Item) -> str:
    """Return `<creator>_<titleword>_<year>`, the stem of the item's proposed citekey."""
    return f"{_creator_part(item)}_{_title_part(item)}_{_year_part(item)}"
