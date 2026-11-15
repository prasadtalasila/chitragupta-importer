# Zotero Importer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `chitragupta-importer zotero` reads one Zotero library read-only and writes a deterministic papers directory: `bibliography.bib` with frozen citekeys and `cg-collections`, `files/<citekey>.pdf`, `citekeys.lock` and `collections.lock`.

**Architecture:** A source reader turns `zotero.sqlite` into plain records; pure modules choose the main PDF, assign citekeys, freeze collection slugs and render BibTeX; one writer module touches the disk; `run.py` orchestrates an import run and the click command reports it.

**Tech Stack:** Python >=3.12, sqlite3 (stdlib), click, bibtexparser 1.4 (bootstrap only), pytest.

**Spec:** `docs/superpowers/specs/2026-11-13-zotero-importer-design.md`. Vocabulary is binding: `GLOSSARY.md`. Decisions are binding: `docs/adr/0001`–`0007`.

## Global Constraints

- Use the glossary's terms in code names, messages and docs: item, entry, item ID, collection ID, main PDF, included / left-out item, import run, citekey lock, collection lock, segment slug, slug path, display path, name table, dormant, retired, clash suffix.
- Never open the original `zotero.sqlite` writable; never write outside `--out`.
- Two runs on the same input give byte-identical output files.
- A citekey in the citekey lock never changes spelling or moves to another item ID; lock lines are never removed.
- Output text: UTF-8, LF line endings.
- Known Zotero `userdata` schema versions: `{121}`; anything else is refused.
- Item ID format: `zotero:user/<itemKey>`; collection ID: `zotero:user/<collectionKey>`. One import run reads exactly one library: the personal library (`libraries.type = 'user'`); group libraries are listed as skipped as `zotero:group-<groupID>`.
- Functions at most 25 statements, modules at most 250 lines (pylint enforces).
- New runtime dependency allowed: `bibtexparser>=1.4,<2` (bootstrap reads an existing bibliography). No other.
- Commit messages: imperative title; `- Verb ...` bullets at 72 columns; end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- After every task: `uv run pytest --cov` at 100% line and branch, `uv run ruff check . && uv run ruff format --check . && uv run pylint src tests` clean.

## Review Focus

1. Zotero is running while the import runs (a `zotero.sqlite-wal` file sits beside the database): the run still sees committed data and never touches the original: Task 1, `test_reads_copy_including_wal`.
2. A linked attachment with a Windows path (`C:\Users\...\x.pdf`, present in the Zotero data) on Linux: the item is left out as "PDF missing on disk", no crash: Task 2, `test_windows_linked_path_is_missing_on_disk`.
3. An item with no creator, no date and no title: gets a safe key `noauthor__nodate`, not a crash: Task 3, `test_stem_with_nothing`.
4. Braces and BibTeX specials (`{`, `}`, `%`, `&`, `#`, `_`) in a title or collection name: the bibliography stays brace-balanced and parses back with bibtexparser: Task 7, `test_specials_round_trip`.
5. `--out` does not exist yet, or holds files from an earlier run that this run no longer writes: the directory is created; stale files are reported, never deleted: Task 8, `test_creates_out_dir` and `test_reports_unreferenced_files`.

---

## File Structure

```text
src/chitragupta_importer/
  model.py            records: Creator, Attachment, Collection, Item, Library
  sources/__init__.py
  sources/zotero.py   read_library(data_dir) -> Library; schema check
  pdfs.py             main PDF choice and left-out reasons
  citekeys.py         safe-citekey rule, key rule, citekey lock, assignment
  bootstrap.py        match an existing bibliography to items
  slugs.py            segment slugs, collection lock, slug paths, changes
  bibtex.py           entry and bibliography rendering
  write.py            atomic writes, PDF copies, unreferenced files
  run.py              import_zotero(...) -> RunSummary
  __main__.py         adds the `zotero` command
tests/
  zotero_fixture.py   builds a synthetic zotero.sqlite + storage/
  fixtures/zotero_schema.sql
  test_*.py           one per module
scripts/check_zotero_data.py   by-hand checks against the Zotero data
```

---

### Task 1: Records and the Zotero reader

