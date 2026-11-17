"""The import run: reading a library and writing the papers directory."""

from run_fixture import OSTRANDER, SMITH, build, existing_bibliography, snapshot

from chitragupta_importer.bootstrap import BootstrapResult
from chitragupta_importer.run import RunSummary, format_summary, import_zotero


def test_writes_papers_directory(tmp_path):
    out = tmp_path / "out"
    summary = import_zotero(build(tmp_path, OSTRANDER), out)
    assert sorted(p.name for p in out.iterdir()) == [
        "bibliography.bib",
        "citekeys.lock",
        "collections.lock",
        "files",
    ]
    assert (out / "files" / "ostrander_calibrating_2024.pdf").read_bytes() == b"%PDF-1"
    bib = (out / "bibliography.bib").read_text(encoding="utf-8")
    assert bib.startswith("@comment{cg-collections v1\ntide-pools\tTide Pools\n}\n\n@article{")
    assert "\tcg-collections = {tide-pools},\n" in bib
    assert (out / "citekeys.lock").read_text(encoding="utf-8") == (
        "zotero:user/AAAA1111\tostrander_calibrating_2024\n"
    )
    assert summary.included == 1
    assert summary.new_citekeys == ("ostrander_calibrating_2024",)
    assert summary.collection_changes == ("new tide-pools",)
    assert summary.bootstrap is None


def test_second_run_is_byte_identical(tmp_path):
    data_dir, out = build(tmp_path, OSTRANDER, SMITH), tmp_path / "out"
    import_zotero(data_dir, out)
    first = snapshot(out)
    summary = import_zotero(data_dir, out)
    assert snapshot(out) == first
    assert summary.new_citekeys == summary.collection_changes == ()


def test_adding_an_item_changes_only_its_lines(tmp_path):
    out = tmp_path / "out"
    import_zotero(build(tmp_path / "v1", OSTRANDER), out)
    bib_before = (out / "bibliography.bib").read_text(encoding="utf-8")
    lock_before = (out / "citekeys.lock").read_text(encoding="utf-8")
    import_zotero(build(tmp_path / "v2", OSTRANDER, SMITH), out)
    bib_after = (out / "bibliography.bib").read_text(encoding="utf-8")
    lock_after = (out / "citekeys.lock").read_text(encoding="utf-8")
    assert bib_after.startswith(bib_before)
    assert bib_after[len(bib_before) :].startswith("\n@article{smith_digital_2020,\n")
    assert bib_after.count("@article{") == 2
    assert lock_after == lock_before + "zotero:user/BBBB2222\tsmith_digital_2020\n"


def test_left_out_items_reported_by_reason(tmp_path):
    no_attachment = {"key": "CCCC3333", "fields": {"title": "Bare"}}
    missing = {"key": "DDDD4444", "pdfs": [("gone.pdf", None)]}
    missing_too = {"key": "EEEE5555", "pdfs": [("gone.pdf", None)]}
    data_dir = build(tmp_path, OSTRANDER, missing_too, no_attachment, missing)
    summary = import_zotero(data_dir, tmp_path / "out")
    assert summary.included == 1
    assert summary.left_out == {
        "no attachment": ("zotero:user/CCCC3333",),
        "PDF missing on disk": ("zotero:user/DDDD4444", "zotero:user/EEEE5555"),
    }
    assert "CCCC3333" not in (tmp_path / "out" / "citekeys.lock").read_text(encoding="utf-8")


def test_dormant_key_returns(tmp_path):
    out = tmp_path / "out"
    import_zotero(build(tmp_path / "v1", OSTRANDER, SMITH), out)
    lock = (out / "citekeys.lock").read_text(encoding="utf-8")
    without_pdf = {**SMITH, "pdfs": [("smith.pdf", None)]}
    summary = import_zotero(build(tmp_path / "v2", OSTRANDER, without_pdf), out)
    assert summary.left_out == {"PDF missing on disk": ("zotero:user/BBBB2222",)}
    assert (out / "citekeys.lock").read_text(encoding="utf-8") == lock
    assert "smith_digital_2020" not in (out / "bibliography.bib").read_text(encoding="utf-8")
    assert summary.unreferenced == ("smith_digital_2020.pdf",)
    assert (out / "files" / "smith_digital_2020.pdf").exists()
    summary = import_zotero(build(tmp_path / "v3", OSTRANDER, SMITH), out)
    assert "@article{smith_digital_2020," in (out / "bibliography.bib").read_text(encoding="utf-8")
    assert summary.new_citekeys == summary.unreferenced == ()


