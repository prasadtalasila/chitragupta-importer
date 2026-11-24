# Citekey Renames Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record each citekey that a paper has left behind in `papers/renames.lock` and publish them to chitragupta as a `@comment{cg-renames v1 ...}` block, renaming frozen citekeys longer than 30 characters on the way.

**Architecture:** A new `renames.py` owns the rename lock, chain resolution, the block and the rename sources that need the lock (B, C). Bootstrap reports source A, the Zotero reader exposes `dc:replaces` for source C, and `citekeys.py` gains source D. `run.py` wires them between key assignment and rendering.

**Tech Stack:** Python ≥3.12, uv, pytest with 100% line and branch coverage, ruff, pylint. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-11-24-citekey-renames-design.md`

## Global Constraints

- Functions at most 25 statements; modules at most 250 lines (pylint enforces). `bibtex.py` (235), `bootstrap.py` (222), `run.py` (207) and `sources/zotero.py` (207) are near the cap: put new logic in `renames.py`.
- 100% line and branch coverage; a failing test first for every behaviour.
- Lock lines are never removed; a citekey never moves to another paper.
- Case D threshold: a citekey **longer than 30** characters (`MAX_FROZEN_LENGTH = 30`).
- Reserved old spelling: pseudo item ID `renamed:<old>` with value `<old>`, like `dropped:`.
- Block: `@comment{cg-renames v1\n` + `<old>\t<new>\n` rows sorted by old key + `}\n`, placed after the `cg-collections` block; no rows, no block.
- `renames.lock`: `<old>\t<new>` lines sorted by old key; first row for an old key wins; written only when it has rows.
- Version 0.3.0 (MINOR).
- Never commit output from the real library.

## Review Focus

1. A dropped key that fails `citekey_problem` (dropped keys are not checked): kept in `renames.lock`, left out of the block. Test in Task 1.
2. A successor that is dormant (its item lost its PDF): the row stays in `renames.lock`, is absent from the block, and returns when the item is included. Test in Task 1.
3. A long frozen key whose item is dormant: not renamed until the item is included again. Test in Task 4.
4. A second run with no library change: every file byte-identical and no rows added. Test in Task 5.
5. A `dc:replaces` object naming a group-library item or an unparseable URI: ignored. Test in Task 3.

---

### Task 1: The rename lock and the `cg-renames` block

**Files:**
- Create: `src/chitragupta_importer/renames.py`
- Test: `tests/test_renames.py`

**Interfaces:**
- Produces:
  - `parse_renames_lock(text: str) -> dict[str, str]` (old → new; ValueError for a line without a tab or an old key listed twice)
  - `format_renames_lock(renames: Mapping[str, str]) -> str`
  - `add_renames(renames: Mapping[str, str], rows: Iterable[tuple[str, str]]) -> tuple[dict[str, str], list[tuple[str, str]]]` (updated lock, rows actually added, in input order; skips an existing old key and `old == new`)
  - `block_rows(renames: Mapping[str, str], entry_keys: Set[str]) -> list[tuple[str, str]]`
  - `render_renames_block(rows: Sequence[tuple[str, str]]) -> str`

- [ ] **Step 1: Write the failing tests**

```python
def test_lock_round_trip_sorted_by_old_key():
    text = "b\tc\na\tc\n"
    assert parse_renames_lock(text) == {"a": "c", "b": "c"}
    assert format_renames_lock({"b": "c", "a": "c"}) == "a\tc\nb\tc\n"

@pytest.mark.parametrize("text", ["a c\n", "a\tb\na\tc\n"])
def test_malformed_lock_is_a_value_error(text):
    with pytest.raises(ValueError):
        parse_renames_lock(text)

def test_first_row_for_an_old_key_wins_and_self_rows_are_skipped():
    lock, added = add_renames({"a": "b"}, [("a", "z"), ("c", "c"), ("d", "b")])
    assert lock == {"a": "b", "d": "b"} and added == [("d", "b")]

def test_chains_collapse_to_the_last_successor():
    assert block_rows({"a": "b", "b": "c"}, {"c"}) == [("a", "c"), ("b", "c")]

def test_row_needs_successor_in_bibliography_and_old_key_out_of_it():
    assert block_rows({"a": "b", "x": "y"}, {"b", "x", "y"}) == [("a", "b")]

def test_dormant_successor_gives_no_row():
    assert block_rows({"a": "b"}, set()) == []

def test_unsafe_key_gives_no_row():
    assert block_rows({"con": "b", "a:b": "b"}, {"b"}) == []

def test_a_loop_gives_no_row():
    assert block_rows({"a": "b", "b": "a"}, {"c"}) == []