**Files:**
- Create: `src/chitragupta_importer/model.py`, `src/chitragupta_importer/sources/__init__.py`, `src/chitragupta_importer/sources/zotero.py`, `tests/zotero_fixture.py`, `tests/fixtures/zotero_schema.sql`
- Test: `tests/test_zotero_source.py`

**Interfaces:**
- Produces (in `model.py`, all `@dataclass(frozen=True)`):
  - `Creator(last: str, first: str, single_field: bool, role: str)`; `role` is Zotero's `creatorType` (`author`, `editor`, `contributor`, ...).
  - `Attachment(content_type: str | None, path: Path | None, file_name: str)`; `path` is absolute, or `None` when it cannot be resolved.
  - `Collection(collection_id: str, parent_id: str | None, name: str)`.
  - `Item(item_id: str, item_type: str, fields: Mapping[str, str], creators: tuple[Creator, ...], attachments: tuple[Attachment, ...], collection_ids: tuple[str, ...], tags: tuple[str, ...])`; `fields` keyed by Zotero field name (`title`, `date`, `DOI`, `publicationTitle`, ...).
  - `Library(items: tuple[Item, ...], collections: tuple[Collection, ...], skipped_libraries: tuple[str, ...])`; items sorted by `item_id`, collections by `collection_id`.
- Produces (in `sources/zotero.py`): `KNOWN_SCHEMA_VERSIONS = frozenset({121})`; `class UnknownSchema(Exception)`; `read_library(data_dir: Path) -> Library`.
- Produces (in `tests/zotero_fixture.py`): `ZoteroFixture(root: Path)` with `add_collection(key, name, parent_key=None, deleted=False)`, `add_item(key, item_type="journalArticle", fields=None, creators=(), pdfs=(), collections=(), tags=(), deleted=False)` where `pdfs` is a sequence of `(file_name, content: bytes | None)` (`None` = attachment row but no file), `add_group_library(group_id, name)`, `build(schema_version=121) -> Path` (returns the data directory).

- [ ] **Step 1: Write `tests/fixtures/zotero_schema.sql`** with exactly the `CREATE TABLE` statements of Zotero's public `userdata` schema for: `version`, `libraries`, `groups`, `items`, `itemTypes`, `deletedItems`, `itemData`, `fields`, `itemDataValues`, `creators`, `itemCreators`, `creatorTypes`, `itemAttachments`, `collections`, `collectionItems`, `deletedCollections`, `tags`, `itemTags`. No data from the Zotero data enters the repository.

- [ ] **Step 2: Write `tests/zotero_fixture.py`**: attachments are child items of type `attachment` with `itemAttachments.path = 'storage:<file_name>'`, `contentType = 'application/pdf'`, `linkMode = 1`, and the file written to `storage/<attachment key>/<file_name>`.

- [ ] **Step 3: Write the failing tests**

```python
def test_reads_item_fields_creators_tags_and_collections(tmp_path):
    fx = ZoteroFixture(tmp_path)
    fx.add_collection("COLLAAAA", "Digital Twin")
    fx.add_collection("COLLBBBB", "DT Platforms", parent_key="COLLAAAA")
    fx.add_item("ITEMAAAA", fields={"title": "A Twin", "date": "2024-02-01"},
                creators=[("Richstein", "Rebecca", "author")],
                pdfs=[("a.pdf", b"%PDF-1")], collections=["COLLBBBB"], tags=["twin"])
    lib = read_library(fx.build())
    item = lib.items[0]
    assert item.item_id == "zotero:user/ITEMAAAA"
    assert item.fields["title"] == "A Twin"
    assert item.creators == (Creator("Richstein", "Rebecca", False, "author"),)
    assert item.collection_ids == ("zotero:user/COLLBBBB",)
    assert item.tags == ("twin",)
    assert item.attachments[0].path.name == "a.pdf" and item.attachments[0].path.exists()
    assert lib.collections[1] == Collection("zotero:user/COLLBBBB", "zotero:user/COLLAAAA", "DT Platforms")

def test_skips_deleted_items_and_collections(tmp_path): ...   # deleted=True on both → absent
def test_refuses_unknown_schema(tmp_path):                     # build(schema_version=122)
    with pytest.raises(UnknownSchema, match="122"): ...
def test_lists_group_libraries_as_skipped(tmp_path):          # add_group_library(42, "Lab")
    assert lib.skipped_libraries == ("zotero:group-42",)
def test_reads_copy_including_wal(tmp_path):                  # original bytes and mtime unchanged after read;
    ...                                                       # a zotero.sqlite-wal beside it is copied too
def test_unresolvable_attachment_path_is_none(tmp_path):      # path 'attachments:x.pdf' → Attachment.path is None
```

