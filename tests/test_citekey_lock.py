"""The citekey lock and key assignment."""

import pytest

from chitragupta_importer.citekeys import (
    UnsafeCitekey,
    assign_citekeys,
    format_citekey_lock,
    parse_citekey_lock,
)


def test_known_item_keeps_key():
    lock, new = assign_citekeys({"z:1": "smith_x_2020"}, {"z:1": "old_key_1999"})
    assert lock == {"z:1": "old_key_1999"} and not new


def test_new_item_gets_stem():
    lock, new = assign_citekeys({"z:1": "smith_x_2020"}, {})
    assert lock == {"z:1": "smith_x_2020"} and new == ["z:1"]


def test_clash_in_one_run_by_item_id_order():
    lock, new = assign_citekeys({"z:2": "a_b_2020", "z:1": "a_b_2020", "z:3": "a_b_2020"}, {})
    assert lock == {"z:1": "a_b_2020", "z:2": "a_b_2020-1", "z:3": "a_b_2020-2"}
    assert new == ["z:1", "z:2", "z:3"]


def test_clash_skips_spellings_in_lock_including_dormant_and_retired():
    lock, _ = assign_citekeys({"z:9": "a_b_2020"}, {"z:1": "a_b_2020", "z:2": "a_b_2020-1"})
    assert lock["z:9"] == "a_b_2020-2"


def test_clash_skips_suffixed_spelling_assigned_earlier_in_run():
    lock, _ = assign_citekeys({"z:1": "a_b_2020-1", "z:2": "a_b_2020", "z:3": "a_b_2020"}, {})
    assert lock == {"z:1": "a_b_2020-1", "z:2": "a_b_2020", "z:3": "a_b_2020-2"}


def test_known_item_key_is_not_rechecked():
    lock, new = assign_citekeys({"z:1": "a_b_2020"}, {"z:1": "con"})
    assert lock == {"z:1": "con"} and not new


def test_lines_never_removed():
    lock, _ = assign_citekeys({"z:2": "a_b_2020"}, {"z:1": "old_key_1999"})
    assert lock == {"z:1": "old_key_1999", "z:2": "a_b_2020"}


def test_input_lock_is_not_changed():
    given = {"z:1": "old_key_1999"}
    assign_citekeys({"z:2": "a_b_2020"}, given)
    assert given == {"z:1": "old_key_1999"}


def test_unsafe_new_key_raises():
    with pytest.raises(UnsafeCitekey, match=r"z:1.*reserved Windows device name"):
        assign_citekeys({"z:1": "con"}, {})


def test_lock_round_trip():
    m = {"zotero:user/B": "b_x_2021", "zotero:user/A": "a_y_2020-1"}
    assert parse_citekey_lock(format_citekey_lock(m)) == m


def test_lock_text_is_sorted_tab_lf():
    text = format_citekey_lock({"zotero:user/B": "b_x_2021", "zotero:user/A": "a_y_2020"})
    assert text == "zotero:user/A\ta_y_2020\nzotero:user/B\tb_x_2021\n"


def test_empty_lock_is_empty_text():
    assert format_citekey_lock({}) == "" and not parse_citekey_lock("")


def test_parse_ignores_blank_lines():
    assert parse_citekey_lock("\nz:1\tk1\n\n  \nz:2\tk2\n") == {"z:1": "k1", "z:2": "k2"}


def test_parse_refuses_a_citekey_held_by_two_item_ids():
    text = "zotero:user/A\tk\nzotero:user/B\tother\nzotero:user/C\tk\n"
    with pytest.raises(ValueError, match="line 3: citekey 'k' is held by both zotero:user/A and"):
        parse_citekey_lock(text)


def test_parse_accepts_dropped_lines():
    text = "dropped:a:b\ta:b\ndropped:k-1\tk-1\nzotero:user/A\tk\n"
    lock = parse_citekey_lock(text)
    assert lock == {"dropped:a:b": "a:b", "dropped:k-1": "k-1", "zotero:user/A": "k"}
    assert format_citekey_lock(lock) == text