def test_block_text():
    assert render_renames_block([("a", "c"), ("b", "c")]) == (
        "@comment{cg-renames v1\na\tc\nb\tc\n}\n"
    )
    assert render_renames_block([]) == ""
```

- [ ] **Step 2: Run** `uv run pytest tests/test_renames.py -v`. Expected: FAIL, `ModuleNotFoundError: chitragupta_importer.renames`.
- [ ] **Step 3: Implement the five functions** in `renames.py`. `parse_renames_lock` mirrors `citekeys.parse_citekey_lock`. `block_rows` follows each chain with a visited set and drops a row whose chain revisits a key; it filters with `citekeys.citekey_problem`.
- [ ] **Step 4: Run** `uv run pytest tests/test_renames.py -v`. Expected: PASS.
- [ ] **Step 5: Commit** "Add the rename lock and the cg-renames block".

### Task 2: Bibliography header blocks

**Files:**
- Modify: `src/chitragupta_importer/bibtex.py` (`render_bibliography`), `src/chitragupta_importer/run.py` (its one call)
- Test: `tests/test_bibtex.py`, `tests/test_bibtex_escaping.py`

**Interfaces:**
- Produces: `render_bibliography(header: Sequence[str], entries: Sequence[str]) -> str`. Empty header strings are dropped, and the remaining blocks and entries are joined with one blank line, as today.

- [ ] **Step 1: Change the tests in `test_bibtex.py`** to `render_bibliography([table], [first, second]) == f"{table}\n{first}\n{second}"` and `render_bibliography(["", ""], []) == ""`. Add `test_header_blocks_in_order`: `render_bibliography(["T\n", "R\n"], ["E\n"]) == "T\n\nR\n\nE\n"`. Update the two calls in `test_bibtex_escaping.py`.
- [ ] **Step 2: Run** `uv run pytest tests/test_bibtex.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement**, and change `run.py` to `render_bibliography([name_table], entries)`.
- [ ] **Step 4: Run** the full suite. Expected: PASS.
- [ ] **Step 5: Commit** "Let the bibliography take several header blocks".

### Task 3: Read Zotero merges (`dc:replaces`)

**Files:**
- Modify: `src/chitragupta_importer/model.py` (`Item`), `src/chitragupta_importer/sources/zotero.py`
- Modify: `tests/fixtures/zotero_schema.sql`, `tests/zotero_fixture.py` (`add_item(..., replaces=())`)
- Test: `tests/test_zotero_source.py`

**Interfaces:**
- Produces: `Item.replaces: tuple[str, ...] = ()`, the sorted item IDs (`zotero:user/<KEY>`) of the personal-library items this item replaced in a Zotero merge.

- [ ] **Step 1: Add the fixture tables**, as in Zotero:

```sql
CREATE TABLE relationPredicates (predicateID INTEGER PRIMARY KEY, predicate TEXT UNIQUE);
CREATE TABLE itemRelations (itemID INT NOT NULL, predicateID INT NOT NULL,
  object TEXT NOT NULL, PRIMARY KEY (itemID, predicateID, object));
```

`add_item(replaces=...)` takes object URIs verbatim and writes one `dc:replaces` row each.

- [ ] **Step 2: Write the failing tests**

```python
def test_item_lists_the_items_it_replaced(tmp_path):
    # replaces=["http://zotero.org/users/local/abCD1234/items/OLD00001",
    #           "http://zotero.org/users/12345/items/OLD00002"]
    assert item.replaces == ("zotero:user/OLD00001", "zotero:user/OLD00002")

def test_replaced_group_item_or_odd_uri_is_ignored(tmp_path):
    # replaces=["http://zotero.org/groups/7/items/GRP00001", "urn:x"]
    assert item.replaces == ()
```

- [ ] **Step 3: Run** `uv run pytest tests/test_zotero_source.py -v`. Expected: FAIL.
- [ ] **Step 4: Implement** a `_REPLACES` query (join `relationPredicates` where `predicate = 'dc:replaces'`) read through `_by_item`. Parse with `re.compile(r"^http://zotero\.org/users/(?:local/)?\w+/items/([A-Z0-9]{8})$")`.
- [ ] **Step 5: Run** the full suite. Expected: PASS.
- [ ] **Step 6: Commit** "Read the items a Zotero merge replaced".

### Task 4: Rename sources A, B, C and D

**Files:**
- Modify: `src/chitragupta_importer/bootstrap.py` (A), `src/chitragupta_importer/citekeys.py` (D), `src/chitragupta_importer/renames.py` (B, C)
- Test: `tests/test_bootstrap_claims.py` (A), `tests/test_citekey_lock.py` (D), `tests/test_renames.py` (B, C)

