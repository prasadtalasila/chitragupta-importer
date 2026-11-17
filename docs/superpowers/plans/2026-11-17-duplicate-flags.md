# Duplicate Rules, Flags and Scrub Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the revised duplicate rules (URL evidence, bootstrap URL ties, survivor with its own PDF, survivor's own PDF as main PDF, frozen key from the survivor's PDF match), put merging behind `--merge-duplicates` with refusal by default, add `--dry-run`, and replace real library data in docs and tests with invented data.

**Architecture:** `duplicates.py` gains URL evidence, extra groups and the new survivor rule; `bootstrap.py` gains URL-tie group discovery and the PDF-level preference for the frozen key; `run.py` and the CLI gain the two flags and a `DuplicatesFound` refusal.

**Tech Stack:** as before.

**Spec:** `docs/superpowers/specs/2026-11-13-zotero-importer-design.md`, section "Duplicate items within a library" (revised) and "CLI"; `docs/adr/0008-merge-duplicate-items-in-code.md`; `GLOSSARY.md` (duplicate group, survivor, dropped citekey).

## Global Constraints

- Same as `docs/superpowers/plans/2026-11-15-zotero-importer.md` Global Constraints (glossary terms, read-only Zotero, nothing outside `--out`, byte-identical reruns, frozen citekeys never move, UTF-8/LF, 25 statements per function, 250 lines per module, coverage >= 98%, commit message format).
- `duplicates.py` imports nothing Zotero-specific.
- No real data from `/workspace/papers` in the repository: invented titles, keys, names, DOIs, URLs only.

## Review Focus

1. A generic URL shared by several items with different titles, where each entry's title breaks its tie: no group forms: Task 1, `test_generic_url_with_title_breaks_groups_nothing`.
2. Two copies with different PDFs: the frozen key is the entry whose PDF is the survivor's, not the stem winner: Task 1, `test_frozen_key_follows_survivor_pdf`.
3. Survivor has no PDF but a member does: survivor is the member with the PDF (survivor rule), so main PDF is its own: Task 1, `test_survivor_is_copy_with_pdf`.
4. Duplicates present, no flag, with `--dry-run`: lists groups, exits 1, writes nothing: Task 2, `test_dry_run_without_flag_still_lists_and_fails`.
5. `--dry-run` with the flag on an empty `--out`: `--out` is not created: Task 2, `test_dry_run_creates_nothing`.

---

### Task 1: Revised duplicate and bootstrap rules

**Files:**
- Modify: `src/chitragupta_importer/duplicates.py`, `src/chitragupta_importer/bootstrap.py`
- Test: `tests/test_duplicates_rules.py`, `tests/test_bootstrap_url_ties.py` (new files; existing ones are near 250 lines)

**Interfaces:**
- Produces (duplicates.py): `pdf_then_oldest(items: Sequence[Item]) -> Item` (items with a PDF attachment that is a file first, then smallest `(date_added, item_id)`); `merge_duplicates(library: Library, survivor: Survivor, extra_groups: Sequence[Set[str]] = ()) -> tuple[Library, dict[str, str]]`; `duplicate_groups(library: Library, extra_groups: Sequence[Set[str]] = ()) -> list[tuple[str, ...]]` (sorted item IDs per group, groups sorted; used by the refusal listing).
- Produces (bootstrap.py): `url_tie_groups(existing: Path, library: Library) -> list[frozenset[str]]` (for each entry whose first matching level is URL with 2+ items left after the title tie-breaker, those items); `bootstrap(..., merged: Set[str] = frozenset(), survivor_pdfs: Mapping[str, Set[str]] = {})` where `survivor_pdfs` maps a merged survivor's item ID to the SHA-256 hashes of its own PDFs.
- Keep `oldest_added` (still used by tests and as a building block).

- [ ] **Step 1: Write the failing tests**

```python
def test_same_type_title_and_url_merged(): ...
def test_extra_group_merges_different_types_and_titles(): ...
def test_survivor_is_copy_with_pdf(tmp_path): ...            # older copy has no PDF → newer copy with PDF survives
def test_pdf_then_oldest_among_copies_with_pdf(tmp_path): ...
def test_merged_keeps_only_survivor_attachments_when_it_has_pdf(tmp_path): ...  # main_pdf == survivor's own
def test_merged_takes_member_attachments_when_survivor_has_no_pdf(tmp_path): ...
def test_duplicate_groups_listing_sorted(): ...
def test_url_tie_groups_found(tmp_path): ...                  # entry ties two items by URL, titles differ from entry
def test_generic_url_with_title_breaks_groups_nothing(tmp_path): ...
def test_frozen_key_follows_survivor_pdf(tmp_path):
    # copies A (survivor) and B with different PDFs; entries "smith_twins_2024" (B's PDF) and "smith_twins_2024-1" (A's PDF)
    # → frozen "smith_twins_2024-1", dropped ("smith_twins_2024",)
def test_identical_pdfs_fall_back_to_stem_rule(tmp_path): ...
```

