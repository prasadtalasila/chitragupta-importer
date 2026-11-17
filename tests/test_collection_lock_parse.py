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


def test_self_parent_refused():
    with pytest.raises(ValueError, match="cycle.*zotero:user/A"):
        parse_collection_lock("zotero:user/A\tzotero:user/A\ta\tA\tlive\n")


def test_two_record_cycle_refused():
    text = (
        "zotero:user/A\tzotero:user/B\ta\tA\tlive\n"
        "zotero:user/B\tzotero:user/A\tb\tB\tretired\n"
        "zotero:user/C\tzotero:user/A\tc\tC\tlive\n"
    )
    with pytest.raises(
        ValueError, match="parent links form a cycle: zotero:user/A, zotero:user/B$"
    ):
        parse_collection_lock(text)


def test_parent_outside_the_lock_is_no_cycle():
    text = (
        GOOD
        + "zotero:user/B\tzotero:user/A\tb\tB\tlive\n"
        + "zotero:user/C\tzotero:user/X\tc\tC\tlive\n"
    )
    assert set(parse_collection_lock(text)) == {"zotero:user/A", "zotero:user/B", "zotero:user/C"}
