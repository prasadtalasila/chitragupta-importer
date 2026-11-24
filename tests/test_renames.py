"""The rename lock, chain resolution and the cg-renames block."""

import pytest

from chitragupta_importer.model import Item, Library
from chitragupta_importer.renames import (
    add_renames,
    block_rows,
    format_renames_lock,
    merge_renames,
    parse_renames_lock,
    render_renames_block,
    zotero_merge_renames,
)


def test_lock_round_trip_sorted_by_old_key():
    assert parse_renames_lock("b\tc\n\na\tc\n") == {"a": "c", "b": "c"}
    assert format_renames_lock({"b": "c", "a": "c"}) == "a\tc\nb\tc\n"


@pytest.mark.parametrize("text", ["a c\n", "a\tb\na\tc\n"])
def test_malformed_lock_is_a_value_error(text):
    with pytest.raises(ValueError):
        parse_renames_lock(text)


def test_first_row_for_an_old_key_wins_and_self_rows_are_skipped():
    lock, added = add_renames({"a": "b"}, [("a", "z"), ("c", "c"), ("d", "b")])
    assert lock == {"a": "b", "d": "b"} and added == [("d", "b")]


def test_chains_collapse_to_the_last_successor():
    assert block_rows({"a": "b", "b": "c"}, {"c"}, {"c"}) == [("a", "c"), ("b", "c")]


def test_row_needs_successor_in_bibliography_and_old_key_out_of_it():
    assert block_rows({"a": "b", "x": "y"}, {"b", "x", "y"}, {"b", "x", "y"}) == [("a", "b")]


def test_dormant_successor_gives_no_row():
    assert not block_rows({"a": "b"}, set(), {"b"})


def test_unsafe_key_gives_no_row():
    assert not block_rows({"con": "b", "a:b": "b"}, {"b"}, {"b"})


def test_a_loop_gives_no_row():
    assert not block_rows({"a": "b", "b": "a"}, {"c"}, {"c"})


def test_block_text():
    assert render_renames_block([("a", "c"), ("b", "c")]) == (
        "@comment{cg-renames v1\na\tc\nb\tc\n}\n"
    )
    assert render_renames_block([]) == ""


def test_merge_rename_needs_both_items_in_the_lock():
    lock = {"z:1": "old", "z:2": "new"}
    assert merge_renames({"z:1": "z:2", "z:3": "z:2"}, lock) == [("old", "new")]


def _item(item_id, replaces=()):
    return Item(item_id, "journalArticle", {}, (), (), (), (), replaces=replaces)


def test_zotero_merge_rename_for_a_retired_line_only():
    library = Library((_item("z:2", replaces=("z:1", "z:3")), _item("z:3")), (), ())
    lock = {"z:1": "old", "z:2": "new", "z:3": "k3"}
    assert zotero_merge_renames(library, lock) == [("old", "new")]


def test_zotero_merge_rename_needs_the_replacing_item_in_the_lock():
    library = Library((_item("z:2", replaces=("z:1",)),), (), ())
    assert not zotero_merge_renames(library, {"z:1": "old"})


def test_chain_stops_at_a_live_key():
    renames = {"x": "g", "g": "r"}
    assert block_rows(renames, {"g", "r"}, {"g", "r"}) == [("x", "g")]


def test_live_dormant_old_key_gives_no_row():
    assert not block_rows({"g": "r"}, {"r"}, {"g", "r"})
