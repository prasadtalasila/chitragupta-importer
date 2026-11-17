"""Bootstrap: freeze the citekeys of an existing bibliography in the citekey lock.

Each entry of the existing bibliography is matched to an item by, in order,
PDF content hash, DOI, URL and title; the first level with any match decides.
"""

import re
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from bibtexparser.bparser import BibTexParser

from chitragupta_importer.citekeys import citekey_problem
from chitragupta_importer.model import Item, Library
from chitragupta_importer.normalise import hash_file as _hash_file
from chitragupta_importer.normalise import item_dois as _item_dois
from chitragupta_importer.normalise import normal_doi as _doi
from chitragupta_importer.normalise import normal_title as _title
from chitragupta_importer.pdfs import LeftOutReason, is_pdf, main_pdf

_ESCAPE = re.compile(r"\\(.)")


@dataclass(frozen=True)
class BootstrapResult:
    """The citekey lock from an existing bibliography; tuples hold sorted citekeys."""

    lock: dict[str, str]
    unmatched: tuple[str, ...]
    ambiguous: tuple[str, ...]
    not_included: tuple[str, ...]


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
                hashes.add(_hash_file(path))
    return hashes


def _item_pdf_hashes(item: Item) -> set[str]:
    return {
        _hash_file(a.path)
        for a in item.attachments
        if is_pdf(a) and a.path is not None and a.path.is_file()
    }


_Level = tuple[Callable[[Item], set[str]], Callable[[dict[str, str], Path], set[str]]]
_LEVELS: tuple[_Level, ...] = (
    (_item_pdf_hashes, _entry_pdf_hashes),
    (_item_dois, lambda e, _: {_doi(e.get("doi", ""))}),
    (lambda i: {i.fields.get("url", "")}, lambda e, _: {e.get("url", "")}),
    (lambda i: {_title(i.fields.get("title", ""))}, lambda e, _: {_title(e.get("title", ""))}),
)


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


def _match(entry: dict[str, str], directory: Path, indexes) -> set[str]:
    """Return the item IDs the entry matches at its first matching level."""
    for (_, entry_keys), index in zip(_LEVELS, indexes, strict=True):
        found = set().union(*(index.get(key, set()) for key in entry_keys(entry, directory)))
        if found:
            return found
    return set()


def _read_entries(existing: Path) -> list[dict[str, str]]:
    parser = BibTexParser(common_strings=True, ignore_nonstandard_types=False)
    return parser.parse(existing.read_text(encoding="utf-8")).entries


def _refusals(matches: list[tuple[str, set[str]]], claims: dict[str, list[str]]) -> Iterable[str]:
    counts = Counter(citekey for citekey, _ in matches)
    for citekey in sorted(c for c, n in counts.items() if n > 1):
        yield f"duplicate citekey {citekey} in existing bibliography"
    ambiguous = sorted(citekey for citekey, found in matches if len(found) > 1)
    if ambiguous:
        yield f"ambiguous entries, each matching several items: {', '.join(ambiguous)}"
    for item_id in sorted(claims):
        if len(claims[item_id]) > 1:
            yield f"item {item_id} claimed by entries {', '.join(sorted(claims[item_id]))}"
    for citekey in sorted({c for c, found in matches if len(found) == 1}):
        problem = citekey_problem(citekey)
        if problem is not None:
            yield f"unsafe citekey {citekey!r}: {problem}"


def bootstrap(existing: Path, library: Library) -> BootstrapResult:
    """Match the existing bibliography's entries to items; refuse if any match is unsafe."""
    indexes = _index(library)
    matches: list[tuple[str, set[str]]] = []
    claims: dict[str, list[str]] = {}
    for entry in _read_entries(existing):
        found = _match(entry, existing.parent, indexes)
        matches.append((entry["ID"], found))
        if len(found) == 1:
            claims.setdefault(next(iter(found)), []).append(entry["ID"])
    problems = list(_refusals(matches, claims))
    if problems:
        raise BootstrapRefused("bootstrap refused: " + "; ".join(problems))
    items = {item.item_id: item for item in library.items}
    lock, not_included = {}, []
    for item_id in sorted(claims):
        citekey = claims[item_id][0]
        if isinstance(main_pdf(items[item_id]), LeftOutReason):
            not_included.append(citekey)
        else:
            lock[item_id] = citekey
    unmatched = sorted(citekey for citekey, found in matches if not found)
    return BootstrapResult(lock, tuple(unmatched), (), tuple(sorted(not_included)))
