"""Collections deleted in the same import run that re-creates or moves into their slug."""

from chitragupta_importer.model import Collection
from chitragupta_importer.slugs import CollectionRecord, update_collections


def cid(key):
    return f"zotero:user/{key}"


def test_recreation_in_same_run_takes_the_retiring_slug():
    lock = {
        cid("P"): CollectionRecord(cid("P"), None, "p", "P", "live"),
        cid("OLD"): CollectionRecord(cid("OLD"), cid("P"), "coral", "Coral", "live"),
    }
    library = [Collection(cid("P"), None, "P"), Collection(cid("NEW"), cid("P"), "Coral")]
    new, changes = update_collections(lock, library, {cid("NEW")})
    assert new[cid("NEW")].slug == "coral"
    assert new[cid("OLD")].status == "retired"
    assert changes == ["new p.coral", "retired p.coral"]


def test_move_in_same_run_into_a_vacated_slug_keeps_the_slug():
    lock = {
        cid("P"): CollectionRecord(cid("P"), None, "p", "P", "live"),
        cid("Q"): CollectionRecord(cid("Q"), None, "q", "Q", "live"),
        cid("A"): CollectionRecord(cid("A"), cid("P"), "x", "X", "live"),
        cid("B"): CollectionRecord(cid("B"), cid("Q"), "x", "X", "live"),
    }
    library = [
        Collection(cid("P"), None, "P"),
        Collection(cid("Q"), None, "Q"),
        Collection(cid("B"), cid("P"), "X"),
    ]
    new, changes = update_collections(lock, library, set())
    assert new[cid("B")].slug == "x"
    assert changes == ["moved q.x -> p.x", "retired p.x"]