- [ ] **Step 2: Run to verify they fail.** **Step 3: Implement.** URL evidence = exact `url` field, non-empty. Extra groups are unioned into the union-find before survivors are chosen. Frozen-key order: entries whose PDF hash is in `survivor_pdfs[survivor]` (exactly one → it); else the existing stem → unsuffixed → smallest rule over all claiming entries. **Step 4: Run tests, suite, linters.** **Step 5: Commit** ("Group duplicates by URL and keep the copy with a PDF").

---

### Task 2: Flags, dry run and refusal

**Files:**
- Modify: `src/chitragupta_importer/run.py`, `src/chitragupta_importer/__main__.py`, `scripts/check_zotero_data.py`, `README.md`
- Test: `tests/test_run_flags.py`, `tests/test_cli.py` (or a new CLI test file if near 250 lines)

**Interfaces:**
- Consumes: Task 1's functions.
- Produces: `class DuplicatesFound(ImportRefused)` whose message lists each group as `duplicate group: <item ID> (<title>), <item ID> (<title>)` lines; `import_zotero(data_dir, out_dir, bootstrap_from=None, merge_duplicates=False, dry_run=False) -> RunSummary`; `RunSummary.dry_run: bool = False`; CLI options `--merge-duplicates` and `--dry-run` (flags).

- [ ] **Step 1: Write the failing tests**

```python
def test_duplicates_without_flag_refuse_and_list(tmp_path): ...   # DuplicatesFound, every group listed, out/ untouched
def test_url_tie_groups_listed_without_flag_when_bootstrapping(tmp_path): ...
def test_merge_flag_merges(tmp_path): ...
def test_no_duplicates_flag_irrelevant(tmp_path): ...             # same bytes with and without the flag
def test_dry_run_writes_nothing(tmp_path): ...                    # existing out/ byte-identical; summary returned
def test_dry_run_creates_nothing(tmp_path): ...                   # absent out/ stays absent
def test_dry_run_without_flag_still_lists_and_fails(tmp_path): ...
def test_cli_flags(tmp_path): ...                                 # exit 1 + list on stderr; exit 0 with flag; dry-run line
```

- [ ] **Step 2–5:** run to fail; implement; run tests, suite, linters; commit ("Add --merge-duplicates and --dry-run").
  - Order: read → URL-tie groups (only when bootstrapping) → `duplicate_groups`; any group and no flag → `DuplicatesFound` before any write. With the flag: `merge_duplicates(library, pdf_then_oldest, extra_groups)`; `survivor_pdfs` from the survivors' own PDF hashes in the unmerged library.
  - Dry run: everything up to rendering; no `copy_pdf`, no `atomic_write`, no directory creation; `format_summary` starts with `dry run: nothing written`.
  - `check_zotero_data.py` gains `--merge-duplicates` passthrough and runs with `dry_run=True` (no out dir needed); README documents both flags.

- [ ] **Step 6: Real-data check.** `uv run python scripts/check_zotero_data.py --merge-duplicates /workspace/papers/Zotero /workspace/papers/bibliography-groups.bib` (adjust to the script's final arguments). Expected: no refusal; report aggregate numbers only. Also run without `--merge-duplicates` and report the number of groups listed.

---

### Task 3: Replace real library data with invented data

**Files:**
- Modify: any of `docs/`, `tests/`, `README.md`, `PROJECT.md`, `GLOSSARY.md` that contain real data.

- [ ] **Step 1: Find real data.** For every citekey, DOI, URL, person name and title in `bibliography-groups.bib` (read from `/workspace/papers`, never copied), `git grep -F` it in the repository (skip common words; check names and keys). List hits (paths and counts only) in the report.
- [ ] **Step 2: Replace** each hit with an invented equivalent of the same shape (a key with the same suffix pattern, a plausible fake DOI `10.9999/...`, `example.org` URLs, invented surnames with the same diacritics/edge cases where a test needs them). Keep every test's intent; keep docs examples meaningful.
- [ ] **Step 3: Re-run the search** until no hits; run the suite and linters. **Step 4: Commit** ("Replace real library data with invented examples").