def test_retired_key_not_reused(tmp_path):
    out = tmp_path / "out"
    import_zotero(build(tmp_path / "v1", OSTRANDER, SMITH), out)
    same_stem = {**SMITH, "key": "CCCC3333"}
    summary = import_zotero(build(tmp_path / "v2", OSTRANDER, same_stem), out)
    assert summary.new_citekeys == ("smith_digital_2020-1",)
    lock = (out / "citekeys.lock").read_text(encoding="utf-8")
    assert "zotero:user/BBBB2222\tsmith_digital_2020\n" in lock
    assert "zotero:user/CCCC3333\tsmith_digital_2020-1\n" in lock


def test_bootstrap_freezes_existing_keys(tmp_path):
    out = tmp_path / "out"
    data_dir = build(tmp_path, OSTRANDER, SMITH)
    summary = import_zotero(data_dir, out, bootstrap_from=existing_bibliography(tmp_path))
    assert summary.bootstrap == BootstrapResult(
        {"zotero:user/AAAA1111": "io2024"}, ("lost",), (), ()
    )
    assert summary.new_citekeys == ("smith_digital_2020",)
    assert (out / "files" / "io2024.pdf").read_bytes() == b"%PDF-1"
    assert (out / "citekeys.lock").read_text(encoding="utf-8") == (
        "zotero:user/AAAA1111\tio2024\nzotero:user/BBBB2222\tsmith_digital_2020\n"
    )


def test_nothing_written_outside_out(tmp_path):
    data_dir = build(tmp_path, OSTRANDER, SMITH)
    data_before = snapshot(data_dir)
    outside_before = set(tmp_path.rglob("*"))
    out = tmp_path / "out"
    import_zotero(data_dir, out)
    assert snapshot(data_dir) == data_before
    gained = set(tmp_path.rglob("*")) - outside_before
    assert gained and all(out == p or out in p.parents for p in gained)


def test_format_summary_lists_every_line_in_order():
    summary = RunSummary(
        included=3,
        left_out={
            "no attachment": ("zotero:user/A",),
            "PDF missing on disk": ("zotero:user/B", "zotero:user/C"),
        },
        new_citekeys=("a_b_2020", "c_d_2021"),
        collection_changes=("new x", "retired y"),
        unreferenced=("old.pdf", "stray.pdf"),
        skipped_libraries=("zotero:group-7",),
        bootstrap=BootstrapResult({"i": "k"}, ("u1", "u2"), (), ("n1",), ("k-1", "k-2")),
        duplicates={"zotero:user/E": "zotero:user/D", "zotero:user/C2": "zotero:user/D"},
    )
    assert format_summary(summary) == (
        "included: 3\n"
        "left out (no attachment): 1\n"
        "left out (PDF missing on disk): 2\n"
        "duplicate zotero:user/C2 of zotero:user/D\n"
        "duplicate zotero:user/E of zotero:user/D\n"
        "new citekeys: 2\n"
        "new x\n"
        "retired y\n"
        "unreferenced files: 2: old.pdf, stray.pdf\n"
        "skipped libraries: zotero:group-7\n"
        "bootstrap: matched 1, unmatched 2, ambiguous 0, not included 1, dropped 2\n"
        "dropped citekey: k-1\n"
        "dropped citekey: k-2\n"
    )


def test_format_summary_omits_empty_optional_lines():
    summary = RunSummary(1, {}, (), (), (), (), None)
    assert format_summary(summary) == "included: 1\nnew citekeys: 0\nunreferenced files: 0\n"
