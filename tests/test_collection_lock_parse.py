"""Refusing a malformed collection lock."""

import pytest

from chitragupta_importer.slugs import parse_collection_lock

GOOD = "zotero:user/A\t-\ta\tA\tlive\n"


@pytest.mark.parametrize("status", ["gone", "Live", ""])
def test_unknown_status_refused(status):
    with pytest.raises(ValueError, match=f"line 2: status '{status}'"):
        parse_collection_lock(f"{GOOD}zotero:user/B\t-\tb\tB\t{status}\n")


@pytest.mark.parametrize(
    "bad_line", ["zotero:user/B\t-\tb\tB", "zotero:user/B\t-\tb\tB\tlive\textra", "no tabs"]
)
def test_wrong_field_count_refused(bad_line):
    with pytest.raises(ValueError, match="line 3: expected 5 tab-separated fields"):
        parse_collection_lock(GOOD + "\n" + bad_line + "\n")


def test_retired_status_accepted():
    lock = parse_collection_lock("zotero:user/B\t-\tb\tB\tretired\n")
    assert lock["zotero:user/B"].status == "retired"
