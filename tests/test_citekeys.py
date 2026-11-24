"""The safe-citekey rule and the key rule."""

import pytest

from chitragupta_importer.citekeys import (
    UnsafeCitekey,
    citekey_problem,
    export_stem,
    key_stem,
)
from chitragupta_importer.model import Creator, Item


def item(creators=(), fields=None):
    return Item(
        item_id="zotero:user/ABCD1234",
        item_type="journalArticle",
        fields=fields or {},
        creators=tuple(
            Creator(last=c[0], first=c[1], single_field=c[1] == "", role=c[2]) for c in creators
        ),
        attachments=(),
        collection_ids=(),
        tags=(),
    )


@pytest.mark.parametrize(
    "key",
    ["", " ", ".", "..", "a/b", "a\\b", "a:b", "a*b", "a?b", 'a"b', "a<b", "a>b",
     "a|b", "a\x01b", "a\x00b", "a\x1fb", "key.", "key ", "CON", "com1.x", "lpt9",
     "Nul.tar.gz"],
)  # fmt: skip
def test_unsafe(key):
    assert citekey_problem(key) is not None


@pytest.mark.parametrize(
    "key", ["dorsey_pattern_2023-1", "con_x_2020", "com10", "lpt0", "a.b", "a\x7fb"]
)
def test_safe(key):
    assert citekey_problem(key) is None


def test_problem_names_the_character():
    assert "'\\x01'" in citekey_problem("a\x01b")
    assert "':'" in citekey_problem("a:b")


def test_unsafe_citekey_is_a_value_error():
    assert issubclass(UnsafeCitekey, ValueError)


def test_stem_shape():
    it = item(
        creators=[("Köhler", "Jan", "author")],
        fields={"title": "The Calibrating of Twins", "date": "2024-02"},
    )
    assert export_stem(it) == "kohler_calibrating_2024"


def test_stem_with_nothing():
    assert export_stem(item()) == "noauthor__nodate"


def test_stem_takes_first_creator_whatever_its_role():
    it = item(creators=[("Ed", "A", "editor"), ("Writer", "B", "author")])
    assert export_stem(it) == "ed__nodate"
    assert export_stem(item(creators=[("", "Only First", "author")])) == "noauthor__nodate"


def test_stem_uses_first_creator_of_any_role_when_no_author():
    it = item(creators=[("Mäder", "Jan", "editor"), ("Other", "X", "editor")])
    assert export_stem(it) == "mader__nodate"


def test_stem_single_field_creator():
    it = item(creators=[("Microsoft Research", "", "author")])
    assert export_stem(it).startswith("microsoft_research_")


@pytest.mark.parametrize(
    ("last", "part"),
    [
        ("van Dyke", "van_dyke"),
        ("Lee, Kim, Park", "lee_kim_park"),
        ("García Lorca", "garcia_lorca"),
    ],
)
def test_stem_creator_spaces_become_underscores_commas_dropped(last, part):
    assert export_stem(item(creators=[(last, "", "author")])) == f"{part}__nodate"


def test_stem_drops_characters_outside_a_z_0_9_hyphen():
    it = item(creators=[("microsoft/web-dev", "", "author")])
    assert export_stem(it) == "microsoftweb-dev__nodate"


@pytest.mark.parametrize(
    ("title", "word"),
    [
        ("A Study", "study"),
        ("THE AN Of with Models", "models"),
        ("Die Theorie der Dinge", "theorie"),
        ("L'Évolution des espèces", "levolution"),
        ("Out-of-the-Box Tools", "out---box"),
        ("On-line Learning", "-line"),
        ("Hands-on with Sensors", "hands-sensors"),
        ("Models-as-a-Service", "models-as--service"),
        ("(Co-)Design Methods", "co-design"),
        ("TCP/IP stacks", "tcpip"),
        ("Don't panic", "dont"),
        ("Rule\u2010based systems", "rulebased"),
        ("The <i>Gene</i> Study", "gene"),
        ("On", ""),
        ("", ""),
    ],
)
def test_stem_title_word(title, word):
    assert export_stem(item(fields={"title": title})) == f"noauthor_{word}_nodate"


@pytest.mark.parametrize(
    ("date", "year"),
    [("2024", "2024"), ("March 12, 1999", "1999"), ("12/03/99", "nodate"), ("", "nodate")],
)
def test_stem_year(date, year):
    assert export_stem(item(fields={"date": date})) == f"noauthor__{year}"


@pytest.mark.parametrize(
    ("last", "title", "date", "stem"),
    [
        ("Smith", "Digital Platforms", "2020", "smith_digital_2020"),
        ("Ostrander", "Calibrating the Digital Twin", "2024", "ostrander_calib_2024"),
        ("dos Santos", "Digital twins", "2022", "dos_santos_digi_2022"),
        ("Committee on Foundational Research Gaps", "Foundational", "2024", "committee_found_2024"),
        ("Kuruppuarachchi", "Architecture", "2022", "kuruppuara_arch_2022"),
        ("Li", "Knowledge-orchestrated agents", "2025", "li_knowledge_2025"),
        ("Zech", "Digital-Twins-as-a-Service", "2024", "zech_digital_2024"),
        ("Ostrander", "Calibrating", "", "ostrander_cal_nodate"),
    ],
)
def test_key_stem_is_at_most_20_characters_with_creator_at_most_10(last, title, date, stem):
    it = item(creators=[(last, "", "author")], fields={"title": title, "date": date})
    assert key_stem(it) == stem and len(stem) <= 20


def test_key_stem_keeps_the_export_stem_when_it_fits():
    it = item(creators=[("Ed", "A", "editor")])
    assert key_stem(it) == export_stem(it) == "ed__nodate"
