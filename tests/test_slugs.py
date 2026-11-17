"""Segment slugs, slug paths and the collection lock."""

import pytest

from chitragupta_importer.model import Collection
from chitragupta_importer.slugs import (
    CollectionRecord,
    display_paths,
    format_collection_lock,
    name_table_rows,
    parse_collection_lock,
    segment_slug,
    slug_paths,
    update_collections,
)


def cid(key):
    return f"zotero:user/{key}"


def coll(key, name, parent=None):
    return Collection(cid(key), cid(parent) if parent else None, name)


def rec(key, slug, name, parent=None, status="live"):
    return CollectionRecord(cid(key), cid(parent) if parent else None, slug, name, status)


def lock_of(*records):
    return {r.collection_id: r for r in records}


# A library: Tide Pools > TP Gauges > Mooring; Tide Pools > Field Notes > Coral.
LIBRARY = [
    coll("BASIN", "Tide Pools"),
    coll("GAUGE", "TP Gauges", "BASIN"),
    coll("MOOR", "Mooring", "GAUGE"),
    coll("NOTES", "Field Notes", "BASIN"),
    coll("CORAL", "Coral", "NOTES"),
]


SLUG_CASES = [
    ("Tide Pools", "tide-pools"),
    ("Phase 2.0", "phase-2-0"),
    ("Köhler & Co", "kohler-co"),
    ("Ebb/Flow", "ebb-flow"),
    ("***", "collection"),
]


@pytest.mark.parametrize("name,slug", SLUG_CASES)
def test_segment_slug(name, slug):
    assert segment_slug(name) == slug


def test_ancestors_of_used_collections_are_recorded():
    new, _ = update_collections({}, LIBRARY, {cid("MOOR")})
    assert set(new) == {cid("BASIN"), cid("GAUGE"), cid("MOOR")}
    assert slug_paths(new)[cid("MOOR")] == "tide-pools.tp-gauges.mooring"
    assert new[cid("GAUGE")] == rec("GAUGE", "tp-gauges", "TP Gauges", "BASIN")


def test_collection_holding_only_left_out_items_gets_no_record():
    new, changes = update_collections({}, LIBRARY, {cid("GAUGE")})
    assert cid("MOOR") not in new and cid("CORAL") not in new
    assert changes == ["new tide-pools", "new tide-pools.tp-gauges"]


def test_used_collection_not_in_library_is_ignored_and_outside_parent_is_none():
    new, _ = update_collections({}, [coll("A", "Alpha", "MISSING")], {cid("A"), cid("GONE")})
    assert list(new) == [cid("A")] and new[cid("A")].parent_id is None


def test_rename_keeps_slug_and_reports():
    lock = lock_of(rec("B", "kelp-tp", "Kelp TP"))
    new, changes = update_collections(lock, [coll("B", "Kelp Tide Pools")], set())
    assert new[cid("B")].slug == "kelp-tp"
    assert new[cid("B")].name == "Kelp Tide Pools"
    assert changes == ["renamed Kelp TP -> Kelp Tide Pools"]


def test_unchanged_lock_reports_nothing():
    lock, _ = update_collections({}, LIBRARY, {cid("MOOR"), cid("CORAL")})
    again, changes = update_collections(lock, LIBRARY, {cid("MOOR"), cid("CORAL")})
    assert again == lock and not changes


def test_move_keeps_segment_and_changes_path():
    lock = lock_of(
        rec("BASIN", "tide-pools", "Tide Pools"),
        rec("NOTES", "field-notes", "Field Notes", "BASIN"),
        rec("CORAL", "coral", "Coral", "NOTES"),
        rec("CORAL2", "coral", "Coral", "BASIN"),
    )
    library = LIBRARY + [coll("CORAL2", "Coral", "NOTES")]
    new, changes = update_collections(lock, library, set())
    assert new[cid("CORAL2")] == rec("CORAL2", "coral-1", "Coral", "NOTES")
    assert changes == ["moved tide-pools.coral -> tide-pools.field-notes.coral-1"]


def test_move_without_clash_keeps_segment():
    lock = lock_of(
        rec("BASIN", "tide-pools", "Tide Pools"),
        rec("NOTES", "field-notes", "Field Notes", "BASIN"),
        rec("CORAL", "coral", "Coral", "BASIN"),
    )
    new, changes = update_collections(lock, LIBRARY, set())
    assert new[cid("CORAL")].slug == "coral"
    assert changes == ["moved tide-pools.coral -> tide-pools.field-notes.coral"]


def test_rename_and_move_report_both():
    lock = lock_of(rec("BASIN", "tide-pools", "Tide Pools"), rec("X", "x", "X"))
    new, changes = update_collections(
        lock, [coll("BASIN", "Tide Pools"), coll("X", "Ex", "BASIN")], set()
    )
    assert new[cid("X")] == rec("X", "x", "Ex", "BASIN")
    assert lock[cid("X")] == rec("X", "x", "X")
    assert changes == ["moved x -> tide-pools.x", "renamed X -> Ex"]


def test_sibling_clash_including_case():
    library = [coll("P", "Parent"), coll("D2", "logbooks", "P"), coll("D1", "Logbooks", "P")]
    new, _ = update_collections({}, library, {cid("D1"), cid("D2")})
    assert new[cid("D1")].slug == "logbooks" and new[cid("D2")].slug == "logbooks-1"