**Interfaces:**
- Consumes: `Item.replaces` (Task 3).
- Produces:
  - `BootstrapResult.successors: Mapping[str, str]` (dropped key → the key frozen for its item; default empty)
  - `RENAMED_PREFIX = "renamed:"` and `MAX_FROZEN_LENGTH = 30` in `citekeys.py`
  - `shorten_long_citekeys(stems: Mapping[str, str], lock: Mapping[str, str]) -> tuple[dict[str, str], list[tuple[str, str]]]`. `stems` covers the included items only. It returns the updated lock and the `(old, new)` rows in item-ID order.
  - `merge_renames(duplicates: Mapping[str, str], lock: Mapping[str, str]) -> list[tuple[str, str]]` (B)
  - `zotero_merge_renames(library: Library, lock: Mapping[str, str]) -> list[tuple[str, str]]` (C)

- [ ] **Step 1: Write the failing tests**

```python
# test_bootstrap_claims.py: extend the existing two-entry test
assert result.successors == {"smith_twins_2024-1": "smith_twins_2024"}

# test_citekey_lock.py
LONG = "a" * 31
def test_key_over_30_is_renamed_and_its_spelling_reserved():
    lock, rows = shorten_long_citekeys({"z:1": "a_b_2020"}, {"z:1": LONG})
    assert lock == {"z:1": "a_b_2020", f"renamed:{LONG}": LONG}
    assert rows == [(LONG, "a_b_2020")]

def test_key_of_30_stays():
    assert shorten_long_citekeys({"z:1": "a_b_2020"}, {"z:1": "a" * 30})[1] == []

def test_dormant_long_key_is_not_renamed():
    assert shorten_long_citekeys({}, {"z:1": LONG}) == ({"z:1": LONG}, [])

def test_new_short_key_takes_a_clash_suffix():
    lock, rows = shorten_long_citekeys({"z:1": "a_b_2020"}, {"z:1": LONG, "z:2": "a_b_2020"})
    assert rows == [(LONG, "a_b_2020-1")]

# test_renames.py
def test_merge_rename_needs_both_items_in_the_lock():
    lock = {"z:1": "old", "z:2": "new"}
    assert merge_renames({"z:1": "z:2", "z:3": "z:2"}, lock) == [("old", "new")]

def test_zotero_merge_rename_for_a_retired_line_only(tmp_path):
    # library: item z:2 with replaces=("z:1", "z:3"); z:3 is still in the library
    assert zotero_merge_renames(library, {"z:1": "old", "z:2": "new", "z:3": "k3"}) == [
        ("old", "new")
    ]
```

- [ ] **Step 2: Run** the three test files. Expected: FAIL.
- [ ] **Step 3: Implement.** In `bootstrap()`, build `successors` next to `dropped` from `claims` and `frozen`. `shorten_long_citekeys` takes each new spelling with `free_spelling(stem, used)` and checks it with `citekey_problem`, raising `UnsafeCitekey`, as `assign_citekeys` does. B and C skip any item ID missing from the lock.
- [ ] **Step 4: Run** the full suite. Expected: PASS.
- [ ] **Step 5: Commit** "Find citekey renames from bootstraps, merges and long keys".

### Task 5: Wire renames into the import run

**Files:**
- Modify: `src/chitragupta_importer/run.py`, `src/chitragupta_importer/renames.py` (a `plan_renames` helper keeps `run.py` under 250 lines), `src/chitragupta_importer/summary.py`, `src/chitragupta_importer/console.py`
- Test: `tests/test_run_renames.py` (new), `tests/test_run.py`

**Interfaces:**
- Consumes: Tasks 1 to 4.
- Produces:
  - `RENAMES_LOCK = "renames.lock"` in `run.py`
  - `Plan.renames_lock: dict[str, str]`
  - `RunSummary.renames: tuple[tuple[str, str], ...] = ()`, the rows added this run
  - `plan_renames(renames, lock, stems, library, duplicates, bootstrap) -> tuple[dict[str, str], dict[str, str], list[tuple[str, str]]]`, returning the citekey lock, the rename lock and the added rows. It applies A, B, C, then D.

Order in `_plan`: assign new keys, then `plan_renames`, then `_check_citekeys`, then PDFs keyed by the final lock, then render with `[name_table, render_renames_block(block_rows(renames, entry_keys))]`. `_write` writes `renames.lock`, when it has rows, after `citekeys.lock` and before `collections.lock`.

- [ ] **Step 1: Write the failing tests** in `tests/test_run_renames.py`, using `run_fixture.build`:

