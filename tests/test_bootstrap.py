"""Bootstrap: freezing the citekeys of an existing bibliography in the citekey lock."""

import pytest
from zotero_fixture import ZoteroFixture

from chitragupta_importer.bootstrap import BootstrapRefused, bootstrap
from chitragupta_importer.sources.zotero import read_library

PDF = b"%PDF-1.4\nsame bytes\n"


def library_of(tmp_path, *items):
    """Each item is `(key, fields, pdfs)`; returns the read `Library`."""
    fixture = ZoteroFixture(tmp_path)
    for key, fields, pdfs in items:
        fixture.add_item(key, fields=fields, pdfs=pdfs)
    return read_library(fixture.build())


def existing_bib(tmp_path, text):
    path = tmp_path / "existing" / "references.bib"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def entry(citekey, **fields):
    body = "".join(f"  {name} = {{{value}}},\n" for name, value in fields.items())
    return f"@article{{{citekey},\n{body}}}\n"


def test_matches_by_pdf_content_hash(tmp_path):
    library = library_of(
        tmp_path,
        ("AAAA1111", {"title": "Other"}, [("a.pdf", b"%PDF other")]),
        ("BBBB2222", {"title": "Digital Twins"}, [("b.pdf", PDF)]),
    )
    bib = existing_bib(
        tmp_path, entry("smith_digital_2020", file="Full Text:pdfs/x.pdf:application/pdf")
    )
    (bib.parent / "pdfs").mkdir()
    (bib.parent / "pdfs" / "x.pdf").write_bytes(PDF)
    result = bootstrap(bib, library)
    assert result.lock == {"zotero:user/BBBB2222": "smith_digital_2020"}
    assert result.unmatched == result.ambiguous == result.not_included == ()


def test_pdf_hash_matches_any_pdf_of_the_item_and_unescapes_file_field(tmp_path):
    library = library_of(
        tmp_path,
        ("AAAA1111", {}, [("a.pdf", b"%PDF main"), ("z.pdf", PDF)]),
    )
    pdf = tmp_path / "abs dir" / "x:y;z.pdf"
    pdf.parent.mkdir()
    pdf.write_bytes(PDF)
    escaped = str(pdf).replace(":", "\\:").replace(";", "\\;")
    files = (
        "Snapshot:gone.html:text/html;:missing.pdf:application/pdf;"
        f"Full\\: Text:{escaped}:application/pdf"
    )
    result = bootstrap(existing_bib(tmp_path, entry("k1", file=files)), library)
    assert result.lock == {"zotero:user/AAAA1111": "k1"}


def test_falls_back_to_doi_then_url_then_title(tmp_path):
    library = library_of(
        tmp_path,
        ("AAAA1111", {"DOI": "10.1/a", "title": "Same"}, [("a.pdf", b"%PDF a")]),
        ("BBBB2222", {"url": "https://x.org/b", "title": "Same"}, [("b.pdf", b"%PDF b")]),
        ("CCCC3333", {"extra": "tex.key: x\nDOI: 10.1/c"}, [("c.pdf", b"%PDF c")]),
        ("DDDD4444", {"title": "Unique Title"}, [("d.pdf", b"%PDF d")]),
    )
    text = (
        entry("ka", doi="10.1/a", title="Same", file="pdfs/none.pdf")
        + entry("kb", url="https://x.org/b", title="Same")
        + entry("kc", doi="doi:10.1/C")
        + entry("kd", title="Unique title")
    )
    result = bootstrap(existing_bib(tmp_path, text), library)
    assert result.lock == {
        "zotero:user/AAAA1111": "ka",
        "zotero:user/BBBB2222": "kb",
        "zotero:user/CCCC3333": "kc",
        "zotero:user/DDDD4444": "kd",
    }


def test_doi_normalised(tmp_path):
    library = library_of(tmp_path, ("AAAA1111", {"DOI": "10.1/abc"}, [("a.pdf", PDF)]))
    bib = existing_bib(tmp_path, entry("k1", doi="https://doi.org/10.1/ABC"))
    assert bootstrap(bib, library).lock == {"zotero:user/AAAA1111": "k1"}


def test_title_normalised(tmp_path):
    library = library_of(tmp_path, ("AAAA1111", {"title": "Digital Twins"}, [("a.pdf", PDF)]))
    bib = existing_bib(tmp_path, entry("k1", title="{Digital} {Twin}s"))
    assert bootstrap(bib, library).lock == {"zotero:user/AAAA1111": "k1"}


