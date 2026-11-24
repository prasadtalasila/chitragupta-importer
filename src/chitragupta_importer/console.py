"""The import run summary and refusals rendered with rich for the terminal.

Off a terminal (a pipe, a file, a test runner) rich writes plain text
without ANSI codes. `summary.format_summary` stays the plain-text form.
"""

from rich import box
from rich.console import Console
from rich.table import Table

from chitragupta_importer.summary import RunSummary


def _counts(summary: RunSummary) -> Table:
    """The counts table: included, left out by reason, new citekeys and the rest."""
    table = Table(box=box.SIMPLE, show_header=False, title="Import run")
    table.add_column("what")
    table.add_column("count", justify="right")
    table.add_row("included", str(summary.included))
    for reason, item_ids in summary.left_out.items():
        table.add_row(f"left out ({reason})", str(len(item_ids)))
    table.add_row("new citekeys", str(len(summary.new_citekeys)))
    table.add_row("duplicates", str(len(summary.duplicates)))
    result = summary.bootstrap
    if result is not None:
        table.add_row("bootstrap: matched", str(result.matched))
        table.add_row("bootstrap: unmatched", str(len(result.unmatched)))
        table.add_row("bootstrap: ambiguous", str(len(result.ambiguous)))
        table.add_row("bootstrap: not included", str(len(result.not_included)))
        table.add_row("dropped citekeys", str(len(result.dropped)))
    table.add_row("citekey renames", str(len(summary.renames)))
    table.add_row("unreferenced files", str(len(summary.unreferenced)))
    return table


def _detail_lines(summary: RunSummary) -> list[str]:
    """One line per collection change, duplicate, dropped or renamed citekey, file and library."""
    lines = list(summary.collection_changes)
    lines += [f"duplicate {i} of {summary.duplicates[i]}" for i in sorted(summary.duplicates)]
    if summary.bootstrap is not None:
        lines += [f"dropped citekey: {citekey}" for citekey in sorted(summary.bootstrap.dropped)]
    lines += [f"renamed citekey: {old} -> {new}" for old, new in summary.renames]
    lines += [f"unreferenced file: {name}" for name in summary.unreferenced]
    lines += [f"skipped library: {library}" for library in summary.skipped_libraries]
    return lines


def print_summary(summary: RunSummary, console: Console) -> None:
    """Print the import run summary: a counts table, then one line per change."""
    if summary.dry_run:
        console.print("dry run: nothing written", style="bold yellow", soft_wrap=True)
    console.print(_counts(summary))
    for line in _detail_lines(summary):
        console.print(line, markup=False, highlight=False, soft_wrap=True)


def print_error(message: str, console: Console) -> None:
    """Print `Error: ` and the message's first line, then each further problem on its own line."""
    first, *problems = message.splitlines()
    console.print(f"Error: {first}", style="bold red", markup=False, soft_wrap=True)
    for problem in problems:
        console.print(f"  {problem}", style="red", markup=False, highlight=False, soft_wrap=True)
