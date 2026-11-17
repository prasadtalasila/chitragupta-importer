"""Bootstrap on merged items, and title tie-breaks between items that are not duplicates."""

import pytest

from chitragupta_importer.bootstrap import BootstrapRefused, bootstrap
from chitragupta_importer.duplicates import merge_duplicates, oldest_added
from chitragupta_importer.model import Attachment, Creator, Item, Library

TWIN = b"%PDF-1.4 twin\n"
SURVIVOR = "zotero:user/AAAA1111"


def item(tmp_path, key, title, content=TWIN, item_type="journalArticle"):
    path = tmp_path / "storage" / key / "main.pdf"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return Item(
        item_id=f"zotero:user/{key}",
        item_type=item_type,
        fields={"title": title},
        creators=(Creator("Kapteyn", "Ada", False, "author"),),
        attachments=(Attachment("application/pdf", path, "main.pdf"),),
        collection_ids=(),
        tags=(),
        date_added="2020-01-01 00:00:00",
    )


def merged_library(tmp_path):
    """Two duplicate items titled "Toward a Twin"; returns the merged library and `merged`."""
    library = Library(
        items=(
            item(tmp_path, "AAAA1111", "Toward a Twin"),
            item(tmp_path, "BBBB2222", "Toward a twin"),
        ),
        collections=(),
        skipped_libraries=(),
    )
    merged, duplicates = merge_duplicates(library, oldest_added)
    return merged, set(duplicates.values())


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
    (path.parent / "twin.pdf").write_bytes(TWIN)
    return path


def same_pdf(title=None):
    fields = {"file": "Full Text:twin.pdf:application/pdf"}
    return fields if title is None else {**fields, "title": title}


def plain_library(*items):
    return Library(items=items, collections=(), skipped_libraries=())


def test_title_breaks_non_duplicate_tie(tmp_path):
    library = plain_library(
        item(tmp_path, "AAAA1111", "First Twin"), item(tmp_path, "BBBB2222", "Second Twin")
    )
    bib = existing_bib(tmp_path, ("k_second", same_pdf("{Second} twin")))
    result = bootstrap(bib, library)
    assert result.lock == {"zotero:user/BBBB2222": "k_second"}


@pytest.mark.parametrize(
    ("first", "second", "entry_title"),
    [
        ("First Twin", "Second Twin", None),
        ("First Twin", "", ""),
        ("First Twin", "Second Twin", "Third Twin"),
        ("Same Twin", "Same Twin", "Same Twin"),
    ],
)
def test_title_tie_unresolved_is_ambiguous(tmp_path, first, second, entry_title):
    library = plain_library(
        item(tmp_path, "AAAA1111", first),
        item(tmp_path, "BBBB2222", second, item_type="book"),
    )
    bib = existing_bib(tmp_path, ("k_twin", same_pdf(entry_title)))
    with pytest.raises(BootstrapRefused, match="ambiguous.*k_twin"):
        bootstrap(bib, library)


def test_two_entries_for_merged_item_stem_wins(tmp_path):
    library, merged = merged_library(tmp_path)
    bib = existing_bib(
        tmp_path,
        ("kapteyn_toward_nodate-1", same_pdf()),
        ("kapteyn_toward_nodate", same_pdf()),
    )
    result = bootstrap(bib, library, merged)
    assert result.lock == {SURVIVOR: "kapteyn_toward_nodate"}
    assert result.dropped == ("kapteyn_toward_nodate-1",)


@pytest.mark.parametrize(
    ("citekeys", "frozen"),
    [
        (("kapteyn_twin_2020-2", "smith_twin", "kapteyn_twin_2020-1"), "smith_twin"),
        (("b_twin", "a_twin-1", "a_twin"), "a_twin"),
    ],
)
def test_three_entries_unsuffixed_wins(tmp_path, citekeys, frozen):
    library, merged = merged_library(tmp_path)
    bib = existing_bib(tmp_path, *((citekey, same_pdf()) for citekey in citekeys))
    result = bootstrap(bib, library, merged)
    assert result.lock == {SURVIVOR: frozen}
    assert result.dropped == tuple(sorted(set(citekeys) - {frozen}))


def test_all_suffixed_smallest_wins(tmp_path):
    library, merged = merged_library(tmp_path)
    citekeys = ("twin-2", "twin-1", "other-3")
    bib = existing_bib(tmp_path, *((citekey, same_pdf()) for citekey in citekeys))
    result = bootstrap(bib, library, merged)
    assert result.lock == {SURVIVOR: "other-3"}
    assert result.dropped == ("twin-1", "twin-2")


def test_dropped_citekey_is_not_checked_but_frozen_one_is(tmp_path):
    library, merged = merged_library(tmp_path)
    bib = existing_bib(tmp_path, ("kapteyn_toward_nodate", same_pdf()), ("a:b", same_pdf()))
    assert bootstrap(bib, library, merged).dropped == ("a:b",)
    bib = existing_bib(tmp_path, ("a:b", same_pdf()), ("a:b-1", same_pdf()))
    with pytest.raises(BootstrapRefused, match="'a:b'.*contains ':'"):
        bootstrap(bib, library, merged)


def test_two_entries_for_plain_item_still_refused(tmp_path):
    library = plain_library(item(tmp_path, "AAAA1111", "Toward a Twin"))
    bib = existing_bib(
        tmp_path,
        ("kapteyn_toward_nodate", same_pdf()),
        ("kapteyn_toward_nodate-1", same_pdf()),
    )
    with pytest.raises(BootstrapRefused, match="claimed by entries kapteyn_toward_nodate, kap"):
        bootstrap(bib, library, {"zotero:user/BBBB2222"})


def test_duplicate_citekey_in_bibliography_still_refused(tmp_path):
    library, merged = merged_library(tmp_path)
    bib = existing_bib(
        tmp_path, ("kapteyn_toward_nodate", same_pdf()), ("kapteyn_toward_nodate", same_pdf())
    )
    with pytest.raises(BootstrapRefused, match="duplicate citekey kapteyn_toward_nodate"):
        bootstrap(bib, library, merged)
