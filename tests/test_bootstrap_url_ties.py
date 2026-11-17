"""Bootstrap URL ties that make duplicate groups, and the frozen key of a merged survivor."""

from dataclasses import replace

from chitragupta_importer.bootstrap import bootstrap, url_tie_groups
from chitragupta_importer.duplicates import merge_duplicates, pdf_then_oldest
from chitragupta_importer.model import Attachment, Creator, Item, Library
from chitragupta_importer.normalise import item_pdf_hashes

URL = "https://example.org/smith-twins"
DOI = "10.9999/smith.twins"
SURVIVOR = "zotero:user/AAAA1111"


def item(key, title, item_type="journalArticle", attachments=(), **fields):
    return Item(
        item_id=f"zotero:user/{key}",
        item_type=item_type,
        fields={"title": title, "date": "2024", **fields},
        creators=(Creator("Smith", "Jo", False, "author"),),
        attachments=attachments,
        collection_ids=(),
        tags=(),
        date_added="2020-01-01 00:00:00",
    )


def library(*items):
    return Library(items=items, collections=(), skipped_libraries=())


def existing_bib(tmp_path, *entries):
    """Each entry is `(citekey, fields)`."""
    path = tmp_path / "existing" / "references.bib"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            f"@article{{{citekey},\n"
            + "".join(f"  {name} = {{{value}}},\n" for name, value in fields.items())
            + "}\n"
            for citekey, fields in entries
        ),
        encoding="utf-8",
    )
    return path


def test_url_tie_groups_found(tmp_path):
    lib = library(
        item("AAAA1111", "Twins, part one", url=URL),
        item("BBBB2222", "Twins deliverable", item_type="report", url=URL),
        item("CCCC3333", "Other twins", url="https://example.org/other", DOI=DOI),
        item("DDDD4444", "More twins", url="https://example.org/other"),
    )
    bib = existing_bib(
        tmp_path,
        ("smith_twins_2024", {"title": "Smith twins", "url": URL}),
        ("smith_twins_2024-1", {"title": "Twins", "url": URL}),
        ("smith_other_2024", {"doi": DOI, "url": "https://example.org/other"}),
    )
    assert url_tie_groups(bib, lib) == [frozenset({SURVIVOR, "zotero:user/BBBB2222"})]


def test_generic_url_with_title_breaks_groups_nothing(tmp_path):
    lib = library(
        item("AAAA1111", "Twins, part one", url=URL),
        item("BBBB2222", "Twins, part two", url=URL),
        item("CCCC3333", "Lone twin", url="https://example.org/lone"),
    )
    bib = existing_bib(
        tmp_path,
        ("smith_twins_2024", {"title": "Twins, Part One", "url": URL}),
        ("smith_lone_2024", {"title": "Different", "url": "https://example.org/lone"}),
        ("smith_none_2024", {"title": "Nothing"}),
    )
    assert not url_tie_groups(bib, lib)


def test_url_tie_narrowed_to_items_with_entry_title(tmp_path):
    project = "https://example.org/project"
    lib = library(
        item("AAAA1111", "Twins", url=project),
        item("BBBB2222", "Twins", item_type="report", url=project),
        item("CCCC3333", "Deliverable D1", url=project),
    )
    bib = existing_bib(tmp_path, ("smith_twins_2024", {"title": "Twins", "url": project}))
    assert url_tie_groups(bib, lib) == [frozenset({SURVIVOR, "zotero:user/BBBB2222"})]


def test_ties_at_doi_or_pdf_level_make_no_group(tmp_path):
    pdf = tmp_path / "storage" / "shared.pdf"
    pdf.parent.mkdir(parents=True)
    pdf.write_bytes(b"%PDF shared")
    attachment = (Attachment("application/pdf", pdf, "shared.pdf"),)
    lib = library(
        item("AAAA1111", "Twins, part one", url=URL, DOI=DOI),
        item("BBBB2222", "Twins, part two", url=URL, DOI=DOI),
        item("CCCC3333", "Gauges, part one", attachments=attachment, url=URL),
        item("DDDD4444", "Gauges, part two", attachments=attachment, url=URL),
    )
    entry_pdf = tmp_path / "existing" / "gauges.pdf"
    entry_pdf.parent.mkdir(parents=True)
    entry_pdf.write_bytes(b"%PDF shared")
    bib = existing_bib(
        tmp_path,
        ("smith_twins_2024", {"title": "Twins", "doi": DOI, "url": URL}),
        (
            "smith_gauges_2024",
            {"title": "Gauges", "url": URL, "file": ":gauges.pdf:application/pdf"},
        ),
    )
    assert not url_tie_groups(bib, lib)


def merged_copies(tmp_path, a_bytes, b_bytes):
    """Copies A (older, the survivor) and B with PDFs; the merged library and survivor PDFs."""
    copies = []
    for key, content, added in (("AAAA1111", a_bytes, "2019"), ("BBBB2222", b_bytes, "2020")):
        path = tmp_path / "storage" / key / "main.pdf"
        path.parent.mkdir(parents=True)
        path.write_bytes(content)
        attachment = Attachment("application/pdf", path, "main.pdf")
        copy = item(key, "Twins", attachments=(attachment,), DOI=DOI)
        copies.append(replace(copy, date_added=f"{added}-01-01 00:00:00"))
    merged, duplicates = merge_duplicates(library(*copies), pdf_then_oldest)
    assert set(duplicates.values()) == {SURVIVOR}
    return merged, {SURVIVOR: item_pdf_hashes(copies[0])}


def entry_with_pdf(tmp_path, name, content):
    (tmp_path / "existing").mkdir(exist_ok=True)
    (tmp_path / "existing" / name).write_bytes(content)
    return {"title": "Twins", "doi": DOI, "file": f"Full Text:{name}:application/pdf"}


def test_frozen_key_follows_survivor_pdf(tmp_path):
    lib, survivor_pdfs = merged_copies(tmp_path, b"%PDF copy A", b"%PDF copy B")
    bib = existing_bib(
        tmp_path,
        ("smith_twins_2024", entry_with_pdf(tmp_path, "b.pdf", b"%PDF copy B")),
        ("smith_twins_2024-1", entry_with_pdf(tmp_path, "a.pdf", b"%PDF copy A")),
    )
    assert bootstrap(bib, lib, {SURVIVOR}).lock == {SURVIVOR: "smith_twins_2024"}
    result = bootstrap(bib, lib, {SURVIVOR}, survivor_pdfs)
    assert result.lock == {SURVIVOR: "smith_twins_2024-1"}
    assert result.dropped == ("smith_twins_2024",)


def test_identical_pdfs_fall_back_to_stem_rule(tmp_path):
    lib, survivor_pdfs = merged_copies(tmp_path, b"%PDF same", b"%PDF same")
    bib = existing_bib(
        tmp_path,
        ("smith_twins_2024-1", entry_with_pdf(tmp_path, "a.pdf", b"%PDF same")),
        ("smith_twins_2024", entry_with_pdf(tmp_path, "b.pdf", b"%PDF same")),
    )
    result = bootstrap(bib, lib, {SURVIVOR}, survivor_pdfs)
    assert result.lock == {SURVIVOR: "smith_twins_2024"}
    assert result.dropped == ("smith_twins_2024-1",)
