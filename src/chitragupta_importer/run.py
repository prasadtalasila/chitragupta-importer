"""The import run: read a Zotero library and write the papers directory.

Everything that can refuse happens before the first write, so a refused import
run leaves the output directory as it was.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from chitragupta_importer.bibtex import render_bibliography, render_entry, render_name_table
from chitragupta_importer.bootstrap import BootstrapResult, bootstrap
from chitragupta_importer.citekeys import (
    assign_citekeys,
    format_citekey_lock,
    key_stem,
    parse_citekey_lock,
)
from chitragupta_importer.model import Item, Library
from chitragupta_importer.pdfs import LeftOutReason, main_pdf
from chitragupta_importer.slugs import (
    CollectionRecord,
    format_collection_lock,
    name_table_rows,
    parse_collection_lock,
    slug_paths,
    update_collections,
)
from chitragupta_importer.sources.zotero import read_library
from chitragupta_importer.write import atomic_write, copy_pdf, unreferenced_files

BIBLIOGRAPHY = "bibliography.bib"
CITEKEY_LOCK = "citekeys.lock"
COLLECTION_LOCK = "collections.lock"
FILES = "files"


class ImportRefused(Exception):
    """An import run that cannot go ahead; nothing has been written."""


@dataclass(frozen=True)
class RunSummary:
    """What an import run did; `left_out` maps a reason to sorted item IDs."""

    included: int
    left_out: Mapping[str, tuple[str, ...]]
    new_citekeys: tuple[str, ...]
    collection_changes: tuple[str, ...]
    unreferenced: tuple[str, ...]
    skipped_libraries: tuple[str, ...]
    bootstrap: BootstrapResult | None


@dataclass(frozen=True)
class _Plan:
    """Everything an import run writes, worked out before the first write."""

    pdfs: dict[str, Path]
    bibliography: str
    citekey_lock: dict[str, str]
    collection_lock: dict[str, CollectionRecord]


def _read_lock(path: Path, parse):
    """Parse the lock file at `path`, or return an empty lock when there is none."""
    if not path.exists():
        return {}
    try:
        return parse(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError) as error:
        raise ImportRefused(f"{path}: malformed lock file ({error})") from error


def _split(library: Library) -> tuple[dict[str, tuple[Item, Path]], dict[str, tuple[str, ...]]]:
    """Split the items into included (item ID -> item, main PDF) and left out by reason."""
    included: dict[str, tuple[Item, Path]] = {}
    left_out: dict[str, list[str]] = {}
    for item in library.items:
        pdf = main_pdf(item)
        if isinstance(pdf, LeftOutReason):
            left_out.setdefault(str(pdf), []).append(item.item_id)
        else:
            included[item.item_id] = (item, pdf)
    ordered = [str(reason) for reason in LeftOutReason if str(reason) in left_out]
    return included, {reason: tuple(sorted(left_out[reason])) for reason in ordered}


def _seed_lock(out_dir: Path, library: Library, bootstrap_from: Path | None):
    """The citekey lock to start from, and the bootstrap result when bootstrapping."""
    lock_path = out_dir / CITEKEY_LOCK
    if bootstrap_from is None:
        return _read_lock(lock_path, parse_citekey_lock), None
    if lock_path.exists():
        raise ImportRefused(f"{lock_path} exists: bootstrap needs a new citekey lock")
    try:
        bootstrap_from.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ImportRefused(f"{bootstrap_from}: cannot read the bibliography ({error})") from error
    try:
        result = bootstrap(bootstrap_from, library)
    except OSError as error:
        raise ImportRefused(f"{error.filename}: cannot read ({error.strerror})") from error
    return dict(result.lock), result


def _render(
    included: Mapping[str, tuple[Item, Path]],
    citekeys: Mapping[str, str],
    records: Mapping[str, CollectionRecord],
    used: set[str],
) -> str:
    """The bibliography: the name table, then one entry per included item by citekey."""
    paths = slug_paths(records)
    entries = []
    for item_id in sorted(included, key=lambda key: citekeys[key]):
        item = included[item_id][0]
        item_paths = sorted(paths[c] for c in item.collection_ids if c in paths)
        entries.append(render_entry(citekeys[item_id], item, item_paths))
    name_table = render_name_table(name_table_rows(records, used))
    return render_bibliography(name_table, entries)


def _write(out_dir: Path, plan: _Plan) -> None:
    """Write PDFs, the bibliography, the citekey lock and, last, the collection lock."""
    for name, src in sorted(plan.pdfs.items()):
        copy_pdf(src, out_dir / FILES / name)
    atomic_write(out_dir / BIBLIOGRAPHY, plan.bibliography)
    atomic_write(out_dir / CITEKEY_LOCK, format_citekey_lock(plan.citekey_lock))
    atomic_write(out_dir / COLLECTION_LOCK, format_collection_lock(plan.collection_lock))


def import_zotero(data_dir: Path, out_dir: Path, bootstrap_from: Path | None = None) -> RunSummary:
    """Run one import of the Zotero library in `data_dir` into the papers directory `out_dir`.

    Raises ImportRefused, UnknownSchema, BootstrapRefused or UnsafeCitekey before
    anything is written.
    """
    library = read_library(data_dir)
    included, left_out = _split(library)
    lock, bootstrapped = _seed_lock(out_dir, library, bootstrap_from)
    collection_lock = _read_lock(out_dir / COLLECTION_LOCK, parse_collection_lock)
    stems = {item_id: key_stem(item) for item_id, (item, _) in included.items()}
    lock, new_ids = assign_citekeys(stems, lock)
    used = {c for item, _ in included.values() for c in item.collection_ids}
    records, changes = update_collections(collection_lock, library.collections, used)
    plan = _Plan(
        pdfs={f"{lock[item_id]}.pdf": pdf for item_id, (_, pdf) in included.items()},
        bibliography=_render(included, lock, records, used),
        citekey_lock=lock,
        collection_lock=records,
    )
    _write(out_dir, plan)
    return RunSummary(
        included=len(included),
        left_out=left_out,
        new_citekeys=tuple(lock[item_id] for item_id in new_ids),
        collection_changes=tuple(changes),
        unreferenced=tuple(unreferenced_files(out_dir / FILES, set(plan.pdfs))),
        skipped_libraries=library.skipped_libraries,
        bootstrap=bootstrapped,
    )


def format_summary(summary: RunSummary) -> str:
    """The import run summary printed to stdout, one fact per line."""
    lines = [f"included: {summary.included}"]
    lines += [f"left out ({reason}): {len(ids)}" for reason, ids in summary.left_out.items()]
    lines.append(f"new citekeys: {len(summary.new_citekeys)}")
    lines += summary.collection_changes
    unreferenced = f"unreferenced files: {len(summary.unreferenced)}"
    if summary.unreferenced:
        unreferenced += ": " + ", ".join(summary.unreferenced)
    lines.append(unreferenced)
    if summary.skipped_libraries:
        lines.append("skipped libraries: " + ", ".join(summary.skipped_libraries))
    if summary.bootstrap is not None:
        result = summary.bootstrap
        lines.append(
            f"bootstrap: matched {len(result.lock)}, unmatched {len(result.unmatched)}, "
            f"ambiguous {len(result.ambiguous)}, not included {len(result.not_included)}"
        )
    return "".join(f"{line}\n" for line in lines)
