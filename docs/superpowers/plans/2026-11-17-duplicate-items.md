# Duplicate Items Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge duplicate items within one library before an import run, freeze one citekey per merged item in bootstrap, and break non-duplicate bootstrap ties by title, so the first run on the Zotero data succeeds.

**Architecture:** A source-neutral `duplicates.py` turns a `Library` into a deduplicated `Library` plus a map of non-survivors to survivors, using a pluggable survivor rule. The import run applies it right after reading; bootstrap gains a title tie-breaker and the dropped-citekey rule for merged items.

**Tech Stack:** as before (Python >=3.12, click, bibtexparser 1.4, pytest).

**Spec:** `docs/superpowers/specs/2026-11-13-zotero-importer-design.md`, section "Duplicate items within a library"; `docs/adr/0008-merge-duplicate-items-in-code.md`; `GLOSSARY.md` (duplicate group, survivor, dropped citekey).

## Global Constraints

- Same as `docs/superpowers/plans/2026-11-15-zotero-importer.md` Global Constraints (glossary terms, read-only Zotero, nothing outside `--out`, byte-identical reruns, frozen citekeys never move, UTF-8/LF, 25 statements per function, 250 lines per module, coverage >= 98%, commit message format).
- `duplicates.py` must not import anything Zotero-specific; it works on `model` records only.

## Review Focus

1. A duplicate group whose oldest item has no PDF while a newer one does: the survivor is the oldest and is still included, with the newer item's PDF: Task 1, `test_survivor_inherits_member_pdf`.
2. Two items with the same title and type but no shared DOI or PDF (e.g. two editions): not merged: Task 1, `test_same_title_without_shared_identifier_not_merged`.
3. Three entries for one merged item where none equals the key-rule stem: the unsuffixed one is frozen, two dropped: Task 2, `test_three_entries_unsuffixed_wins`.
4. Two entries claiming one ordinary (non-merged) item: still refused: Task 2, `test_two_entries_for_plain_item_still_refused`.
5. A rerun after the user later merges the same group in Zotero with the default master: same citekey, no retired line: Task 3, `test_later_zotero_merge_keeps_key`.

---

### Task 1: `date_added` and the duplicate grouping

**Files:**
- Modify: `src/chitragupta_importer/model.py`, `src/chitragupta_importer/sources/zotero.py`, `tests/zotero_fixture.py`
- Create: `src/chitragupta_importer/duplicates.py`
- Test: `tests/test_duplicates.py`, and one reader test in `tests/test_zotero_source.py` (or a new file if it is near 250 lines)

**Interfaces:**
- Produces: `Item.date_added: str = ""` (new last field with a default; Zotero value of `items.dateAdded`, `"YYYY-MM-DD HH:MM:SS"`); `ZoteroFixture.add_item(..., date_added="2020-01-01 00:00:00")`.
- Produces (in `duplicates.py`): `Survivor = Callable[[Sequence[Item]], Item]`; `oldest_added(items: Sequence[Item]) -> Item` (smallest `(date_added, item_id)`); `merge_duplicates(library: Library, survivor: Survivor) -> tuple[Library, dict[str, str]]` returning `(library with each group replaced by its merged survivor, {non-survivor item ID: survivor item ID})`.

- [ ] **Step 1: Write the failing tests**

