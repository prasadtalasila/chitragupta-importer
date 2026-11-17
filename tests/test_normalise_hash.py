"""PDF content hashes: read in chunks, each unchanged file once per import run."""

import os

import pytest
from run_fixture import OSTRANDER, build, existing_bibliography

from chitragupta_importer import normalise
from chitragupta_importer.run import import_zotero


@pytest.fixture(name="reads")
def counted_reads(monkeypatch):
    """The paths whose bytes `hash_file` reads, in order; the cache starts empty."""
    real = normalise.file_digest
    paths = []

    def counting(handle, digest):
        paths.append(handle.name)
        return real(handle, digest)

    monkeypatch.setattr(normalise, "file_digest", counting)
    normalise.clear_hash_cache()
    return paths


def test_unchanged_file_is_read_once(tmp_path, reads):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1")
    first = normalise.hash_file(pdf)
    assert normalise.hash_file(pdf) == first
    assert reads == [str(pdf)]


def test_changed_file_is_hashed_again(tmp_path, reads):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF-1")
    first = normalise.hash_file(pdf)
    pdf.write_bytes(b"%PDF-2")
    os.utime(pdf, ns=(1, 1))
    second = normalise.hash_file(pdf)
    pdf.write_bytes(b"%PDF-22")
    os.utime(pdf, ns=(1, 1))
    assert len({first, second, normalise.hash_file(pdf)}) == 3
    assert reads == [str(pdf)] * 3


def test_bootstrap_run_reads_each_pdf_once(tmp_path, reads):
    data_dir, existing = build(tmp_path, OSTRANDER), existing_bibliography(tmp_path)
    import_zotero(data_dir, tmp_path / "out", existing)
    assert len(reads) == 1
    import_zotero(data_dir, tmp_path / "out2", existing)
    assert len(reads) == 2
