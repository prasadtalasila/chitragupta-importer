"""The import run: read a Zotero library and write the papers directory.

Everything that can refuse happens before the first write, so a refused import
run leaves the output directory as it was.
"""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

from chitragupta_importer import normalise
from chitragupta_importer.bibtex import render_bibliography, render_entry, render_name_table
from chitragupta_importer.citekeys import (
    assign_citekeys,
    citekey_problem,
    format_citekey_lock,
    key_stem,
)
from chitragupta_importer.inputs import (
    DuplicatesFound,
    ImportRefused,
    check_bootstrap,
    merged_library,
    read_lock,
    seed_lock,
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
from chitragupta_importer.summary import RunSummary, format_summary
from chitragupta_importer.write import atomic_write, copy_pdf, unreferenced_files

BIBLIOGRAPHY = "bibliography.bib"
CITEKEY_LOCK = "citekeys.lock"
COLLECTION_LOCK = "collections.lock"
FILES = "files"

__all__ = [
    "DuplicatesFound",
    "ImportRefused",
    "Plan",
    "RunSummary",
    "WriteFailed",
    "format_summary",
    "import_zotero",
    "pdf_destination",
    "plan_import",
]


class WriteFailed(Exception):
    """An import run that failed while writing; the papers directory may be partly written."""


@dataclass(frozen=True)
class Plan:
    """Everything an import run writes, worked out before the first write.

    `pdfs` maps each PDF's destination to the main PDF it copies.
    """

    pdfs: dict[Path, Path]
    bibliography: str
    citekey_lock: dict[str, str]
    collection_lock: dict[str, CollectionRecord]


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
    return render_bibliography([name_table], entries)


def _check_citekeys(included: Mapping[str, tuple[Item, Path]], lock: Mapping[str, str]) -> None:
    """Refuse when an included item's citekey from the lock is not a safe citekey."""
    for item_id in sorted(included):
        problem = citekey_problem(lock[item_id])
        if problem is not None:
            raise ImportRefused(f"unsafe citekey {lock[item_id]!r} for item {item_id}: {problem}")


def _check_readable(included: Mapping[str, tuple[Item, Path]]) -> None:
    """Refuse when an included item's main PDF cannot be opened for reading."""
    for item_id, (_, pdf) in sorted(included.items()):
        try:
            with pdf.open("rb"):
                pass
        except OSError as error:
            raise ImportRefused(
                f"{pdf}: cannot read the main PDF of item {item_id} ({error.strerror})"
            ) from error


def pdf_destination(out_dir: Path, name: str) -> Path:
    """`out_dir/files/name`; ImportRefused if it resolves outside `out_dir/files`."""
    files = out_dir / FILES
    dest = files / name
    if not dest.resolve().is_relative_to(files.resolve()):
        raise ImportRefused(f"{dest}: PDF destination resolves outside {files}")
    return dest


def _write(out_dir: Path, plan: Plan) -> None:
    """Write PDFs, the bibliography, the citekey lock and, last, the collection lock."""
    for dest, src in sorted(plan.pdfs.items()):
        copy_pdf(src, dest)
    atomic_write(out_dir / BIBLIOGRAPHY, plan.bibliography)
    atomic_write(out_dir / CITEKEY_LOCK, format_citekey_lock(plan.citekey_lock))
    atomic_write(out_dir / COLLECTION_LOCK, format_collection_lock(plan.collection_lock))


def _plan(out_dir: Path, library: Library, lock: dict[str, str]) -> tuple[Plan, RunSummary]:
    """The plan and summary for the merged `library`, starting from the citekey `lock`."""
    included, left_out = _split(library)
    _check_readable(included)
    collection_lock = read_lock(out_dir / COLLECTION_LOCK, parse_collection_lock)
    lock, new_ids = assign_citekeys({i: key_stem(item) for i, (item, _) in included.items()}, lock)
    _check_citekeys(included, lock)
    used = {c for item, _ in included.values() for c in item.collection_ids}
    records, changes = update_collections(collection_lock, library.collections, used)
    pdfs = {pdf_destination(out_dir, f"{lock[i]}.pdf"): pdf for i, (_, pdf) in included.items()}
    plan = Plan(pdfs, _render(included, lock, records, used), lock, records)
    return plan, RunSummary(
        included=len(included),
        left_out=left_out,
        new_citekeys=tuple(lock[item_id] for item_id in new_ids),
        collection_changes=tuple(changes),
        unreferenced=tuple(unreferenced_files(out_dir / FILES, {p.name for p in pdfs})),
        skipped_libraries=library.skipped_libraries,
        bootstrap=None,
    )


def plan_import(
    data_dir: Path, out_dir: Path, bootstrap_from: Path | None = None, merge: bool = False
) -> tuple[Plan, RunSummary]:
    """Everything an import run would write into `out_dir`, and its summary; writes nothing.

    Raises ImportRefused (DuplicatesFound included), UnknownSchema,
    UnreadableLibrary, BootstrapRefused or UnsafeCitekey.
    """
    normalise.clear_hash_cache()
    check_bootstrap(out_dir / CITEKEY_LOCK, bootstrap_from)
    library, duplicates, survivor_pdfs = merged_library(data_dir, bootstrap_from, merge)
    lock, bootstrapped = seed_lock(out_dir / CITEKEY_LOCK, library, bootstrap_from, survivor_pdfs)
    plan, summary = _plan(out_dir, library, lock)
    return plan, replace(summary, bootstrap=bootstrapped, duplicates=duplicates)


def import_zotero(
    data_dir: Path,
    out_dir: Path,
    bootstrap_from: Path | None = None,
    *,
    merge_duplicates: bool = False,
    dry_run: bool = False,
) -> RunSummary:
    """Run one import of the Zotero library in `data_dir` into the papers directory `out_dir`.

    Duplicate groups refuse the import run unless `merge_duplicates`. A
    `dry_run` writes and creates nothing but refuses as a real run would.
    Raises what `plan_import` raises, before anything is written, and
    WriteFailed when writing fails part way.
    """
    plan, summary = plan_import(data_dir, out_dir, bootstrap_from, merge_duplicates)
    if dry_run:
        return replace(summary, dry_run=True)
    try:
        _write(out_dir, plan)
    except OSError as error:
        raise WriteFailed(
            f"{error.filename or out_dir}: cannot write the papers directory"
            f" ({error.strerror or error})"
        ) from error
    return summary