```python
def test_reader_reads_date_added(tmp_path): ...        # fixture date_added → Item.date_added
def test_same_type_title_and_doi_merged(): ...          # two items, DOI "10.1/A" and "https://doi.org/10.1/a"
def test_same_type_title_and_pdf_bytes_merged(tmp_path): ...
def test_grouping_is_transitive(tmp_path): ...          # A~B by DOI, B~C by PDF → one group of three
def test_same_title_without_shared_identifier_not_merged(): ...
def test_different_type_not_merged(): ...
def test_oldest_added_wins_ties_by_item_id(): ...
def test_merged_item_unions_attachments_collections_tags(tmp_path):
    # survivor's own attachments first, then others in item-ID order; collections and tags sorted unions;
    # survivor keeps its item ID, type, fields, creators
def test_survivor_inherits_member_pdf(tmp_path): ...    # main_pdf(merged) is the newer member's PDF
def test_returns_non_survivor_map_and_sorted_items(): ...
def test_custom_survivor_rule_is_used(): ...            # pass lambda items: max(items, key=...)
```

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement.** Title normalisation: case-fold, keep letters and digits only (same as bootstrap's title key; share one helper, e.g. move it to a small `normalise.py` with the DOI normaliser, and import it from both). DOI from field `DOI` or a `DOI:` line in `extra`. PDF bytes: SHA-256 of every PDF attachment (`pdfs.is_pdf`) whose path is a file. Group with union-find over items keyed by `(item_type, title)` sharing any DOI or PDF hash; empty title never groups.

- [ ] **Step 4: Run tests, suite, linters.** **Step 5: Commit** ("Merge duplicate items with a pluggable survivor rule").

---

### Task 2: Bootstrap on merged items

**Files:**
- Modify: `src/chitragupta_importer/bootstrap.py`
- Test: `tests/test_bootstrap_duplicates.py`

**Interfaces:**
- Consumes: `merge_duplicates` output (a merged `Library`, the non-survivor map); `key_stem`.
- Produces: `bootstrap(existing: Path, library: Library, merged: Set[str] = frozenset()) -> BootstrapResult`, where `merged` holds the item IDs of survivors that absorbed at least one other item; `BootstrapResult` gains `dropped: tuple[str, ...] = ()` (sorted citekeys).

- [ ] **Step 1: Write the failing tests**

```python
def test_title_breaks_non_duplicate_tie(tmp_path): ...       # one PDF on two items with different titles → entry goes to its title's item
def test_title_tie_unresolved_is_ambiguous(tmp_path): ...    # no or several title matches → BootstrapRefused "ambiguous"
def test_two_entries_for_merged_item_stem_wins(tmp_path):
    # survivor's key_stem == "abernathy_toward_nodate"; entries "abernathy_toward_nodate-1" and "abernathy_toward_nodate"
    assert result.lock == {survivor_id: "abernathy_toward_nodate"} and result.dropped == ("abernathy_toward_nodate-1",)
def test_three_entries_unsuffixed_wins(tmp_path): ...        # none equals the stem → the one without -N; two dropped
def test_all_suffixed_smallest_wins(tmp_path): ...
def test_two_entries_for_plain_item_still_refused(tmp_path): ...
def test_duplicate_citekey_in_bibliography_still_refused(tmp_path): ...
```

- [ ] **Step 2–5:** run to fail; implement; run tests, suite, linters; commit ("Freeze one citekey per merged item in bootstrap").
  - Tie-breaker applies at the first level with any match, before deciding ambiguity: candidates whose normalised title equals the entry's normalised title; exactly one → that item.
  - Clash suffix test: a citekey ends in `-<digits>`.
  - The duplicate-citekey refusal (same citekey twice in the bibliography) stays as is.

---

### Task 3: Import run, summary and checks

**Files:**
- Modify: `src/chitragupta_importer/run.py`, `scripts/check_zotero_data.py`, `README.md`
- Test: `tests/test_run_duplicates.py`, `tests/test_cli.py` if the summary changes its output

**Interfaces:**
- Consumes: `merge_duplicates`, `oldest_added`, the new `bootstrap` signature.
- Produces: `RunSummary.duplicates: Mapping[str, str] = {}` (non-survivor → survivor); summary lines, after the left-out lines: one `duplicate <item ID> of <item ID>` per non-survivor, sorted; the bootstrap line gains `, dropped N` and is followed by one `dropped citekey: <citekey>` line per dropped key.

- [ ] **Step 1: Write the failing tests**

```python
def test_duplicates_merged_before_import(tmp_path): ...  # two duplicate items → one entry, summary has the duplicate line
def test_bootstrap_with_duplicates_freezes_one_key(tmp_path): ...  # dropped line printed
def test_later_zotero_merge_keeps_key(tmp_path):
    # run 1 with duplicates A (older) and B; then delete B in the fixture (Zotero merge with default master)
    # and give A B's PDF; run 2 → same citekey for A, no "retired"/new-key change
def test_rerun_with_duplicates_is_byte_identical(tmp_path): ...
```

- [ ] **Step 2–5:** run to fail; implement (call `merge_duplicates(read_library(...), oldest_added)` right after reading; pass the merged survivors set to `bootstrap`); update `check_zotero_data.py` to print duplicate and dropped counts; README: one paragraph on duplicates; run tests, suite, linters; commit ("Merge duplicate items in the import run").

- [ ] **Step 6: Real-data check.** Run `scripts/check_zotero_data.py /workspace/papers/Zotero /workspace/papers/bibliography-groups.bib <scratch out dir>`. Expected: no refusal; 34 duplicate groups merged (about 36 duplicate lines); dropped citekeys about 25; key-rule match rate still 100% on frozen keys. Record aggregate numbers only in the report.