def test_same_name_under_different_parents_does_not_clash():
    library = [
        coll("A", "A"),
        coll("B", "B"),
        coll("MA", "Coral", "A"),
        coll("MB", "Coral", "B"),
    ]
    new, _ = update_collections({}, library, {cid("MA"), cid("MB")})
    assert new[cid("MA")].slug == new[cid("MB")].slug == "coral"


def test_clash_skips_retired_sibling_slugs():
    lock = lock_of(rec("OLD", "logbooks", "Old Log Sheets", status="retired"))
    new, _ = update_collections(lock, [coll("NEW", "Logbooks")], {cid("NEW")})
    assert new[cid("NEW")].slug == "logbooks-1"


def test_gone_collection_is_retired_and_kept():
    lock = lock_of(rec("BASIN", "tide-pools", "Tide Pools"), rec("OLD", "old", "Old", "BASIN"))
    new, changes = update_collections(lock, [coll("BASIN", "Tide Pools")], set())
    assert new[cid("OLD")] == rec("OLD", "old", "Old", "BASIN", status="retired")
    assert changes == ["retired tide-pools.old"]
    assert cid("OLD") not in slug_paths(new)


def test_retired_record_stays_retired_without_report():
    lock = lock_of(rec("OLD", "old", "Old", status="retired"))
    new, changes = update_collections(lock, [], set())
    assert new == lock and not changes


def test_recreated_collection_takes_retired_slug():
    lock = lock_of(
        rec("BASIN", "tide-pools", "Tide Pools"),
        rec("OLD", "coral-1", "Coral", "BASIN", status="retired"),
        rec("CORAL", "coral", "Coral", "BASIN"),
    )
    library = [
        coll("BASIN", "Tide Pools"),
        coll("CORAL", "Coral", "BASIN"),
        coll("NEW", "Coral", "BASIN"),
    ]
    new, changes = update_collections(lock, library, {cid("NEW")})
    assert new[cid("NEW")] == rec("NEW", "coral-1", "Coral", "BASIN")
    assert new[cid("OLD")].status == "retired"
    assert changes == ["new tide-pools.coral-1"]


def test_recreated_collection_skips_retired_slug_held_by_live_sibling():
    lock = lock_of(
        rec("OLD", "coral", "Coral", status="retired"),
        rec("MOVED", "coral", "Coral Reefs"),
    )
    library = [coll("MOVED", "Coral Reefs"), coll("NEW", "Coral")]
    new, _ = update_collections(lock, library, {cid("NEW")})
    assert new[cid("NEW")].slug == "coral-1"


def test_returning_retired_collection_becomes_live():
    lock = lock_of(
        rec("OLD", "coral", "Coral", status="retired"),
        rec("NEW", "coral", "Coral"),
    )
    library = [coll("NEW", "Coral"), coll("OLD", "Coral")]
    new, changes = update_collections(lock, library, set())
    assert new[cid("OLD")] == rec("OLD", "coral-1", "Coral")
    assert changes == ["new coral-1"]


def test_new_collection_reported():
    lock, _ = update_collections({}, LIBRARY, {cid("BASIN")})
    _, changes = update_collections(lock, LIBRARY, {cid("GAUGE")})
    assert changes == ["new tide-pools.tp-gauges"]


def test_ancestors_of_live_records_are_recorded_after_a_move():
    lock = lock_of(rec("MOOR", "mooring", "Mooring"))
    new, _ = update_collections(lock, LIBRARY, set())
    assert slug_paths(new)[cid("MOOR")] == "tide-pools.tp-gauges.mooring"


def test_name_in_lock_has_no_tab_or_newline():
    new, _ = update_collections({}, [coll("A", "a\tb\nc\rd")], {cid("A")})
    assert new[cid("A")].name == "a b c d"
    again, changes = update_collections(new, [coll("A", "a\tb\nc\rd")], {cid("A")})
    assert again == new and not changes


def test_lock_round_trip():
    lock = lock_of(rec("BASIN", "tide-pools", "Tide Pools"))
    lock |= lock_of(rec("OLD", "old", "Old Things", "BASIN", status="retired"))
    text = format_collection_lock(lock)
    assert text == (
        "zotero:user/BASIN\t-\ttide-pools\tTide Pools\tlive\n"
        "zotero:user/OLD\tzotero:user/BASIN\told\tOld Things\tretired\n"
    )
    assert parse_collection_lock(text) == lock
    assert format_collection_lock({}) == "" and not parse_collection_lock("\n\n")


def test_format_replaces_tab_and_newline_in_name():
    text = format_collection_lock(lock_of(rec("A", "a", "x\ty\nz")))
    assert text == "zotero:user/A\t-\ta\tx y z\tlive\n"


def test_display_paths_join_names():
    new, _ = update_collections({}, LIBRARY, {cid("MOOR")})
    assert display_paths(new)[cid("MOOR")] == "Tide Pools / TP Gauges / Mooring"


def test_name_table_rows_cover_used_and_ancestors_only():
    lock = lock_of(
        rec("BASIN", "tide-pools", "Tide Pools"),
        rec("GAUGE", "tp-gauges", "TP Gauges", "BASIN"),
        rec("MOOR", "mooring", "Mooring", "GAUGE"),
        rec("NOTES", "field-notes", "Field Notes", "BASIN"),
        rec("OLD", "old", "Old", "BASIN", status="retired"),
    )
    rows = name_table_rows(lock, {cid("GAUGE"), cid("OLD")})
    assert rows == [("tide-pools", "Tide Pools"), ("tide-pools.tp-gauges", "TP Gauges")]