- [ ] **Step 4: Run them to verify they fail**

Run: `uv run pytest tests/test_zotero_source.py -v`
Expected: FAIL on import of `chitragupta_importer.sources.zotero`.

- [ ] **Step 5: Implement `read_library`**
  - Copy `zotero.sqlite` (and `zotero.sqlite-wal` if present) into a `tempfile.TemporaryDirectory()` and open the copy; never open the original.
  - Check `SELECT version FROM version WHERE schema = 'userdata'` against `KNOWN_SCHEMA_VERSIONS`; the message names the version found.
  - Items: the user library's items whose type is not `attachment`, `note` or `annotation`, not in `deletedItems`.
  - Fields: `itemData` ⨝ `fields` ⨝ `itemDataValues`. Creators by `orderIndex`; `fieldMode = 1` → `single_field=True` with the name in `last`. Tags by name, sorted case-insensitively.
  - Attachments: child items of type `attachment` not in `deletedItems`. Path `storage:NAME` → `<data_dir>/storage/<attachment key>/NAME`; an absolute path (POSIX or a drive letter) → `Path(path)`; anything else → `None`.
  - Collections: user library, not in `deletedCollections`; an item's `collection_ids` are its direct memberships only, sorted.

- [ ] **Step 6: Run tests to verify they pass**, then full suite and linters as in Global Constraints.

- [ ] **Step 7: Commit** (title: "Read a Zotero library into plain records")

---

### Task 2: Main PDF and left-out reasons

**Files:**
- Create: `src/chitragupta_importer/pdfs.py`
- Test: `tests/test_pdfs.py`

**Interfaces:**
- Consumes: `Item`, `Attachment` (Task 1).
- Produces: `class LeftOutReason(StrEnum)` with members `NO_ATTACHMENT = "no attachment"`, `NO_PDF_ATTACHMENT = "no PDF attachment"`, `PDF_MISSING_ON_DISK = "PDF missing on disk"`; `main_pdf(item: Item) -> Path | LeftOutReason`.

- [ ] **Step 1: Write the failing tests**

```python
def test_no_attachment(): assert main_pdf(item()) is LeftOutReason.NO_ATTACHMENT
def test_html_only_is_no_pdf_attachment(): ...      # content_type "text/html", name "6.html"
def test_pdf_by_suffix_without_content_type(tmp_path): ...   # content_type None, "X.PDF" exists → chosen
def test_missing_pdf(): ...                          # path points nowhere → PDF_MISSING_ON_DISK
def test_windows_linked_path_is_missing_on_disk(): ...  # Path("C:\\Users\\p\\x.pdf") → PDF_MISSING_ON_DISK
def test_lowest_file_name_hash_wins(tmp_path):
    # among existing PDFs, the one whose sha256(file_name.encode()).hexdigest() is smallest
    ...
def test_equal_names_tie_broken_by_full_path(tmp_path): ...  # two "a.pdf" in different dirs → smaller str(path)
def test_missing_pdf_does_not_win_over_existing(tmp_path): ...
```

- [ ] **Step 2: Run to verify they fail** (`uv run pytest tests/test_pdfs.py -v`; FAIL on import).

- [ ] **Step 3: Implement.** A PDF attachment: `content_type == "application/pdf"` or `file_name` ending `.pdf` case-insensitively. Choose among PDF attachments whose `path` is not `None` and `is_file()`; key `(sha256(file_name), str(path))`, minimum wins.

- [ ] **Step 4: Run tests, suite, linters.** **Step 5: Commit** ("Choose the main PDF and name left-out reasons").

---

### Task 3: Safe citekeys and the key rule

**Files:**
- Create: `src/chitragupta_importer/citekeys.py`
- Test: `tests/test_citekeys.py`

