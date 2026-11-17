"""The import run summary and the text printed for it."""

from collections.abc import Mapping
from dataclasses import dataclass, field

from chitragupta_importer.bootstrap import BootstrapResult


@dataclass(frozen=True)
class RunSummary:  # pylint: disable=too-many-instance-attributes
    """What an import run did, or with `dry_run` would have done.

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
    dry_run: bool = False


def format_summary(summary: RunSummary) -> str:
    """The import run summary printed to stdout, one fact per line."""
    lines = ["dry run: nothing written"] if summary.dry_run else []
    lines.append(f"included: {summary.included}")
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
