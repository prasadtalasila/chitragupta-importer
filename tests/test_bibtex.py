"""Rendering entries, the name table and the bibliography."""

import re

import bibtexparser
import pytest
from bibtexparser.bparser import BibTexParser

from chitragupta_importer.bibtex import render_bibliography, render_entry, render_name_table
from chitragupta_importer.model import Creator, Item


def author(last, first):
    return Creator(last, first, False, "author")


def item(item_type="journalArticle", creators=(), tags=(), **fields):
    return Item("zotero:user/ABCD1234", item_type, fields, tuple(creators), (), (), tuple(tags))


def article_item():
    return item(
        title="Characterizing the Digital Twin",
        volume="8",
        DOI="10.3390/designs8010008",
        publicationTitle="Designs",
        date="2024-02-00 2024/2",
        pages="8",
        creators=[author("Richstein", "Rebecca"), author("Schröder", "Kai-Uwe")],
        tags=["design", "digital twin"],
    )


def fields_of(text):
    """The `name = value` pairs of one rendered entry, values as written."""
    return dict(re.findall(r"^\t(\S+) = (.*),$", text, re.MULTILINE))


def test_article_entry_exact():
    text = render_entry(
        "richstein_characterizing_2024", article_item(), ["digital-twin.dt-platforms"]
    )
    assert text == (
        "@article{richstein_characterizing_2024,\n"
        "\ttitle = {Characterizing the {Digital} {Twin}},\n"
        "\tvolume = {8},\n"
        "\tdoi = {10.3390/designs8010008},\n"
        "\tjournal = {Designs},\n"
        "\tauthor = {Richstein, Rebecca and Schröder, Kai-Uwe},\n"
        "\tmonth = feb,\n"
        "\tyear = {2024},\n"
        "\tkeywords = {design, digital twin},\n"
        "\tpages = {8},\n"
        "\tfile = {Full Text PDF:files/richstein_characterizing_2024.pdf:application/pdf},\n"
        "\tcg-collections = {digital-twin.dt-platforms},\n"
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
        Creator("Roe", "Rick", False, "editor"),
        Creator("Poe", "Pam", False, "editor"),
        Creator("Low", "Lee", False, "contributor"),
        Creator("Tran", "Tom", False, "translator"),
    ]
    fields = fields_of(render_entry("k", item("book", creators=creators), []))
    assert fields["author"] == "{Doe, Jane}"
    assert fields["editor"] == "{Roe, Rick and Poe, Pam}"
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


def test_report_and_thesis_fields():
    report = item("report", institution="Aarhus", reportType="Tech", reportNumber="7")
    assert fields_of(render_entry("k", report, [])) == {
        "type": "{Tech}",
        "number": "{7}",
        "institution": "{Aarhus}",
        "file": "{Full Text PDF:files/k.pdf:application/pdf}",
    }
    thesis = fields_of(render_entry("k", item("thesis", university="AU", thesisType="PhD"), []))
    assert (thesis["school"], thesis["type"]) == ("{AU}", "{PhD}")


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


def test_specials_and_backslash_escaped():
    fields = fields_of(render_entry("k", item(extra=r"a\b # $ % & _"), []))
    assert fields["note"] == r"{a\textbackslash{}b \# \$ \% \& \_}"


def test_paired_and_unpaired_braces_in_entries():
    fields = fields_of(render_entry("k", item(extra="{a} b{ c} }d {e{f}"), []))
    assert fields["note"] == (r"{\{a\} b\{ c\} \textbraceright{}d \textbraceleft{}e\{f\}}")


def unescape(value):
    """Undo the renderer: drop protection braces, then resolve escapes."""
    tokens = re.findall(r"\\textbrace(?:left|right)\{\}|\\textbackslash\{\}|\\.|.", value)
    named = {r"\textbraceleft{}": "{", r"\textbraceright{}": "}", r"\textbackslash{}": "\\"}
    out = []
    for token in tokens:
        if token in named:
            out.append(named[token])
        elif token.startswith("\\"):
            out.append(token[1:])
        elif token not in "{}":
            out.append(token)
    return "".join(out)


def test_specials_round_trip():
    title = r"50% of {A} & B_c #1 {open Close} x\y"
    entries = [
        render_entry("a", item(title=title), ["paired", "lone"]),
        render_entry("b", item("conferencePaper", title="T", proceedingsTitle="P {Q"), []),
    ]
    table = render_name_table([("paired", "Paired {X}"), ("lone", "Lone { brace } }")])
    text = render_bibliography(table, entries)
    database = bibtexparser.loads(text, BibTexParser(common_strings=True))
    assert [e["ID"] for e in database.entries] == ["a", "b"]
    assert unescape(database.entries[0]["title"]) == title
    assert unescape(database.entries[1]["booktitle"]) == "P {Q"
    # bibtexparser expands tabs in comments; the table block parses back whole.
    table_text = "cg-collections v1\npaired\tPaired \\{X\\}\nlone\tLone \\{ brace \\}  \n"
    assert database.comments == [table_text.expandtabs()]


def test_name_table_block():
    assert render_name_table([("digital-twin", "Digital Twin")]) == (
        "@comment{cg-collections v1\ndigital-twin\tDigital Twin\n}\n"
    )


def test_name_table_escapes_braces():
    assert render_name_table([("a", "A {B}")]) == "@comment{cg-collections v1\na\tA \\{B\\}\n}\n"


def test_name_table_unpaired_brace_becomes_space():
    assert render_name_table([("a", "A }B{")]) == "@comment{cg-collections v1\na\tA  B \n}\n"


def test_empty_name_table():
    assert render_name_table([]) == ""


def test_bibliography_is_name_table_then_entries_blank_line_separated():
    table = render_name_table([("a", "A")])
    first, second = render_entry("x", item(), []), render_entry("y", item(), [])
    assert render_bibliography(table, [first, second]) == f"{table}\n{first}\n{second}"
    assert render_bibliography("", [first]) == first
    assert render_bibliography("", []) == ""