**Interfaces:**
- Consumes: `Item`.
- Produces: `citekey_problem(citekey: str) -> str | None`; `class UnsafeCitekey(ValueError)`; `key_stem(item: Item) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("key", ["", " ", ".", "..", "a/b", "a\\b", "a:b", "a*b", "a?b",
                                 'a"b', "a<b", "a>b", "a|b", "a\x01b", "key.", "key ", "CON", "com1.x"])
def test_unsafe(key): assert citekey_problem(key) is not None
def test_safe(): assert citekey_problem("lehner_pattern_2023-1") is None

def test_stem_shape():
    it = item(creators=[("Schröder", "Kai", "author")],
              fields={"title": "The Characterizing of Twins", "date": "2024-02"})
    assert key_stem(it) == "schroder_characterizing_2024"
def test_stem_with_nothing(): assert key_stem(item()) == "noauthor__nodate"
def test_stem_uses_first_creator_of_any_role_when_no_author(): ...  # editor only → editor's last name
def test_stem_single_field_creator(): ...  # single_field "Microsoft Research" → "microsoftresearch"
def test_stem_drops_characters_outside_a_z_0_9_hyphen(): ...  # "microsoft/web-dev" → "microsoftweb-dev"
```

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement.**
  - `citekey_problem`: chitragupta's rule: empty or whitespace-only; `.` or `..`; any of `/ \ : * ? " < > |` or a control character `\x00`–`\x1f`; ends in `.` or space; the part before the first `.`, upper-cased, is `CON`, `PRN`, `AUX`, `NUL`, `COM1`–`COM9` or `LPT1`–`LPT9`. Return a reason string naming the problem.
  - `key_stem`: `<creator>_<titleword>_<year>`, each part ASCII-folded (NFKD, drop combining marks), lower-cased, then every character outside `[a-z0-9-]` removed.
    - creator: last name of the first `author` by order, else the first creator; `noauthor` if none.
    - titleword: the first word of `title` after removing these whole words (case-insensitive): `a an the some from on in to of do with der die das ein eine einer eines einem einen un une la le l el las los al uno una unos unas de des del d`; empty if no title.
    - year: the first four-digit run in `date`; `nodate` if none.
  - The rule is pinned further by Task 10's match-rate check; adjust only `key_stem`'s normalisation there, never the shape.

- [ ] **Step 4: Run tests, suite, linters.** **Step 5: Commit** ("Add the safe-citekey rule and the key rule").

---

### Task 4: The citekey lock and key assignment

**Files:**
- Modify: `src/chitragupta_importer/citekeys.py`
- Test: `tests/test_citekey_lock.py`

**Interfaces:**
- Produces: `parse_citekey_lock(text: str) -> dict[str, str]` (item ID → citekey); `format_citekey_lock(lock: Mapping[str, str]) -> str` (lines `<item ID>\t<citekey>\n`, sorted by item ID); `assign_citekeys(stems: Mapping[str, str], lock: Mapping[str, str]) -> tuple[dict[str, str], list[str]]` returning `(updated lock, new item IDs in assignment order)`. `stems` covers the included items only.

- [ ] **Step 1: Write the failing tests**

```python
def test_known_item_keeps_key():
    lock, new = assign_citekeys({"z:1": "smith_x_2020"}, {"z:1": "old_key_1999"})
    assert lock == {"z:1": "old_key_1999"} and new == []
def test_new_item_gets_stem(): ...
def test_clash_in_one_run_by_item_id_order():
    lock, _ = assign_citekeys({"z:2": "a_b_2020", "z:1": "a_b_2020", "z:3": "a_b_2020"}, {})
    assert lock == {"z:1": "a_b_2020", "z:2": "a_b_2020-1", "z:3": "a_b_2020-2"}
def test_clash_skips_spellings_in_lock_including_dormant_and_retired():
    lock, _ = assign_citekeys({"z:9": "a_b_2020"}, {"z:1": "a_b_2020", "z:2": "a_b_2020-1"})
    assert lock["z:9"] == "a_b_2020-2"
def test_lines_never_removed(): ...      # lock entries absent from stems stay in the result
def test_unsafe_new_key_raises(): ...    # stem "con" → UnsafeCitekey naming "z:1"
def test_lock_round_trip(): assert parse_citekey_lock(format_citekey_lock(m)) == m
def test_lock_text_is_sorted_tab_lf(): ...
```

