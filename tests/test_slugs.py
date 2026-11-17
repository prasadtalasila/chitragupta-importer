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


# A library: Digital Twin > DT Platforms > Execution; Digital Twin > Use Cases > Medical.
LIBRARY = [
    coll("DT", "Digital Twin"),
    coll("PLAT", "DT Platforms", "DT"),
    coll("EXEC", "Execution", "PLAT"),
    coll("USES", "Use Cases", "DT"),
    coll("MED", "Medical", "USES"),
]


SLUG_CASES = [
    ("Digital Twin", "digital-twin"),
    ("Industry 5.0", "industry-5-0"),
    ("Köhler & Co", "kohler-co"),
    ("Edge/Cloud", "edge-cloud"),
    ("***", "collection"),
]


@pytest.mark.parametrize("name,slug", SLUG_CASES)
def test_segment_slug(name, slug):
    assert segment_slug(name) == slug


def test_ancestors_of_used_collections_are_recorded():
    new, _ = update_collections({}, LIBRARY, {cid("EXEC")})
    assert set(new) == {cid("DT"), cid("PLAT"), cid("EXEC")}
    assert slug_paths(new)[cid("EXEC")] == "digital-twin.dt-platforms.execution"
    assert new[cid("PLAT")] == rec("PLAT", "dt-platforms", "DT Platforms", "DT")


def test_collection_holding_only_left_out_items_gets_no_record():
    new, changes = update_collections({}, LIBRARY, {cid("PLAT")})
    assert cid("EXEC") not in new and cid("MED") not in new
    assert changes == ["new digital-twin", "new digital-twin.dt-platforms"]


def test_used_collection_not_in_library_is_ignored_and_outside_parent_is_none():
    new, _ = update_collections({}, [coll("A", "Alpha", "MISSING")], {cid("A"), cid("GONE")})
    assert list(new) == [cid("A")] and new[cid("A")].parent_id is None


def test_rename_keeps_slug_and_reports():
    lock = lock_of(rec("B", "plants-dt", "Plants DT"))
    new, changes = update_collections(lock, [coll("B", "Plant Digital Twins")], set())
    assert new[cid("B")].slug == "plants-dt"
    assert new[cid("B")].name == "Plant Digital Twins"
    assert changes == ["renamed Plants DT -> Plant Digital Twins"]


def test_unchanged_lock_reports_nothing():
    lock, _ = update_collections({}, LIBRARY, {cid("EXEC"), cid("MED")})
    again, changes = update_collections(lock, LIBRARY, {cid("EXEC"), cid("MED")})
    assert again == lock and not changes


def test_move_keeps_segment_and_changes_path():
    lock = lock_of(
        rec("DT", "digital-twin", "Digital Twin"),
        rec("USES", "use-cases", "Use Cases", "DT"),
        rec("MED", "medical", "Medical", "USES"),
        rec("MED2", "medical", "Medical", "DT"),
    )
    library = LIBRARY + [coll("MED2", "Medical", "USES")]
    new, changes = update_collections(lock, library, set())
    assert new[cid("MED2")] == rec("MED2", "medical-1", "Medical", "USES")
    assert changes == ["moved digital-twin.medical -> digital-twin.use-cases.medical-1"]


def test_move_without_clash_keeps_segment():
    lock = lock_of(
        rec("DT", "digital-twin", "Digital Twin"),
        rec("USES", "use-cases", "Use Cases", "DT"),
        rec("MED", "medical", "Medical", "DT"),
    )
    new, changes = update_collections(lock, LIBRARY, set())
    assert new[cid("MED")].slug == "medical"
    assert changes == ["moved digital-twin.medical -> digital-twin.use-cases.medical"]


def test_rename_and_move_report_both():
    lock = lock_of(rec("DT", "digital-twin", "Digital Twin"), rec("X", "x", "X"))
    new, changes = update_collections(
        lock, [coll("DT", "Digital Twin"), coll("X", "Ex", "DT")], set()
    )
    assert new[cid("X")] == rec("X", "x", "Ex", "DT")
    assert lock[cid("X")] == rec("X", "x", "X")
    assert changes == ["moved x -> digital-twin.x", "renamed X -> Ex"]


def test_sibling_clash_including_case():
    library = [coll("P", "Parent"), coll("D2", "datasets", "P"), coll("D1", "Datasets", "P")]
    new, _ = update_collections({}, library, {cid("D1"), cid("D2")})
    assert new[cid("D1")].slug == "datasets" and new[cid("D2")].slug == "datasets-1"


def test_same_name_under_different_parents_does_not_clash():
    library = [
        coll("A", "A"),
        coll("B", "B"),
        coll("MA", "Medical", "A"),
        coll("MB", "Medical", "B"),
    ]
    new, _ = update_collections({}, library, {cid("MA"), cid("MB")})
    assert new[cid("MA")].slug == new[cid("MB")].slug == "medical"