```python
def test_bootstrap_dropped_key_gets_a_row(tmp_path):
    # NEWER + OLDER merged; existing bib has the two ostrander keys (as test_run_duplicates)
    assert "@comment{cg-renames v1\nostrander_calibrating_2024-1\tostrander_calibrating_2024\n}\n" in bib
    assert (out / "renames.lock").read_text() == (
        "ostrander_calibrating_2024-1\tostrander_calibrating_2024\n"
    )
    assert summary.renames == (("ostrander_calibrating_2024-1", "ostrander_calibrating_2024"),)

def test_long_frozen_key_is_renamed_and_chain_collapses(tmp_path):
    # existing bib freezes a 31+ character key K for OSTRANDER and drops K-1
    assert "zotero:user/AAAA1111\tostrander_calib_2024\n" in lock
    assert f"renamed:{K}\t{K}\n" in lock
    assert block == [(f"{K}-1", "ostrander_calib_2024"), (K, "ostrander_calib_2024")]
    assert (out / "files" / "ostrander_calib_2024.pdf").exists()

def test_zotero_merge_after_first_run_gets_a_row(tmp_path):
    # run 1: OSTRANDER and SMITH; run 2: SMITH gone, OSTRANDER with replaces=[SMITH's URI]
    assert "smith_digital_2020\tostrander_calib_2024" in bib

def test_second_run_is_byte_identical_with_no_new_rows(tmp_path):
    assert snapshot(out) == before and summary.renames == ()

def test_no_renames_no_block_no_file(tmp_path):
    assert "cg-renames" not in bib and not (out / "renames.lock").exists()

def test_malformed_renames_lock_refuses(tmp_path):
    # renames.lock holds "x y\n"
    with pytest.raises(ImportRefused, match="renames.lock: malformed lock file"):
        import_zotero(data_dir, out)
```

Add `citekey renames` to the expected table in `tests/test_cli_output.py` and `renamed citekey: a -> b` to `test_format_summary_lists_every_line_in_order`.

- [ ] **Step 2: Run** `uv run pytest tests/test_run_renames.py -v`. Expected: FAIL.
- [ ] **Step 3: Implement** as in the Interfaces block. The summary line is `renamed citekey: <old> -> <new>`, after the dropped lines, and the table row label is `citekey renames`.
- [ ] **Step 4: Run** the full suite, then lint. Expected: PASS, pylint 10.00.
- [ ] **Step 5: Commit** "Write citekey renames to renames.lock and the bibliography".

### Task 6: Contract, docs, check script, version

**Files:**
- Create: `docs/adr/0009-citekey-renames-in-the-bibliography.md`
- Modify: `PROJECT.md` (output contract), `docs/superpowers/specs/2026-11-13-zotero-importer-design.md` (key rules 1 and 3), `README.md` (papers tree, renames, summary lines; a `papers/` bootstrapped before 0.3.0 gets source-A rows only by bootstrapping again into an empty directory), `GLOSSARY.md` (add **Citekey rename** and **Successor**; "Rename" stays the collection term), `scripts/check_zotero_data.py` (print `renames: N`), `pyproject.toml` + `uv.lock` (0.3.0)

- [ ] **Step 1: Write the docs.** The contract sentence in `PROJECT.md` becomes: "A citekey, once written to `papers/citekeys.lock`, never moves to another paper. It changes spelling once, when it is longer than 30 characters; the old spelling is reserved and the rename is recorded in `renames.lock` and the bibliography's `cg-renames` block." ADR-0009 records the chosen approach and the rejected ones from the spec.
- [ ] **Step 2: Sweep** with `grep -rn "never changes spelling\|never changes" README.md PROJECT.md GLOSSARY.md docs/` and fix every stale claim.
- [ ] **Step 3: Run** the test, lint and build commands from `PROJECT.md`. Expected: all pass, `dist/chitragupta_importer-0.3.0*`.
- [ ] **Step 4: Commit** "Document citekey renames and bump to 0.3.0".

### Task 7: Real-data check and PR

- [ ] **Step 1:** Run `uv run python scripts/check_zotero_data.py --merge-duplicates ~/chitragupta-importer/zotero/20261124_Zotero /workspace/papers/bibliography-groups.bib`. Expected: matched 447, key rule 443 of 447, and renames 83 (67 from A, 16 from D).
- [ ] **Step 2:** Bootstrap into an empty scratch directory, then run again without `--bootstrap`. Expected: the second run adds 0 renames and every file is byte-identical. The `cg-renames` block has no key over 30 characters as a successor. Every successor is an entry key, and no old key is an entry key.
- [ ] **Step 3:** Open the PR with `.github/pull_request_template.md` (MINOR, 0.3.0). Body says "Closes #7". Give aggregate numbers only.