- [ ] **Step 2–5:** run to fail; implement; run tests, suite, linters; commit ("Freeze citekeys in the citekey lock").

---

### Task 5: Bootstrap from an existing bibliography

**Files:**
- Create: `src/chitragupta_importer/bootstrap.py`
- Modify: `pyproject.toml` (add `bibtexparser>=1.4,<2`), `uv.lock`
- Test: `tests/test_bootstrap.py`

**Interfaces:**
- Consumes: `Library`, `main_pdf`, `citekey_problem`.
- Produces: `@dataclass(frozen=True) BootstrapResult(lock: dict[str, str], unmatched: tuple[str, ...], ambiguous: tuple[str, ...], not_included: tuple[str, ...])` (tuples of citekeys, sorted); `class BootstrapRefused(Exception)`; `bootstrap(existing: Path, library: Library) -> BootstrapResult`.

- [ ] **Step 1: Write the failing tests**

```python
def test_matches_by_pdf_content_hash(tmp_path): ...   # entry file= points at a PDF with the same bytes as the item's
def test_falls_back_to_doi_then_url_then_title(tmp_path): ...
def test_doi_normalised(): ...        # "https://doi.org/10.1/ABC" matches "10.1/abc"
def test_title_normalised(): ...      # "{Digital} {Twin}s" matches "Digital Twins" (casefold, braces and non-alnum dropped)
def test_unmatched_listed_without_lock_line(tmp_path): ...
def test_ambiguous_entry_refuses(tmp_path):   # one entry matches two items at its first matching level
    with pytest.raises(BootstrapRefused, match="ambiguous"): ...
def test_item_claimed_by_two_entries_refuses(tmp_path): ...
def test_matched_item_without_pdf_gets_no_lock_line(tmp_path):
    assert result.not_included == ("kapteyn_toward_nodate",) and result.lock == {}
def test_unsafe_frozen_key_refuses(tmp_path): ...   # entry key "a:b"
```

- [ ] **Step 2–5:** run to fail; implement; run tests, suite, linters; commit ("Bootstrap the citekey lock from an existing bibliography").
  - Parse with bibtexparser 1.4 (`common_strings=True`); PDFs of an entry: `file` field split on unescaped `;`, each `desc:path:mime` split on unescaped `:`, `\:` and `\;` unescaped, path relative to the existing bibliography's directory; keep those whose mime contains `pdf`.
  - Hash every PDF attachment of every item (not only the main PDF) with SHA-256 of the file content.
  - Levels in order: PDF hash, DOI, URL (exact), title; the first level with any match decides; more than one item at that level is ambiguous.

---

### Task 6: Collection slugs and the collection lock

**Files:**
- Create: `src/chitragupta_importer/slugs.py`
- Test: `tests/test_slugs.py`

**Interfaces:**
- Consumes: `Collection`.
- Produces:
  - `segment_slug(name: str) -> str`.
  - `@dataclass(frozen=True) CollectionRecord(collection_id: str, parent_id: str | None, slug: str, name: str, status: Literal["live", "retired"])`.
  - `parse_collection_lock(text: str) -> dict[str, CollectionRecord]`; `format_collection_lock(records) -> str` (tab-separated `<collection ID>\t<parent ID or ->\t<segment slug>\t<name>\t<live|retired>\n`, sorted by collection ID; tab and newline in a name become a space).
  - `update_collections(lock: Mapping[str, CollectionRecord], collections: Sequence[Collection], used: Set[str]) -> tuple[dict[str, CollectionRecord], list[str]]` returning `(new lock, change lines)`; `used` = collection IDs directly holding an included item.
  - `slug_paths(records: Mapping[str, CollectionRecord]) -> dict[str, str]` (collection ID → slug path, live records only).
  - `display_paths(records) -> dict[str, str]` (collection ID → display path with ` / `).
  - `name_table_rows(records: Mapping[str, CollectionRecord], used: Set[str]) -> list[tuple[str, str]]`: `(slug path, own name)` for every live record in `used` or an ancestor of one, sorted by slug path.

