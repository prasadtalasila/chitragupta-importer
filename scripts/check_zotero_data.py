"""Check the importer against a real Zotero library and its existing bibliography.

Usage: check_zotero_data.py [--merge-duplicates] ZOTERO_DATA_DIR EXISTING_BIB

Runs one import run with bootstrap from EXISTING_BIB as a dry run into a new,
empty papers directory, writing nothing, and prints aggregate numbers only.
Without --merge-duplicates, a library with duplicate groups prints how many
groups were found (not the groups) and exits nonzero. Otherwise it prints:

- the bootstrap counts, dropped citekeys included;
- the number of duplicate items and of the groups they were merged into;
- the number of citekey renames;
- the key-rule match rate: how many frozen citekeys, with any clash suffix
  stripped, equal the key stem the key rule gives their item;
- per field name, how many frozen entries differ between EXISTING_BIB and the
  written bibliography, ignoring `file`, `groups` and `cg-collections`.
  Values are compared with runs of whitespace collapsed; `keywords` is
  compared as a set, since tags are written sorted by design.

Not run in CI: the Zotero data is private.
"""

import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

from bibtexparser.bparser import BibTexParser

from chitragupta_importer.bootstrap import BootstrapRefused
from chitragupta_importer.citekeys import UnsafeCitekey, export_stem
from chitragupta_importer.run import DuplicatesFound, ImportRefused, plan_import
from chitragupta_importer.sources.zotero import UnknownSchema, UnreadableLibrary, read_library

IGNORED = frozenset(["ID", "file", "groups", "cg-collections"])
_CLASH_SUFFIX = re.compile(r"-[0-9]+$")


def _entries(source: Path | str) -> dict[str, dict[str, str]]:
    """The entries of a bibliography file or text, by citekey."""
    text = source.read_text(encoding="utf-8") if isinstance(source, Path) else source
    parser = BibTexParser(common_strings=True, ignore_nonstandard_types=False)
    entries = parser.parse(text).entries
    return {entry["ID"]: entry for entry in entries}


def _value(name: str, value: str):
    if name == "keywords":
        return frozenset(k.strip() for k in value.split(",") if k.strip())
    return " ".join(value.split())


def field_differences(existing: dict, written: dict, pairs) -> Counter:
    """Per field name, how many `(frozen, written)` citekey pairs' entries differ in it.

    The written citekey differs from the frozen one when the frozen one was renamed.
    """
    differing: Counter = Counter()
    for frozen, current in pairs:
        old, new = existing[frozen], written[current]
        for name in sorted((set(old) | set(new)) - IGNORED):
            if _value(name, old.get(name, "")) != _value(name, new.get(name, "")):
                differing[name] += 1
    return differing


def key_rule_matches(data_dir: Path, lock: dict[str, str]) -> int:
    """The number of frozen citekeys the key rule reproduces, clash suffix stripped."""
    items = {item.item_id: item for item in read_library(data_dir).items}
    return sum(
        export_stem(items[item_id]) == _CLASH_SUFFIX.sub("", citekey)
        for item_id, citekey in lock.items()
    )


def main(data_dir: Path, existing_bib: Path, merge: bool) -> None:
    with tempfile.TemporaryDirectory() as scratch:
        try:
            plan, summary = plan_import(data_dir, Path(scratch) / "papers", existing_bib, merge)
        except DuplicatesFound as error:
            sys.exit(f"import run refused: {len(error.groups)} duplicate groups found")
        except (
            UnknownSchema,
            UnreadableLibrary,
            UnsafeCitekey,
            BootstrapRefused,
            ImportRefused,
        ) as error:
            sys.exit(f"import run refused: {error}")
    result = summary.bootstrap
    print(
        f"bootstrap: matched {result.matched}, unmatched {len(result.unmatched)}, "
        f"ambiguous {len(result.ambiguous)}, not included {len(result.not_included)}, "
        f"dropped {len(result.dropped)}"
    )
    groups = len(set(summary.duplicates.values()))
    print(f"duplicates: {len(summary.duplicates)} items merged into {groups} groups")
    print(f"citekey renames: {len(summary.renames)}")
    print(f"included {summary.included}, new citekeys {len(summary.new_citekeys)}")
    left_out = ", ".join(f"{reason} {len(ids)}" for reason, ids in summary.left_out.items())
    print(f"left out: {left_out or 'none'}")
    dormant = set(result.not_included)
    lock = {item_id: key for item_id, key in result.lock.items() if key not in dormant}
    matches = key_rule_matches(data_dir, lock)
    total = len(lock)
    print(f"key rule: {matches} of {total} frozen citekeys ({100 * matches / total:.1f}%)")
    pairs = sorted((key, plan.citekey_lock[item_id]) for item_id, key in lock.items())
    differing = field_differences(_entries(existing_bib), _entries(plan.bibliography), pairs)
    print(f"field differences over {len(pairs)} frozen entries:")
    for name, count in sorted(differing.items(), key=lambda pair: (-pair[1], pair[0])):
        print(f"  {name:<12} {count}")


if __name__ == "__main__":
    args = sys.argv[1:]
    merge_flag = "--merge-duplicates" in args
    paths = [arg for arg in args if arg != "--merge-duplicates"]
    if len(paths) != 2 or len(args) - len(paths) > 1:
        sys.exit(__doc__)
    main(Path(paths[0]), Path(paths[1]), merge_flag)