def test_clash_skips_retired_sibling_slugs():
    lock = lock_of(rec("OLD", "datasets", "Old Data Sets", status="retired"))
    new, _ = update_collections(lock, [coll("NEW", "Datasets")], {cid("NEW")})
    assert new[cid("NEW")].slug == "datasets-1"


def test_gone_collection_is_retired_and_kept():
    lock = lock_of(rec("DT", "digital-twin", "Digital Twin"), rec("OLD", "old", "Old", "DT"))
    new, changes = update_collections(lock, [coll("DT", "Digital Twin")], set())
    assert new[cid("OLD")] == rec("OLD", "old", "Old", "DT", status="retired")
    assert changes == ["retired digital-twin.old"]
    assert cid("OLD") not in slug_paths(new)


def test_retired_record_stays_retired_without_report():
    lock = lock_of(rec("OLD", "old", "Old", status="retired"))
    new, changes = update_collections(lock, [], set())
    assert new == lock and not changes


def test_recreated_collection_takes_retired_slug():
    lock = lock_of(
        rec("DT", "digital-twin", "Digital Twin"),
        rec("OLD", "medical-1", "Medical", "DT", status="retired"),
        rec("MED", "medical", "Medical", "DT"),
    )
    library = [
        coll("DT", "Digital Twin"),
        coll("MED", "Medical", "DT"),
        coll("NEW", "Medical", "DT"),
    ]
    new, changes = update_collections(lock, library, {cid("NEW")})
    assert new[cid("NEW")] == rec("NEW", "medical-1", "Medical", "DT")
    assert new[cid("OLD")].status == "retired"
    assert changes == ["new digital-twin.medical-1"]


def test_recreated_collection_skips_retired_slug_held_by_live_sibling():
    lock = lock_of(
        rec("OLD", "medical", "Medical", status="retired"),
        rec("MOVED", "medical", "Medicine"),
    )
    library = [coll("MOVED", "Medicine"), coll("NEW", "Medical")]
    new, _ = update_collections(lock, library, {cid("NEW")})
    assert new[cid("NEW")].slug == "medical-1"


def test_returning_retired_collection_becomes_live():
    lock = lock_of(
        rec("OLD", "medical", "Medical", status="retired"),
        rec("NEW", "medical", "Medical"),
    )
    library = [coll("NEW", "Medical"), coll("OLD", "Medical")]
    new, changes = update_collections(lock, library, set())
    assert new[cid("OLD")] == rec("OLD", "medical-1", "Medical")
    assert changes == ["new medical-1"]


def test_new_collection_reported():
    lock, _ = update_collections({}, LIBRARY, {cid("DT")})
    _, changes = update_collections(lock, LIBRARY, {cid("PLAT")})
    assert changes == ["new digital-twin.dt-platforms"]


def test_ancestors_of_live_records_are_recorded_after_a_move():
    lock = lock_of(rec("EXEC", "execution", "Execution"))
    new, _ = update_collections(lock, LIBRARY, set())
    assert slug_paths(new)[cid("EXEC")] == "digital-twin.dt-platforms.execution"


def test_name_in_lock_has_no_tab_or_newline():
    new, _ = update_collections({}, [coll("A", "a\tb\nc\rd")], {cid("A")})
    assert new[cid("A")].name == "a b c d"
    again, changes = update_collections(new, [coll("A", "a\tb\nc\rd")], {cid("A")})
    assert again == new and not changes


def test_lock_round_trip():
    lock = lock_of(rec("DT", "digital-twin", "Digital Twin"))
    lock |= lock_of(rec("OLD", "old", "Old Things", "DT", status="retired"))
    text = format_collection_lock(lock)
    assert text == (
        "zotero:user/DT\t-\tdigital-twin\tDigital Twin\tlive\n"
        "zotero:user/OLD\tzotero:user/DT\told\tOld Things\tretired\n"
    )
    assert parse_collection_lock(text) == lock
    assert format_collection_lock({}) == "" and not parse_collection_lock("\n\n")


def test_format_replaces_tab_and_newline_in_name():
    text = format_collection_lock(lock_of(rec("A", "a", "x\ty\nz")))
    assert text == "zotero:user/A\t-\ta\tx y z\tlive\n"


def test_display_paths_join_names():
    new, _ = update_collections({}, LIBRARY, {cid("EXEC")})
    assert display_paths(new)[cid("EXEC")] == "Digital Twin / DT Platforms / Execution"


def test_name_table_rows_cover_used_and_ancestors_only():
    lock = lock_of(
        rec("DT", "digital-twin", "Digital Twin"),
        rec("PLAT", "dt-platforms", "DT Platforms", "DT"),
        rec("EXEC", "execution", "Execution", "PLAT"),
        rec("USES", "use-cases", "Use Cases", "DT"),
        rec("OLD", "old", "Old", "DT", status="retired"),
    )
    rows = name_table_rows(lock, {cid("PLAT"), cid("OLD")})
    assert rows == [("digital-twin", "Digital Twin"), ("digital-twin.dt-platforms", "DT Platforms")]
