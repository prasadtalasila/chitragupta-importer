"""Import run refusals: each happens before the first write."""

import pytest
from run_fixture import RICHSTEIN, SMITH, build, existing_bibliography, snapshot

from chitragupta_importer.run import ImportRefused, import_zotero
from chitragupta_importer.sources.zotero import UnknownSchema


def test_bootstrap_with_existing_lock_refused(tmp_path):
    out = tmp_path / "out"
    data_dir = build(tmp_path, RICHSTEIN)
    import_zotero(data_dir, out)
    before = snapshot(out)
    with pytest.raises(ImportRefused, match="citekeys.lock"):
        import_zotero(data_dir, out, bootstrap_from=existing_bibliography(tmp_path))
    assert snapshot(out) == before


def test_unreadable_bootstrap_file_refused(tmp_path):
    data_dir, out = build(tmp_path, RICHSTEIN), tmp_path / "out"
    bad = tmp_path / "latin1.bib"
    bad.write_bytes(b"@article{k,\n  title = {Caf\xe9},\n}\n")
    with pytest.raises(ImportRefused, match="latin1.bib"):
        import_zotero(data_dir, out, bootstrap_from=bad)
    with pytest.raises(ImportRefused, match="absent.bib"):
        import_zotero(data_dir, out, bootstrap_from=tmp_path / "absent.bib")
    assert not out.exists()


@pytest.mark.parametrize("lock_name", ["citekeys.lock", "collections.lock"])
def test_malformed_lock_refused(tmp_path, lock_name):
    out = tmp_path / "out"
    out.mkdir()
    (out / lock_name).write_text("no tabs here\n", encoding="utf-8")
    before = snapshot(out)
    with pytest.raises(ImportRefused, match=lock_name):
        import_zotero(build(tmp_path, RICHSTEIN), out)
    assert snapshot(out) == before


def test_collection_lock_with_unknown_status_refused(tmp_path):
    out = tmp_path / "out"
    import_zotero(build(tmp_path / "v1", RICHSTEIN), out)
    lock = out / "collections.lock"
    lock.write_text(lock.read_text(encoding="utf-8").replace("\tlive\n", "\tactive\n"))
    before = snapshot(out)
    with pytest.raises(ImportRefused, match="collections.lock.*line 1: status 'active'"):
        import_zotero(build(tmp_path / "v2", RICHSTEIN, SMITH), out)
    assert snapshot(out) == before


def test_unreadable_item_pdf_during_bootstrap_names_the_pdf(tmp_path, monkeypatch):
    data_dir, out = build(tmp_path, RICHSTEIN), tmp_path / "out"
    pdf = next((data_dir / "storage").rglob("paper.pdf"))

    def refuse(path):
        raise PermissionError(13, "Permission denied", str(path))

    monkeypatch.setattr("chitragupta_importer.bootstrap._hash_file", refuse)
    with pytest.raises(ImportRefused) as refused:
        import_zotero(data_dir, out, bootstrap_from=existing_bibliography(tmp_path))
    assert str(pdf) in str(refused.value)
    assert "references.bib" not in str(refused.value)
    assert not out.exists()


def test_refusal_writes_nothing(tmp_path):
    out = tmp_path / "out"
    import_zotero(build(tmp_path / "v1", RICHSTEIN), out)
    before = snapshot(out)
    with pytest.raises(UnknownSchema):
        import_zotero(build(tmp_path / "v2", RICHSTEIN, SMITH, schema_version=999), out)
    assert snapshot(out) == before
