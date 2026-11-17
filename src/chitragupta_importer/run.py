"""The import run: read a Zotero library and write the papers directory.

Everything that can refuse happens before the first write, so a refused import
run leaves the output directory as it was.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from chitragupta_importer.bibtex import render_bibliography, render_entry, render_name_table
from chitragupta_importer.bootstrap import BootstrapResult, bootstrap
from chitragupta_importer.citekeys import (
    assign_citekeys,
    citekey_problem,
    format_citekey_lock,
    key_stem,
    parse_citekey_lock,
)
from chitragupta_importer.duplicates import merge_duplicates, oldest_added
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
class RunSummary:  # pylint: disable=too-many-instance-attributes
    """What an import run did.

    `left_out` maps a reason to sorted item IDs; `duplicates` maps each
    non-survivor's item ID to its survivor's.
    """

    included: int
    left_out: Mapping[str, tuple[str, ...]]
    new_citekeys: tuple[str, ...]
    collection_changes: tuple[str, ...]
    unreferenced: tuple[str, ...]
    skipped_libraries: tuple[str, ...]
    bootstrap: BootstrapResult | None
    duplicates: Mapping[str, str] = field(default_factory=dict)


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
    except ValueError as error:  # UnicodeDecodeError included
        raise ImportRefused(f"{path}: malformed lock file ({error})") from error
    except OSError as error:
        raise ImportRefused(f"{path}: cannot read the lock file ({error.strerror})") from error


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


def _cannot_read(error: OSError, stage: str) -> ImportRefused:
    """The refusal for an `error` while reading item files `stage` (e.g. "during bootstrap")."""
    if error.filename is None:
        return ImportRefused(f"cannot read {stage}: {error}")
    return ImportRefused(f"{error.filename}: cannot read {stage} ({error.strerror})")


def _merged_library(data_dir: Path) -> tuple[Library, dict[str, str]]:
    """The library in `data_dir` with each duplicate group merged into its survivor."""
    library = read_library(data_dir)
    try:
        return merge_duplicates(library, oldest_added)
    except OSError as error:
        raise _cannot_read(error, "while merging duplicate items") from error


def _seed_lock(out_dir: Path, library: Library, bootstrap_from: Path | None, merged: set[str]):
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
        result = bootstrap(bootstrap_from, library, merged)
    except OSError as error:
        raise _cannot_read(error, "during bootstrap") from error
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


def _check_citekeys(included: Mapping[str, tuple[Item, Path]], lock: Mapping[str, str]) -> None:
    """Refuse when an included item's citekey from the lock is not a safe citekey."""
    for item_id in sorted(included):
        problem = citekey_problem(lock[item_id])
        if problem is not None:
            raise ImportRefused(f"unsafe citekey {lock[item_id]!r} for item {item_id}: {problem}")


def pdf_destination(out_dir: Path, name: str) -> Path:
    """`out_dir/files/name`; ImportRefused if it resolves outside `out_dir/files`."""
    files = out_dir / FILES
    dest = files / name
    if not dest.resolve().is_relative_to(files.resolve()):
        raise ImportRefused(f"{dest}: PDF destination resolves outside {files}")
    return dest


def _write(out_dir: Path, plan: _Plan) -> None:
    """Write PDFs, the bibliography, the citekey lock and, last, the collection lock."""
    pdfs = [(pdf_destination(out_dir, name), src) for name, src in sorted(plan.pdfs.items())]
    for dest, src in pdfs:
        copy_pdf(src, dest)
    atomic_write(out_dir / BIBLIOGRAPHY, plan.bibliography)
    atomic_write(out_dir / CITEKEY_LOCK, format_citekey_lock(plan.citekey_lock))
    atomic_write(out_dir / COLLECTION_LOCK, format_collection_lock(plan.collection_lock))


def import_zotero(data_dir: Path, out_dir: Path, bootstrap_from: Path | None = None) -> RunSummary:
    """Run one import of the Zotero library in `data_dir` into the papers directory `out_dir`.

    Raises ImportRefused, UnknownSchema, BootstrapRefused or UnsafeCitekey before
    anything is written.
    """
    library, duplicates = _merged_library(data_dir)
    included, left_out = _split(library)
    lock, bootstrapped = _seed_lock(out_dir, library, bootstrap_from, set(duplicates.values()))
    collection_lock = _read_lock(out_dir / COLLECTION_LOCK, parse_collection_lock)
    lock, new_ids = assign_citekeys({i: key_stem(item) for i, (item, _) in included.items()}, lock)
    _check_citekeys(included, lock)
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
        duplicates=duplicates,
    )


def format_summary(summary: RunSummary) -> str:
    """The import run summary printed to stdout, one fact per line."""
    lines = [f"included: {summary.included}"]
    lines += [f"left out ({reason}): {len(ids)}" for reason, ids in summary.left_out.items()]
    lines += [f"duplicate {i} of {summary.duplicates[i]}" for i in sorted(summary.duplicates)]
    lines.append(f"new citekeys: {len(summary.new_citekeys)}")
    lines += summary.collection_changes
    unreferenced = f"unreferenced files: {len(summary.unreferenced)}"
    if summary.unreferenced:
        unreferenced += ": " + ", ".join(summary.unreferenced)
    lines.append(unreferenced)
    if summary.skipped_libraries:
        lines.append("skipped libraries: " + ", ".join(summary.skipped_libraries))
    if summary.bootstrap is not None:
        lines += _bootstrap_lines(summary.bootstrap)
    return "".join(f"{line}\n" for line in lines)


def _bootstrap_lines(result: BootstrapResult) -> list[str]:
    """The bootstrap counts, then one line per dropped citekey."""
    counts = (
        f"bootstrap: matched {len(result.lock)}, unmatched {len(result.unmatched)}, "
        f"ambiguous {len(result.ambiguous)}, not included {len(result.not_included)}, "
        f"dropped {len(result.dropped)}"
    )
    return [counts, *(f"dropped citekey: {citekey}" for citekey in sorted(result.dropped))]
