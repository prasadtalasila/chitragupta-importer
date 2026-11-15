"""Choosing the main PDF of an item and naming why an item is left out."""

from hashlib import sha256
from pathlib import Path

from chitragupta_importer.model import Attachment, Item
from chitragupta_importer.pdfs import LeftOutReason, main_pdf


def item(*attachments):
    return Item(
        item_id="zotero:user/ABCD1234",
        item_type="journalArticle",
        fields={},
        creators=(),
        attachments=attachments,
        collection_ids=(),
        tags=(),
    )


def pdf_file(directory, name):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_bytes(b"%PDF-1.4\n")
    return path


def pdf(path):
    return Attachment(content_type="application/pdf", path=path, file_name=path.name)


def test_no_attachment():
    assert main_pdf(item()) is LeftOutReason.NO_ATTACHMENT


def test_html_only_is_no_pdf_attachment(tmp_path):
    snapshot = tmp_path / "6.html"
    snapshot.write_text("<html></html>", encoding="utf-8")
    html = Attachment(content_type="text/html", path=snapshot, file_name="6.html")
    assert main_pdf(item(html)) is LeftOutReason.NO_PDF_ATTACHMENT


def test_pdf_by_suffix_without_content_type(tmp_path):
    path = pdf_file(tmp_path, "X.PDF")
    attachment = Attachment(content_type=None, path=path, file_name="X.PDF")
    assert main_pdf(item(attachment)) == path


def test_missing_pdf(tmp_path):
    assert main_pdf(item(pdf(tmp_path / "gone.pdf"))) is LeftOutReason.PDF_MISSING_ON_DISK


def test_pdf_without_path_is_missing_on_disk():
    linked_url = Attachment(content_type="application/pdf", path=None, file_name="")
    assert main_pdf(item(linked_url)) is LeftOutReason.PDF_MISSING_ON_DISK


def test_windows_linked_path_is_missing_on_disk():
    linked = pdf(Path("C:\\Users\\p\\x.pdf"))
    assert main_pdf(item(linked)) is LeftOutReason.PDF_MISSING_ON_DISK


def test_lowest_file_name_hash_wins(tmp_path):
    names = ["a.pdf", "b.pdf", "c.pdf", "d.pdf"]
    paths = [pdf_file(tmp_path, name) for name in names]
    expected = min(paths, key=lambda p: sha256(p.name.encode()).hexdigest())
    assert main_pdf(item(*(pdf(p) for p in paths))) == expected
    assert main_pdf(item(*(pdf(p) for p in reversed(paths)))) == expected


def test_equal_names_tie_broken_by_full_path(tmp_path):
    first = pdf_file(tmp_path / "AAA", "a.pdf")
    second = pdf_file(tmp_path / "BBB", "a.pdf")
    assert main_pdf(item(pdf(second), pdf(first))) == first


def test_missing_pdf_does_not_win_over_existing(tmp_path):
    names = ["a.pdf", "b.pdf", "c.pdf", "d.pdf"]
    best = min(names, key=lambda n: sha256(n.encode()).hexdigest())
    worst = max(names, key=lambda n: sha256(n.encode()).hexdigest())
    existing = pdf_file(tmp_path, worst)
    missing = pdf(tmp_path / best)
    assert main_pdf(item(missing, pdf(existing))) == existing