- [ ] **Step 1: Write the failing tests**

```python
@pytest.mark.parametrize("name,slug", [("Digital Twin", "digital-twin"), ("Industry 5.0", "industry-5-0"),
    ("Schröder & Co", "schroder-co"), ("Edge/Cloud", "edge-cloud"), ("***", "collection")])
def test_segment_slug(name, slug): assert segment_slug(name) == slug

def test_ancestors_of_used_collections_are_recorded(): ...
def test_collection_holding_only_left_out_items_gets_no_record(): ...
def test_rename_keeps_slug_and_reports():
    # lock has COLL-B "Plants DT"/"plants-dt"; library renames it "Plant Digital Twins"
    assert new["zotero:user/B"].slug == "plants-dt"
    assert "renamed Plants DT -> Plant Digital Twins" in changes
def test_move_keeps_segment_and_changes_path(): ...   # "moved digital-twin.medical -> digital-twin.use-cases.medical-1"
def test_sibling_clash_including_case(): ...          # "Datasets" and "datasets" under one parent → datasets, datasets-1 by collection ID
def test_gone_collection_is_retired_and_kept(): ...
def test_recreated_collection_takes_retired_slug(): ... # same parent, same name, new ID → retired slug reused
def test_new_collection_reported(): ...                # "new digital-twin.dt-platforms"
def test_lock_round_trip(): ...
def test_name_table_rows_cover_used_and_ancestors_only(): ...
```

- [ ] **Step 2–5:** run to fail; implement; run tests, suite, linters; commit ("Freeze collection slugs in the collection lock").
  - `segment_slug`: NFKD, drop combining marks, lower-case, each run outside `[a-z0-9]` → `-`, strip `-`, empty → `collection`.
  - New records are processed in collection-ID order, parents before children. A clash among siblings (live or retired records with the same parent) takes the next free `-N`, starting at `-1`.
  - Change line formats, exactly: `new <slug path>`, `renamed <old name> -> <new name>`, `moved <old slug path> -> <new slug path>`, `retired <slug path>`; sorted.

---

### Task 7: BibTeX rendering

**Files:**
- Create: `src/chitragupta_importer/bibtex.py`
- Test: `tests/test_bibtex.py`

**Interfaces:**
- Consumes: `Item`.
- Produces: `render_entry(citekey: str, item: Item, slug_paths: Sequence[str]) -> str`; `render_name_table(rows: Sequence[tuple[str, str]]) -> str` (slug path, own name); `render_bibliography(name_table: str, entries: Sequence[str]) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
def test_article_entry_exact():
    text = render_entry("richstein_characterizing_2024", article_item(), ["digital-twin.dt-platforms"])
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
        "}\n")
@pytest.mark.parametrize("zotero_type,bibtex_type", [("journalArticle", "article"), ("conferencePaper", "inproceedings"),
    ("bookSection", "incollection"), ("book", "book"), ("report", "techreport"), ("thesis", "phdthesis"),
    ("webpage", "misc"), ("preprint", "misc"), ("computerProgram", "misc")])
def test_entry_types(zotero_type, bibtex_type): ...
def test_single_field_creator_braced(): ...   # author = {{Microsoft Research}}
def test_editor_and_contributor_fields(): ...  # editor, collaborator
def test_specials_round_trip():
    # title "50% of {A} & B_c #1", collection name with "{" → bibtexparser parses the bibliography back,
    # title value equal after unescaping, name table braces balanced
    ...
def test_name_table_block(): assert render_name_table([("digital-twin", "Digital Twin")]) == \
    "@comment{cg-collections v1\ndigital-twin\tDigital Twin\n}\n"
def test_name_table_escapes_braces(): ...   # "A {B}" → "A \\{B\\}"
def test_bibliography_is_name_table_then_entries_blank_line_separated(): ...
```

