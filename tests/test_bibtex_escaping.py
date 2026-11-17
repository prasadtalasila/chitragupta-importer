"""Escaping and case protection of Zotero text, in entries and the name table."""

import re

import bibtexparser
import pytest
from bibtexparser.bparser import BibTexParser
from test_bibtex import fields_of, item

from chitragupta_importer.bibtex import render_bibliography, render_entry, render_name_table


def test_specials_escaped():
    fields = fields_of(render_entry("k", item(extra=r"a\b # $ % & _ | < > ~ ^"), []))
    assert fields["note"] == (
        r"{a{\textbackslash}b \# \$ \% \& \_ {\textbar} {\textless} {\textgreater}"
        r" {\textasciitilde} {\textasciicircum}}"
    )


@pytest.mark.parametrize(
    ("title", "protected"),
    [
        (
            "Robust Rule-Based Planning: A Review",
            "Robust {Rule}-{Based} {Planning}: {A} {Review}",
        ),
        ("ZEPHYR: A Toolkit", "{ZEPHYR}: {A} {Toolkit}"),
        ("(Co-)Design", "({Co}-){Design}"),
        ("Köhler's Ünits", "Köhler's {Ünits}"),
        ("5G and R&D", "{5G} and {R}\\&{D}"),
        ("Foo_Bar x|Y", "Foo\\_{Bar} x{\\textbar}{Y}"),
    ],
)
def test_case_protection_braces_each_run_of_letters_and_digits(title, protected):
    assert fields_of(render_entry("k", item(title=title), []))["title"] == f"{{{protected}}}"


def test_case_protected_fields():
    zotero = item(
        "bookSection",
        shortTitle="A B",
        series="C D",
        genre="E F",
        bookTitle="G H",
        abstractNote="I J",
    )
    fields = fields_of(render_entry("k", zotero, []))
    assert [fields[name] for name in ("shorttitle", "series", "type", "booktitle", "abstract")] == [
        "{A {B}}",
        "{C {D}}",
        "{E {F}}",
        "{G {H}}",
        "{I J}",
    ]
    journal = fields_of(render_entry("k", item(publicationTitle="K L"), []))["journal"]
    assert journal == "{K L}"


def test_paired_and_unpaired_braces_in_entries():
    fields = fields_of(render_entry("k", item(extra="{a} b{ c} }d {e{f}"), []))
    assert fields["note"] == (r"{\{a\} b\{ c\} \textbraceright{}d \textbraceleft{}e\{f\}}")


def unescape(value):
    """Undo the renderer: drop protection braces, then resolve escapes."""
    tokens = re.findall(r"\\textbrace(?:left|right)\{\}|\{\\textbackslash\}|\\.|.", value)
    named = {r"\textbraceleft{}": "{", r"\textbraceright{}": "}", r"{\textbackslash}": "\\"}
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
    assert render_name_table([("tide-pools", "Tide Pools")]) == (
        "@comment{cg-collections v1\ntide-pools\tTide Pools\n}\n"
    )


def test_name_table_escapes_braces():
    assert render_name_table([("a", "A {B}")]) == "@comment{cg-collections v1\na\tA \\{B\\}\n}\n"


def test_name_table_unpaired_brace_becomes_space():
    assert render_name_table([("a", "A }B{")]) == "@comment{cg-collections v1\na\tA  B \n}\n"


def test_unpaired_braces_in_url_and_doi_percent_encoded():
    entries = [
        render_entry("a", item(url="http://x.example/a}b", DOI="10.9999/x{"), []),
        render_entry("b", item(url="http://x.example/{c}%20#d_e", DOI="10.9999/{y}"), []),
        render_entry("c", item(title="After"), []),
    ]
    database = bibtexparser.loads(render_bibliography("", entries), BibTexParser())
    assert [e["ID"] for e in database.entries] == ["a", "b", "c"]
    a, b = database.entries[0], database.entries[1]
    assert (a["url"], a["doi"]) == ("http://x.example/a%7Db", "10.9999/x%7B")
    assert (b["url"], b["doi"]) == ("http://x.example/{c}%20#d_e", "10.9999/{y}")
