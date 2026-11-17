"""Shared inputs for the import run tests: a Zotero library builder and snapshots."""

from zotero_fixture import ZoteroFixture

OSTRANDER = {
    "key": "AAAA1111",
    "fields": {"title": "Calibrating the Digital Twin", "date": "2024"},
    "creators": [("Ostrander", "Ingrid", "author")],
    "pdfs": [("paper.pdf", b"%PDF-1")],
    "collections": ["COLL0001"],
}
SMITH = {
    "key": "BBBB2222",
    "fields": {"title": "Digital Platforms", "date": "2020"},
    "creators": [("Smith", "Jo", "author")],
    "pdfs": [("smith.pdf", b"%PDF-2")],
}

# Two copies of one paper: the same title up to case and a shared PDF.
OLDER = {**OSTRANDER, "date_added": "2019-01-01 00:00:00"}
NEWER = {
    **OSTRANDER,
    "key": "BBBB2222",
    "fields": {"title": "Calibrating the digital twin", "date": "2024"},
    "pdfs": [("copy.pdf", b"%PDF-1")],
    "date_added": "2020-01-01 00:00:00",
}


def build(root, *items, schema_version=121, collections=(("COLL0001", "Tide Pools"),)):
    """Build a Zotero data directory under `root` holding `items` (dicts of add_item kwargs)."""
    fixture = ZoteroFixture(root)
    for key, name in collections:
        fixture.add_collection(key, name)
    for spec in items:
        fixture.add_item(**spec)
    return fixture.build(schema_version)


def snapshot(directory):
    """Every file under `directory`, relative path -> bytes."""
    return {
        str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob("*") if p.is_file()
    }


def existing_bibliography(tmp_path):
    path = tmp_path / "existing" / "references.bib"
    path.parent.mkdir()
    path.write_text(
        "@article{io2024,\n  title = {Calibrating the digital twin},\n}\n"
        "@article{lost,\n  title = {Nowhere},\n}\n",
        encoding="utf-8",
    )
    return path