- [ ] **Step 2–5:** run to fail; implement; run tests, suite, linters; commit ("Render entries, the name table and the bibliography").
  - Field order, exactly: `address type series title volume edition copyright isbn issn shorttitle url doi abstract language number urldate institution school booktitle journal publisher author collaborator editor month year note keywords pages file cg-collections`; empty fields are omitted.
  - Entry types: `journalArticle magazineArticle newspaperArticle → article`; `conferencePaper → inproceedings`; `bookSection → incollection`; `book → book`; `report → techreport`; `thesis → phdthesis`; `manuscript → unpublished`; everything else `misc`.
  - Fields: `title←title`, `shorttitle←shortTitle`, `abstract←abstractNote`, `url←url`, `doi←DOI` (or a `DOI: …` line in `extra`), `issn←ISSN`, `isbn←ISBN`, `language`, `copyright←rights`, `volume`, `number←issue|number|reportNumber`, `pages`, `series`, `address←place`, `edition`, `journal←publicationTitle` (article types), `booktitle←publicationTitle|proceedingsTitle|bookTitle` (other types), `publisher←publisher|repository|company`, `institution←institution` (report), `school←university` (thesis), `type←reportType|thesisType|genre`, `note←extra`, `urldate←` date part of `accessDate`, `month`/`year←date`, `keywords←tags` joined `, `, `author|editor|collaborator←` creators by role (`contributor → collaborator`; other non-author, non-editor roles omitted).
  - Values: `month` is the unbraced three-letter macro (`jan` … `dec`). `title` and `booktitle`: brace every word after the first that contains an upper-case letter. Escape `# $ % & _` with `\` in every field except `url`, `doi` and `file`; replace `{`/`}` that would unbalance a value with `\{`/`\}`. Creators: `Last, First` joined ` and `; single-field names braced `{Name}`. `file`: `Full Text PDF:files/<citekey>.pdf:application/pdf`.
  - Task 10 measures the remaining differences against the Zotero data; change these rules there only with a ledgered ruling.

---

### Task 8: Writing the papers directory

**Files:**
- Create: `src/chitragupta_importer/write.py`
- Test: `tests/test_write.py`

**Interfaces:**
- Produces: `atomic_write(path: Path, text: str) -> None`; `copy_pdf(src: Path, dest: Path) -> bool` (True if written); `unreferenced_files(files_dir: Path, written: Set[str]) -> list[str]` (sorted names).

- [ ] **Step 1: Write the failing tests**

```python
def test_atomic_write_creates_parents_and_replaces(tmp_path): ...
def test_atomic_write_leaves_old_file_on_failure(tmp_path, monkeypatch): ...  # os.replace raises → old content intact, no temp left
def test_atomic_write_is_utf8_lf(tmp_path): ...   # "ä\n" → bytes b"\xc3\xa4\n"
def test_copy_pdf_skips_identical(tmp_path): ...  # second copy returns False, mtime unchanged
def test_copy_pdf_replaces_changed(tmp_path): ...
def test_creates_out_dir(tmp_path): ...
def test_reports_unreferenced_files(tmp_path): ... # files/old.pdf not in written → ["old.pdf"], file still there
```

- [ ] **Step 2–5:** run to fail; implement (temp file in the target's directory, then `os.replace`; `newline="\n"`); run tests, suite, linters; commit ("Write the papers directory atomically").

---

### Task 9: The import run and the `zotero` command

**Files:**
- Create: `src/chitragupta_importer/run.py`
- Modify: `src/chitragupta_importer/__main__.py`
- Test: `tests/test_run.py`, `tests/test_cli.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `@dataclass(frozen=True) RunSummary(included: int, left_out: Mapping[str, tuple[str, ...]], new_citekeys: tuple[str, ...], collection_changes: tuple[str, ...], unreferenced: tuple[str, ...], skipped_libraries: tuple[str, ...], bootstrap: BootstrapResult | None)`; `class ImportRefused(Exception)`; `import_zotero(data_dir: Path, out_dir: Path, bootstrap_from: Path | None = None) -> RunSummary`; `format_summary(summary: RunSummary) -> str`.

- [ ] **Step 1: Write the failing tests** (`tests/test_run.py`, using `ZoteroFixture`)

