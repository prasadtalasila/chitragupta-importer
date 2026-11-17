"""The input of an import run: the library, merged or refused, and the locks to start from.

Everything here only reads; each refusal is an ImportRefused.
"""

from collections.abc import Mapping, Sequence, Set
from pathlib import Path

from chitragupta_importer.bootstrap import BootstrapResult, bootstrap, url_tie_groups
from chitragupta_importer.citekeys import DROPPED_PREFIX, parse_citekey_lock
from chitragupta_importer.duplicates import duplicate_groups, merge_duplicates, pdf_then_oldest
from chitragupta_importer.model import Library
from chitragupta_importer.normalise import item_pdf_hashes
from chitragupta_importer.sources.zotero import read_library


class ImportRefused(Exception):
    """An import run that cannot go ahead; nothing has been written."""


class DuplicatesFound(ImportRefused):
    """Duplicate groups in an import run without --merge-duplicates; each is listed."""

    def __init__(self, groups: Sequence[Sequence[str]], library: Library) -> None:
        titles = {item.item_id: item.fields.get("title", "") for item in library.items}
        lines = [
            f"{len(groups)} duplicate groups found; rerun with --merge-duplicates to merge them"
        ]
        lines += [
            "duplicate group: " + ", ".join(f"{item_id} ({titles[item_id]})" for item_id in group)
            for group in groups
        ]
        super().__init__("\n".join(lines))
        self.groups = tuple(tuple(group) for group in groups)


def read_lock(path: Path, parse):
    """Parse the lock file at `path`, or return an empty lock when there is none."""
    if not path.exists():
        return {}
    try:
        return parse(path.read_text(encoding="utf-8"))
    except ValueError as error:  # UnicodeDecodeError included
        raise ImportRefused(f"{path}: malformed lock file ({error})") from error
    except OSError as error:
        raise ImportRefused(f"{path}: cannot read the lock file ({error.strerror})") from error


def _cannot_read(error: OSError, stage: str) -> ImportRefused:
    """The refusal for an `error` while reading item files `stage` (e.g. "during bootstrap")."""
    if error.filename is None:
        return ImportRefused(f"cannot read {stage}: {error}")
    return ImportRefused(f"{error.filename}: cannot read {stage} ({error.strerror})")


def check_bootstrap(lock_path: Path, bootstrap_from: Path | None) -> None:
    """Refuse a bootstrap into an existing citekey lock or from an unreadable file."""
    if bootstrap_from is None:
        return
    if lock_path.exists():
        raise ImportRefused(f"{lock_path} exists: bootstrap needs a new citekey lock")
    try:
        bootstrap_from.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ImportRefused(f"{bootstrap_from}: cannot read the bibliography ({error})") from error


def merged_library(
    data_dir: Path, bootstrap_from: Path | None, merge: bool
) -> tuple[Library, dict[str, str], dict[str, set[str]]]:
    """The library with each duplicate group merged into its survivor.

    Also returns each non-survivor's survivor and each survivor's own PDF
    hashes. Without `merge`, any duplicate group refuses the import run.
    """
    library = read_library(data_dir)
    try:
        extra = [] if bootstrap_from is None else url_tie_groups(bootstrap_from, library)
    except OSError as error:
        raise _cannot_read(error, "during bootstrap") from error
    try:
        groups = duplicate_groups(library, extra)
        if groups and not merge:
            raise DuplicatesFound(groups, library)
        merged, duplicates = merge_duplicates(library, pdf_then_oldest, extra)
        items = {item.item_id: item for item in library.items}
        pdfs = {kept: item_pdf_hashes(items[kept]) for kept in set(duplicates.values())}
    except OSError as error:
        raise _cannot_read(error, "while merging duplicate items") from error
    return merged, duplicates, pdfs


def seed_lock(
    lock_path: Path,
    library: Library,
    bootstrap_from: Path | None,
    survivor_pdfs: Mapping[str, Set[str]],
) -> tuple[dict[str, str], BootstrapResult | None]:
    """The citekey lock to start from, and the bootstrap result when bootstrapping.

    A bootstrap reserves each dropped citekey under `dropped:<citekey>`.
    """
    if bootstrap_from is None:
        return read_lock(lock_path, parse_citekey_lock), None
    try:
        result = bootstrap(bootstrap_from, library, survivor_pdfs)
    except OSError as error:
        raise _cannot_read(error, "during bootstrap") from error
    reserved = {f"{DROPPED_PREFIX}{citekey}": citekey for citekey in result.dropped}
    return {**result.lock, **reserved}, result
