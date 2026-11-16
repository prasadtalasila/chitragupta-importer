"""Writing the papers directory: atomic text writes, PDF copies, stray files."""

import os

import pytest

from chitragupta_importer import write
from chitragupta_importer.write import atomic_write, copy_pdf, unreferenced_files


def test_atomic_write_creates_parents_and_replaces(tmp_path):
    target = tmp_path / "papers" / "bibliography.bib"
    atomic_write(target, "first\n")
    assert target.read_text(encoding="utf-8") == "first\n"
    atomic_write(target, "second\n")
    assert target.read_text(encoding="utf-8") == "second\n"
    assert os.listdir(target.parent) == ["bibliography.bib"]


def test_atomic_write_leaves_old_file_on_failure(tmp_path, monkeypatch):
    target = tmp_path / "bibliography.bib"
    target.write_text("old\n", encoding="utf-8")

    def failing_replace(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(write.os, "replace", failing_replace)
    with pytest.raises(OSError, match="disk full"):
        atomic_write(target, "new\n")
    assert target.read_text(encoding="utf-8") == "old\n"
    assert os.listdir(tmp_path) == ["bibliography.bib"]


def test_atomic_write_is_utf8_lf(tmp_path):
    target = tmp_path / "citekeys.lock"
    atomic_write(target, "ä\n")
    assert target.read_bytes() == b"\xc3\xa4\n"


def test_copy_pdf_skips_identical(tmp_path):
    src = tmp_path / "storage" / "paper.pdf"
    src.parent.mkdir()
    src.write_bytes(b"%PDF-1.4\nsame\n")
    dest = tmp_path / "papers" / "files" / "smith2020.pdf"
    assert copy_pdf(src, dest) is True
    os.utime(dest, ns=(1_000_000_000, 1_000_000_000))
    assert copy_pdf(src, dest) is False
    assert dest.stat().st_mtime_ns == 1_000_000_000
    assert src.read_bytes() == b"%PDF-1.4\nsame\n"


def test_copy_pdf_replaces_changed(tmp_path):
    src = tmp_path / "paper.pdf"
    src.write_bytes(b"%PDF-1.4\nnew\n")
    dest = tmp_path / "files" / "smith2020.pdf"
    dest.parent.mkdir()
    dest.write_bytes(b"%PDF-1.4\nolder version\n")
    assert copy_pdf(src, dest) is True
    assert dest.read_bytes() == b"%PDF-1.4\nnew\n"
    assert os.listdir(dest.parent) == ["smith2020.pdf"]


def test_copy_pdf_replaces_same_size_changed(tmp_path):
    src = tmp_path / "paper.pdf"
    src.write_bytes(b"%PDF-1.4\nAAA\n")
    dest = tmp_path / "smith2020.pdf"
    dest.write_bytes(b"%PDF-1.4\nBBB\n")
    assert copy_pdf(src, dest) is True
    assert dest.read_bytes() == b"%PDF-1.4\nAAA\n"


def test_copy_pdf_leaves_no_temp_on_failure(tmp_path, monkeypatch):
    src = tmp_path / "paper.pdf"
    src.write_bytes(b"%PDF-1.4\n")
    files_dir = tmp_path / "files"

    def failing_replace(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(write.os, "replace", failing_replace)
    with pytest.raises(OSError, match="disk full"):
        copy_pdf(src, files_dir / "smith2020.pdf")
    assert not os.listdir(files_dir)


def test_creates_out_dir(tmp_path):
    out = tmp_path / "out"
    src = tmp_path / "paper.pdf"
    src.write_bytes(b"%PDF-1.4\n")
    atomic_write(out / "bibliography.bib", "@article{smith2020}\n")
    assert copy_pdf(src, out / "files" / "smith2020.pdf") is True
    assert (out / "bibliography.bib").read_text(encoding="utf-8") == "@article{smith2020}\n"
    assert (out / "files" / "smith2020.pdf").read_bytes() == b"%PDF-1.4\n"


def test_reports_unreferenced_files(tmp_path):
    files_dir = tmp_path / "files"
    files_dir.mkdir()
    (files_dir / "smith2020.pdf").write_bytes(b"%PDF-1.4\n")
    (files_dir / "old.pdf").write_bytes(b"%PDF-1.4\n")
    (files_dir / "subdir").mkdir()
    assert unreferenced_files(files_dir, {"smith2020.pdf"}) == ["old.pdf"]
    assert (files_dir / "old.pdf").exists()


def test_unreferenced_files_of_missing_dir(tmp_path):
    assert not unreferenced_files(tmp_path / "files", set())


@pytest.mark.parametrize(("umask", "mode"), [(0o022, 0o644), (0o002, 0o664)])
def test_written_files_follow_umask(tmp_path, monkeypatch, umask, mode):
    monkeypatch.setattr(write, "UMASK", umask)
    src = tmp_path / "paper.pdf"
    src.write_bytes(b"%PDF-1.4\n")
    atomic_write(tmp_path / "out" / "bibliography.bib", "@article{smith2020}\n")
    copy_pdf(src, tmp_path / "out" / "files" / "smith2020.pdf")
    assert (tmp_path / "out" / "bibliography.bib").stat().st_mode & 0o777 == mode
    assert (tmp_path / "out" / "files" / "smith2020.pdf").stat().st_mode & 0o777 == mode