```python
def test_writes_papers_directory(tmp_path):
    summary = import_zotero(data_dir, out)
    assert sorted(p.name for p in out.iterdir()) == ["bibliography.bib", "citekeys.lock", "collections.lock", "files"]
    assert (out / "files" / "richstein_characterizing_2024.pdf").read_bytes() == b"%PDF-1"
def test_second_run_is_byte_identical(tmp_path): ...
def test_adding_an_item_changes_only_its_lines(tmp_path): ...   # diff of bibliography = one new entry; lock = one new line
def test_left_out_items_reported_by_reason(tmp_path): ...
def test_dormant_key_returns(tmp_path): ...  # remove PDF → left out, lock line kept; restore → same key
def test_retired_key_not_reused(tmp_path): ... # delete item; new item with same stem gets "-1"
def test_bootstrap_with_existing_lock_refused(tmp_path):
    with pytest.raises(ImportRefused, match="citekeys.lock"): ...
def test_bootstrap_freezes_existing_keys(tmp_path): ...
def test_refusal_writes_nothing(tmp_path): ...  # unknown schema → out dir untouched
def test_nothing_written_outside_out(tmp_path): ... # data dir bytes unchanged; only out/ gained files
```

and in `tests/test_cli.py`:

```python
def test_zotero_command_prints_summary(tmp_path): ...   # exit 0; "included: 1" in output
def test_zotero_command_refusal_exits_nonzero(tmp_path): ...  # unknown schema → exit 1, message on stderr
```

- [ ] **Step 2–5:** run to fail; implement; run tests, suite, linters; commit ("Add the zotero import run and command").
  - Order: read library → main PDFs → (bootstrap: refuse if `citekeys.lock` exists; else seed the lock) → assign citekeys → update collections → render → copy PDFs → write bibliography → write `citekeys.lock`, then `collections.lock`, last. All refusals happen before the first write.
  - Command: `chitragupta-importer zotero --data-dir DIR --out DIR [--bootstrap FILE]` (`click.Path(exists=True, file_okay=False)` for `--data-dir`, `file_okay=False` for `--out`, `exists=True, dir_okay=False` for `--bootstrap`). `UnknownSchema`, `UnsafeCitekey`, `BootstrapRefused`, `ImportRefused` → `click.ClickException` (exit 1).
  - Summary lines, in this order: `included: N`, one `left out (<reason>): N` per reason, `new citekeys: N`, each collection change, `unreferenced files: N` with names, `skipped libraries: …`, and for bootstrap `bootstrap: matched N, unmatched N, ambiguous N, not included N`.

---

### Task 10: Checks against the Zotero data, and docs

**Files:**
- Create: `scripts/check_zotero_data.py`
- Modify: `README.md`, `PROJECT.md`

- [ ] **Step 1: Write `scripts/check_zotero_data.py ZOTERO_DATA_DIR EXISTING_BIB OUT_DIR`**: runs `import_zotero(..., bootstrap_from=EXISTING_BIB)` into `OUT_DIR` (must be empty or absent) and prints: bootstrap counts; the key-rule match rate (`key_stem` of each matched item vs its frozen key with any `-N` stripped); per field name, how many frozen entries differ between `EXISTING_BIB` and the output, ignoring `file`, `groups` and `cg-collections`. Not run in CI; not covered by the coverage bar (put it outside `src/`).

- [ ] **Step 2: Run it on the Zotero data**

Run: `uv run python scripts/check_zotero_data.py /workspace/papers/Zotero /workspace/papers/bibliography-groups.bib "$SCRATCH/out"` (where `$SCRATCH` is a scratch directory outside the repository)
Expected: matched 497, not included 146 (± the 1 missing PDF); key-rule match rate ≥ 99%; a per-field difference table.

- [ ] **Step 3: Close the gaps the table shows** in `key_stem` and `bibtex.py`, each change with a unit test first; ledger each as a ruling; rerun until the rate and the table stop improving. Record the final numbers in the PR description.

- [ ] **Step 4: Docs.** README: replace "Status: scaffold only" with usage (`chitragupta-importer zotero --data-dir ~/Zotero --out papers --bootstrap old.bib` for the first run, without `--bootstrap` after) and the output layout. PROJECT.md: add `scripts/check_zotero_data.py` under "Verifying a change" for changes to the key rule or BibTeX rendering.

- [ ] **Step 5: Full check and commit** ("Check the importer against real Zotero data and document usage").
