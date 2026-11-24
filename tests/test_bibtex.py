"""Rendering entries, the name table and the bibliography."""

import re

import pytest

from chitragupta_importer.bibtex import render_bibliography, render_entry, render_name_table
from chitragupta_importer.model import Creator, Item


def author(last, first):
    return Creator(last, first, False, "author")


def item(item_type="journalArticle", creators=(), tags=(), **fields):
    return Item("zotero:user/ABCD1234", item_type, fields, tuple(creators), (), (), tuple(tags))


def article_item():
    return item(
        title="Calibrating the Digital Twin",
        volume="8",
        DOI="10.9999/fictional.2024.0008",
        publicationTitle="Fictional Twins",
        date="2024-02-00 2024/2",
        pages="8",
        creators=[author("Ostrander", "Ingrid"), author("Köhler", "Jan-Ole")],
        tags=["design", "digital twin"],
    )


def fields_of(text):
    """The `name = value` pairs of one rendered entry, values as written."""
    return dict(re.findall(r"^\t(\S+) = (.*),$", text, re.MULTILINE))


def test_article_entry_exact():
    text = render_entry("ostrander_calibrating_2024", article_item(), ["tide-pools.tp-gauges"])
    assert text == (
        "@article{ostrander_calibrating_2024,\n"
        "\ttitle = {Calibrating the {Digital} {Twin}},\n"
        "\tvolume = {8},\n"
        "\tdoi = {10.9999/fictional.2024.0008},\n"
        "\tjournal = {Fictional Twins},\n"
        "\tauthor = {Ostrander, Ingrid and Köhler, Jan-Ole},\n"
        "\tmonth = feb,\n"
        "\tyear = {2024},\n"
        "\tkeywords = {design, digital twin},\n"
        "\tpages = {8},\n"
        "\tfile = {Full Text PDF:files/ostrander_calibrating_2024.pdf:application/pdf},\n"
        "\tcg-collections = {tide-pools.tp-gauges},\n"
        "}\n"
    )


ENTRY_TYPES = (
    "journalArticle:article magazineArticle:article newspaperArticle:article "
    "conferencePaper:inproceedings bookSection:incollection book:book report:techreport "
    "thesis:phdthesis manuscript:unpublished webpage:misc preprint:misc computerProgram:misc"
)


@pytest.mark.parametrize("zotero_type,bibtex_type", [p.split(":") for p in ENTRY_TYPES.split()])
def test_entry_types(zotero_type, bibtex_type):
    assert render_entry("k", item(zotero_type, title="T"), []).startswith(f"@{bibtex_type}{{k,\n")


def test_single_field_creator_braced():
    org = Creator("Microsoft Research", "", True, "author")
    assert (
        fields_of(render_entry("k", item(creators=[org]), []))["author"] == "{{Microsoft Research}}"
    )


def test_editor_and_contributor_fields():
    creators = [
        author("Doe", "Jane"),
        Creator("Goe", "Gus", False, "seriesEditor"),
        Creator("Roe", "Rick", False, "editor"),
        Creator("Poe", "Pam", False, "editor"),
        Creator("Low", "Lee", False, "contributor"),
        Creator("Tran", "Tom", False, "translator"),
    ]
    fields = fields_of(render_entry("k", item("book", creators=creators), []))
    assert fields["author"] == "{Doe, Jane}"
    assert fields["editor"] == "{Goe, Gus and Roe, Rick and Poe, Pam}"
    assert fields["collaborator"] == "{Low, Lee}"
    assert "Tran" not in render_entry("k", item("book", creators=creators), [])


def test_field_order_and_omitted_empty_fields():
    text = render_entry(
        "k", item("book", title="T", place="Berlin", series="", note=""), ["a", "b.c"]
    )
    assert text == (
        "@book{k,\n"
        "\taddress = {Berlin},\n"
        "\ttitle = {T},\n"
        "\tfile = {Full Text PDF:files/k.pdf:application/pdf},\n"
        "\tcg-collections = {a, b.c},\n"
        "}\n"
    )


def test_conference_paper_booktitle_protected():
    fields = fields_of(
        render_entry("k", item("conferencePaper", proceedingsTitle="Proc. of the IEEE Conf"), [])
    )
    assert fields["booktitle"] == "{Proc. of the {IEEE} {Conf}}"
    assert "journal" not in fields


@pytest.mark.parametrize(
    ("zotero_type", "source"),
    [("webpage", "websiteTitle"), ("blogPost", "blogTitle"), ("forumPost", "forumTitle")],
)
def test_journal_for_types_other_than_conference_paper_and_book_section(zotero_type, source):
    fields = fields_of(render_entry("k", item(zotero_type, **{source: "Site"}), []))
    assert fields["journal"] == "{Site}"
    assert "booktitle" not in fields


