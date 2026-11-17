"""Bootstrap: freeze the citekeys of an existing bibliography in the citekey lock.

Each entry of the existing bibliography is matched to an item by, in order,
PDF content hash, DOI, URL and title; the first level with any match decides.
Several matches at that level are narrowed to the items whose title equals
the entry's, if there are any; more than one left is ambiguous. A merged item claimed by
several entries freezes one citekey; the others are dropped citekeys. An
entry whose URL tie the title cannot break names a duplicate group.
"""

import re
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Set
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

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


@dataclass(frozen=True)
class _Match:
    """An entry's citekey, its first matching level, the item IDs found there, its PDFs."""

    citekey: str
    level: int
    found: frozenset[str]
    pdfs: frozenset[str]


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
_PDF_LEVEL, _URL_LEVEL = 0, 2


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


def _match(entry: dict[str, str], directory: Path, indexes, titles: Mapping[str, str]) -> _Match:
    """Match the entry to item IDs at its first matching level.

    Several matches are narrowed to the items whose normalised title equals
    the entry's, if there are any; otherwise all are kept. An entry
    matching nothing has level `len(_LEVELS)`.
    """
    keys = [entry_keys(entry, directory) for _, entry_keys in _LEVELS]
    pdfs = frozenset(keys[_PDF_LEVEL])
    for level, (entry_keys, index) in enumerate(zip(keys, indexes, strict=True)):
        found = set().union(*(index.get(key, set()) for key in entry_keys))
        if found:
            title = normalise.normal_title(entry.get("title", ""))
            same_title = {item_id for item_id in found if titles[item_id] == title}
            kept = same_title if same_title and title else found
            return _Match(entry["ID"], level, frozenset(kept), pdfs)
    return _Match(entry["ID"], len(_LEVELS), frozenset(), pdfs)


def _frozen_citekey(claimants: list[_Match], stem: str, survivor_pdfs: Set[str]) -> str:
    """The one claimant whose own PDF is the survivor's, if exactly one is.

    Otherwise the key rule's stem, else the smallest without a clash suffix,
    else the smallest.
    """
    by_pdf = [m.citekey for m in claimants if m.pdfs & survivor_pdfs]
    if len(by_pdf) == 1:
        return by_pdf[0]
    citekeys = [m.citekey for m in claimants]
    unsuffixed = [c for c in citekeys if not _CLASH_SUFFIX.search(c)]
    return min([c for c in citekeys if c == stem] or unsuffixed or citekeys)


def _read_entries(existing: Path) -> list[dict[str, str]]:
    parser = BibTexParser(common_strings=True, ignore_nonstandard_types=False)
    return parser.parse(existing.read_text(encoding="utf-8")).entries


def _refusals(
    matches: list[_Match],
    claims: dict[str, list[_Match]],
    merged: Set[str],
    frozen: Mapping[str, str],
) -> Iterable[str]:
    counts = Counter(m.citekey for m in matches)
    for citekey in sorted(c for c, n in counts.items() if n > 1):
        yield f"duplicate citekey {citekey} in existing bibliography"
    ambiguous = sorted(m.citekey for m in matches if len(m.found) > 1)
    if ambiguous:
        yield f"ambiguous entries, each matching several items: {', '.join(ambiguous)}"
    for item_id in sorted(claims):
        if len(claims[item_id]) > 1 and item_id not in merged:
            citekeys = ", ".join(sorted(m.citekey for m in claims[item_id]))
            yield f"item {item_id} claimed by entries {citekeys}"
    for citekey in sorted(frozen.values()):
        problem = citekey_problem(citekey)
        if problem is not None:
            yield f"unsafe citekey {citekey!r}: {problem}"


def _match_entries(existing: Path, library: Library) -> list[_Match]:
    """Each entry of the existing bibliography matched to item IDs, in file order."""
    indexes = _index(library)
    titles = {item.item_id: _item_title(item) for item in library.items}
    return [_match(e, existing.parent, indexes, titles) for e in _read_entries(existing)]


def url_tie_groups(existing: Path, library: Library) -> list[frozenset[str]]:
    """The item IDs of each entry first matched at the URL level that the title leaves tied.

    Each such set is a duplicate group; the sets are distinct and sorted.
    """
    ties = {m.found for m in _match_entries(existing, library) if m.level == _URL_LEVEL}
    return sorted((found for found in ties if len(found) > 1), key=sorted)


def _split_frozen(
    frozen: Mapping[str, str], items: Mapping[str, Item]
) -> tuple[dict[str, str], list[str]]:
    """The frozen citekeys of included items (the lock), and those of left-out items."""
    lock, not_included = {}, []
    for item_id, citekey in frozen.items():
        if isinstance(main_pdf(items[item_id]), LeftOutReason):
            not_included.append(citekey)
        else:
            lock[item_id] = citekey
    return lock, not_included


def bootstrap(
    existing: Path,
    library: Library,
    merged: Set[str] = frozenset(),
    survivor_pdfs: Mapping[str, Set[str]] = MappingProxyType({}),
) -> BootstrapResult:
    """Match the existing bibliography's entries to items; refuse if any match is unsafe.

    `merged` holds the item IDs of survivors that absorbed at least one other
    item; only those may be claimed by several entries. `survivor_pdfs` maps
    a merged survivor's item ID to the SHA-256 hashes of the survivor's own
    PDFs in the unmerged library.
    """
    items = {item.item_id: item for item in library.items}
    matches = _match_entries(existing, library)
    claims: dict[str, list[_Match]] = {}
    for match in matches:
        if len(match.found) == 1:
            claims.setdefault(next(iter(match.found)), []).append(match)
    frozen = {
        i: _frozen_citekey(claims[i], key_stem(items[i]), survivor_pdfs.get(i, frozenset()))
        for i in sorted(claims)
    }
    problems = list(_refusals(matches, claims, merged, frozen))
    if problems:
        raise BootstrapRefused("bootstrap refused: " + "; ".join(problems))
    lock, not_included = _split_frozen(frozen, items)
    unmatched = tuple(sorted(m.citekey for m in matches if not m.found))
    dropped = tuple(
        sorted(m.citekey for i, ms in claims.items() for m in ms if m.citekey != frozen[i])
    )
    return BootstrapResult(lock, unmatched, (), tuple(sorted(not_included)), dropped)
