"""Check the importer against a real Zotero library and its existing bibliography.

Usage: check_zotero_data.py ZOTERO_DATA_DIR EXISTING_BIB OUT_DIR

Runs one import run with bootstrap from EXISTING_BIB into OUT_DIR (which must
be empty or absent) and prints aggregate numbers only:

- the bootstrap counts, dropped citekeys included;
- the number of duplicate items and of the groups they were merged into;
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
from collections import Counter
from pathlib import Path

from bibtexparser.bparser import BibTexParser

from chitragupta_importer.bootstrap import BootstrapRefused
from chitragupta_importer.citekeys import UnsafeCitekey, key_stem
from chitragupta_importer.run import BIBLIOGRAPHY, ImportRefused, import_zotero
from chitragupta_importer.sources.zotero import UnknownSchema, read_library

IGNORED = frozenset(["ID", "file", "groups", "cg-collections"])
_CLASH_SUFFIX = re.compile(r"-[0-9]+$")


def _entries(path: Path) -> dict[str, dict[str, str]]:
    parser = BibTexParser(common_strings=True, ignore_nonstandard_types=False)
    entries = parser.parse(path.read_text(encoding="utf-8")).entries
    return {entry["ID"]: entry for entry in entries}


def _value(name: str, value: str):
    if name == "keywords":
        return frozenset(k.strip() for k in value.split(",") if k.strip())
    return " ".join(value.split())


def field_differences(existing: dict, written: dict, citekeys) -> Counter:
    """Per field name, the number of citekeys whose two entries differ in that field."""
    differing: Counter = Counter()
    for citekey in citekeys:
        old, new = existing[citekey], written[citekey]
        for name in sorted((set(old) | set(new)) - IGNORED):
            if _value(name, old.get(name, "")) != _value(name, new.get(name, "")):
                differing[name] += 1
    return differing


def key_rule_matches(data_dir: Path, lock: dict[str, str]) -> int:
    """The number of frozen citekeys the key rule reproduces, clash suffix stripped."""
    items = {item.item_id: item for item in read_library(data_dir).items}
    return sum(
        key_stem(items[item_id]) == _CLASH_SUFFIX.sub("", citekey)
        for item_id, citekey in lock.items()
    )


def main(data_dir: Path, existing_bib: Path, out_dir: Path) -> None:
    if out_dir.exists() and any(out_dir.iterdir()):
        sys.exit(f"{out_dir} is not empty")
    try:
        summary = import_zotero(data_dir, out_dir, bootstrap_from=existing_bib)
    except (UnknownSchema, UnsafeCitekey, BootstrapRefused, ImportRefused) as error:
        sys.exit(f"import run refused: {error}")
    result = summary.bootstrap
    print(
        f"bootstrap: matched {len(result.lock)}, unmatched {len(result.unmatched)}, "
        f"ambiguous {len(result.ambiguous)}, not included {len(result.not_included)}, "
        f"dropped {len(result.dropped)}"
    )
    groups = len(set(summary.duplicates.values()))
    print(f"duplicates: {len(summary.duplicates)} items merged into {groups} groups")
    print(f"included {summary.included}, new citekeys {len(summary.new_citekeys)}")
    left_out = ", ".join(f"{reason} {len(ids)}" for reason, ids in summary.left_out.items())
    print(f"left out: {left_out or 'none'}")
    matches = key_rule_matches(data_dir, result.lock)
    total = len(result.lock)
    print(f"key rule: {matches} of {total} frozen citekeys ({100 * matches / total:.1f}%)")
    frozen = sorted(result.lock.values())
    differing = field_differences(_entries(existing_bib), _entries(out_dir / BIBLIOGRAPHY), frozen)
    print(f"field differences over {len(frozen)} frozen entries:")
    for name, count in sorted(differing.items(), key=lambda pair: (-pair[1], pair[0])):
        print(f"  {name:<12} {count}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*(Path(arg) for arg in sys.argv[1:]))