@pytest.mark.parametrize(
    ("pages", "written"),
    [
        ("31-47", "31--47"),
        ("1\u20135", "1--5"),
        ("4:1-4:20", "4:1--4:20"),
        ("2--9", "2--9"),
        ("7", "7"),
    ],
)
def test_page_range_dash(pages, written):
    assert fields_of(render_entry("k", item(pages=pages), []))["pages"] == f"{{{written}}}"


def test_publisher_issn_doi_lines_of_extra_become_fields():
    extra = "Publisher: IEEE\nissn: 1234-5678\nDOI: 10.1/x\nConference Name: C"
    fields = fields_of(render_entry("k", item(extra=extra), []))
    assert (fields["publisher"], fields["issn"], fields["doi"]) == (
        "{IEEE}",
        "{1234-5678}",
        "{10.1/x}",
    )
    assert fields["note"] == "{Conference Name: C}"


def test_item_field_wins_over_extra_line():
    zotero = item(publisher="ACM", ISSN="1", extra="Publisher: IEEE\nISSN: 2")
    text = render_entry("k", zotero, [])
    assert (fields_of(text)["publisher"], fields_of(text)["issn"]) == ("{ACM}", "{1}")
    assert "\tnote = " not in text


def test_report_and_thesis_fields():
    report = item("report", institution="Aarhus", reportType="Tech", reportNumber="7")
    assert fields_of(render_entry("k", report, [])) == {
        "type": "{Tech}",
        "number": "{7}",
        "institution": "{Aarhus}",
        "file": "{Full Text PDF:files/k.pdf:application/pdf}",
    }
    thesis = fields_of(render_entry("k", item("thesis", university="AU", thesisType="PhD"), []))
    assert (thesis["school"], thesis["type"]) == ("{AU}", "{{PhD}}")


SIMPLE_SOURCES = (
    "shortTitle:shorttitle abstractNote:abstract ISSN:issn ISBN:isbn language:language "
    "rights:copyright issue:number edition:edition repository:publisher company:publisher "
    "extra:note genre:type series:series"
)


@pytest.mark.parametrize(
    "zotero_field,entry_field",
    [p.split(":") for p in SIMPLE_SOURCES.split()],
)
def test_simple_field_sources(zotero_field, entry_field):
    fields = fields_of(render_entry("k", item(**{zotero_field: "V"}), []))
    assert fields[entry_field] == "{V}"


def test_first_non_empty_source_wins():
    fields = fields_of(render_entry("k", item(issue="", number="9", reportNumber="7"), []))
    assert fields["number"] == "{9}"


def test_doi_from_extra_and_url_verbatim():
    zotero = item(extra="Foo\nDOI: 10.1/a_b%c\nBar", url="https://x.org/a_b%20c#frag")
    fields = fields_of(render_entry("k", zotero, []))
    assert fields["doi"] == "{10.1/a_b%c}"
    assert fields["url"] == "{https://x.org/a_b%20c#frag}"


def test_doi_field_wins_over_extra():
    fields = fields_of(render_entry("k", item(DOI="10.1/x", extra="DOI: 10.1/y"), []))
    assert fields["doi"] == "{10.1/x}"


@pytest.mark.parametrize(
    "date,month,year",
    [
        ("2020-04-01 2020-04-01", "apr", "{2020}"),
        ("2024-12-00 2024/12", "dec", "{2024}"),
        ("2024-00-00 2024", None, "{2024}"),
        ("2024-13-00 2024", None, "{2024}"),
        ("Spring 1999", None, "{1999}"),
        ("unknown", None, None),
    ],
)
def test_month_and_year(date, month, year):
    fields = fields_of(render_entry("k", item(date=date), []))
    assert (fields.get("month"), fields.get("year")) == (month, year)


def test_urldate_is_date_part_of_access_date():
    assert fields_of(render_entry("k", item(accessDate="2023-05-06 07:08:09"), []))["urldate"] == (
        "{2023-05-06}"
    )


def test_empty_name_table():
    assert render_name_table([]) == ""


def test_bibliography_is_name_table_then_entries_blank_line_separated():
    table = render_name_table([("a", "A")])
    first, second = render_entry("x", item(), []), render_entry("y", item(), [])
    assert render_bibliography([table], [first, second]) == f"{table}\n{first}\n{second}"
    assert render_bibliography([""], [first]) == first
    assert render_bibliography(["", ""], []) == ""


def test_header_blocks_in_order():
    assert render_bibliography(["T\n", "R\n"], ["E\n"]) == "T\n\nR\n\nE\n"
