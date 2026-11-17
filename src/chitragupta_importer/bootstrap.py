"""Bootstrap: freeze the citekeys of an existing bibliography in the citekey lock.

Each entry of the existing bibliography is matched to an item by, in order,
PDF content hash, DOI, URL and title; the first level with any match decides.
Several matches at that level are narrowed to the one item whose title
equals the entry's, if there is exactly one. A merged item claimed by
several entries freezes one citekey; the others are dropped citekeys.
"""

import re
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Set
from dataclasses import dataclass
from pathlib import Path

from bibtexparser.bparser import BibTexParser

from chitragupta_importer import normalise
from chitragupta_importer.citekeys import citekey_problem, key_stem
from chitragupta_importer.model import Item, Library
from chitragupta_importer.pdfs import LeftOutReason, main_pdf

_ESCAPE = re.compile(r"\\(.)")
_CLASH_SUFFIX = re.compile(r"-[0-9]+$")


@dataclass(frozen=True)
class BootstrapResult:
    """The citekey lock from an existing bibliography; tuples hold sorted citekeys."""

    lock: dict[str, str]
    unmatched: tuple[str, ...]
    ambiguous: tuple[str, ...]
    not_included: tuple[str, ...]
    dropped: tuple[str, ...] = ()


class BootstrapRefused(Exception):
    """An existing bibliography that bootstrap cannot turn into a citekey lock."""


def _split_unescaped(text: str, separator: str) -> list[str]:
    """Split on `separator` not preceded by a backslash; escapes are kept."""
    return re.split(rf"(?<!\\){re.escape(separator)}", text)


def _entry_pdf_hashes(entry: dict[str, str], directory: Path) -> set[str]:
    """Hash the PDFs of the entry's `file` field (`desc:path:mime;...`) found on disk."""
    hashes = set()
    for part in _split_unescaped(entry.get("file", ""), ";"):
        pieces = [_ESCAPE.sub(r"\1", p) for p in _split_unescaped(part, ":")]
        if len(pieces) == 3 and "pdf" in pieces[2]:
            path = directory / pieces[1]
            if path.is_file():
                hashes.add(normalise.hash_file(path))
    return hashes


_Level = tuple[Callable[[Item], set[str]], Callable[[dict[str, str], Path], set[str]]]
_LEVELS: tuple[_Level, ...] = (
    (normalise.item_pdf_hashes, _entry_pdf_hashes),
    (normalise.item_dois, lambda e, _: {normalise.normal_doi(e.get("doi", ""))}),
    (lambda i: {i.fields.get("url", "")}, lambda e, _: {e.get("url", "")}),
    (lambda i: {_item_title(i)}, lambda e, _: {normalise.normal_title(e.get("title", ""))}),
)


def _item_title(item: Item) -> str:
    return normalise.normal_title(item.fields.get("title", ""))


def _index(library: Library) -> list[dict[str, set[str]]]:
    """For each level, map a non-empty match key to the item IDs that have it."""
    indexes: list[dict[str, set[str]]] = []
    for item_keys, _ in _LEVELS:
        index: dict[str, set[str]] = {}
        for item in library.items:
            for key in item_keys(item) - {""}:
                index.setdefault(key, set()).add(item.item_id)
        indexes.append(index)
    return indexes


def _match(entry: dict[str, str], directory: Path, indexes, titles: Mapping[str, str]) -> set[str]:
    """Return the item IDs the entry matches at its first matching level.

    Several matches are narrowed to the one item whose normalised title equals
    the entry's, if there is exactly one; otherwise all are returned.
    """
    for (_, entry_keys), index in zip(_LEVELS, indexes, strict=True):
        found = set().union(*(index.get(key, set()) for key in entry_keys(entry, directory)))
        if found:
            title = normalise.normal_title(entry.get("title", ""))
            same_title = {item_id for item_id in found if titles[item_id] == title}
            return same_title if len(same_title) == 1 and title else found
    return set()


def _frozen_citekey(citekeys: list[str], stem: str) -> str:
    """The key rule's stem, else the smallest without a clash suffix, else the smallest."""
    unsuffixed = [c for c in citekeys if not _CLASH_SUFFIX.search(c)]
    return min([c for c in citekeys if c == stem] or unsuffixed or citekeys)


def _read_entries(existing: Path) -> list[dict[str, str]]:
    parser = BibTexParser(common_strings=True, ignore_nonstandard_types=False)
    return parser.parse(existing.read_text(encoding="utf-8")).entries


def _refusals(
    matches: list[tuple[str, set[str]]],
    claims: dict[str, list[str]],
    merged: Set[str],
    frozen: Mapping[str, str],
) -> Iterable[str]:
    counts = Counter(citekey for citekey, _ in matches)
    for citekey in sorted(c for c, n in counts.items() if n > 1):
        yield f"duplicate citekey {citekey} in existing bibliography"
    ambiguous = sorted(citekey for citekey, found in matches if len(found) > 1)
    if ambiguous:
        yield f"ambiguous entries, each matching several items: {', '.join(ambiguous)}"
    for item_id in sorted(claims):
        if len(claims[item_id]) > 1 and item_id not in merged:
            yield f"item {item_id} claimed by entries {', '.join(sorted(claims[item_id]))}"
    for citekey in sorted(frozen.values()):
        problem = citekey_problem(citekey)
        if problem is not None:
            yield f"unsafe citekey {citekey!r}: {problem}"


def bootstrap(existing: Path, library: Library, merged: Set[str] = frozenset()) -> BootstrapResult:
    """Match the existing bibliography's entries to items; refuse if any match is unsafe.

    `merged` holds the item IDs of survivors that absorbed at least one other
    item; only those may be claimed by several entries.
    """
    indexes = _index(library)
    items = {item.item_id: item for item in library.items}
    titles = {item_id: _item_title(item) for item_id, item in items.items()}
    matches: list[tuple[str, set[str]]] = []
    claims: dict[str, list[str]] = {}
    for entry in _read_entries(existing):
        found = _match(entry, existing.parent, indexes, titles)
        matches.append((entry["ID"], found))
        if len(found) == 1:
            claims.setdefault(next(iter(found)), []).append(entry["ID"])
    frozen = {i: _frozen_citekey(claims[i], key_stem(items[i])) for i in sorted(claims)}
    problems = list(_refusals(matches, claims, merged, frozen))
    if problems:
        raise BootstrapRefused("bootstrap refused: " + "; ".join(problems))
    lock, not_included = {}, []
    for item_id, citekey in frozen.items():
        if isinstance(main_pdf(items[item_id]), LeftOutReason):
            not_included.append(citekey)
        else:
            lock[item_id] = citekey
    unmatched = sorted(citekey for citekey, found in matches if not found)
    dropped = sorted(c for i, cs in claims.items() for c in cs if c != frozen[i])
    return BootstrapResult(lock, tuple(unmatched), (), tuple(sorted(not_included)), tuple(dropped))