def test_unmatched_listed_without_lock_line(tmp_path):
    library = library_of(tmp_path, ("AAAA1111", {"title": "Known"}, [("a.pdf", PDF)]))
    text = (
        entry("zz_other_2020", title="Unknown")
        + entry("aa_bare_2020", year="2020")
        + entry("k1", title="Known")
    )
    result = bootstrap(existing_bib(tmp_path, text), library)
    assert result.lock == {"zotero:user/AAAA1111": "k1"}
    assert result.unmatched == ("aa_bare_2020", "zz_other_2020")


def test_ambiguous_entry_refuses(tmp_path):
    library = library_of(
        tmp_path,
        ("AAAA1111", {"title": "Twin", "DOI": "10.1/a"}, [("a.pdf", PDF)]),
        ("BBBB2222", {"title": "Twin"}, [("b.pdf", PDF)]),
    )
    bib = existing_bib(tmp_path, entry("k_twin", title="Twin"))
    with pytest.raises(BootstrapRefused, match="ambiguous.*k_twin"):
        bootstrap(bib, library)


def test_first_matching_level_decides_over_ambiguous_later_level(tmp_path):
    library = library_of(
        tmp_path,
        ("AAAA1111", {"title": "Twin", "DOI": "10.1/a"}, [("a.pdf", b"%PDF a")]),
        ("BBBB2222", {"title": "Twin"}, [("b.pdf", b"%PDF b")]),
    )
    bib = existing_bib(tmp_path, entry("k_twin", title="Twin", doi="10.1/a"))
    assert bootstrap(bib, library).lock == {"zotero:user/AAAA1111": "k_twin"}


def test_item_claimed_by_two_entries_refuses(tmp_path):
    library = library_of(tmp_path, ("AAAA1111", {"title": "Twin"}, [("a.pdf", PDF)]))
    bib = existing_bib(tmp_path, entry("k1", title="Twin") + entry("k2", title="TWIN"))
    with pytest.raises(BootstrapRefused, match="k1.*k2"):
        bootstrap(bib, library)


def test_matched_item_without_pdf_gets_no_lock_line(tmp_path):
    library = library_of(tmp_path, ("AAAA1111", {"title": "Toward a Twin"}, [("gone.pdf", None)]))
    bib = existing_bib(tmp_path, entry("varga_toward_nodate", title="Toward a twin"))
    result = bootstrap(bib, library)
    assert result.not_included == ("varga_toward_nodate",) and not result.lock
    assert not result.unmatched


def test_unsafe_frozen_key_refuses(tmp_path):
    library = library_of(tmp_path, ("AAAA1111", {"title": "Twin"}, [("a.pdf", PDF)]))
    bib = existing_bib(tmp_path, entry("a:b", title="Twin"))
    with pytest.raises(BootstrapRefused, match="'a:b'.*contains ':'"):
        bootstrap(bib, library)


def test_unsafe_unmatched_key_is_only_listed(tmp_path):
    library = library_of(tmp_path, ("AAAA1111", {"title": "Twin"}, [("a.pdf", PDF)]))
    bib = existing_bib(tmp_path, entry("a:b", title="Other"))
    assert bootstrap(bib, library).unmatched == ("a:b",)


def test_duplicate_citekey_refuses(tmp_path):
    library = library_of(
        tmp_path,
        ("AAAA1111", {"title": "One"}, [("a.pdf", b"%PDF a")]),
        ("BBBB2222", {"title": "Two"}, [("b.pdf", b"%PDF b")]),
    )
    bib = existing_bib(tmp_path, entry("k1", title="One") + entry("k1", title="Two"))
    with pytest.raises(BootstrapRefused, match="duplicate citekey k1 in existing bibliography"):
        bootstrap(bib, library)


def test_duplicate_citekey_refuses_when_one_entry_is_unmatched(tmp_path):
    library = library_of(tmp_path, ("AAAA1111", {"title": "One"}, [("a.pdf", PDF)]))
    bib = existing_bib(tmp_path, entry("k1", title="One") + entry("k1", title="Other"))
    with pytest.raises(BootstrapRefused, match="duplicate citekey k1"):
        bootstrap(bib, library)
