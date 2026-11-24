# Citekey renames for chitragupta (issue #7)

## Intent

When a citekey leaves the bibliography and another key now stands for the
same paper, drafts citing the old key should be rewritten without anyone
doing it by hand. chitragupta 7.0.0 reads an optional
`@comment{cg-renames v1 ...}` block of `old<TAB>new` rows in
`bibliography.bib` and rewrites drafts from it
(prasadtalasila/chitragupta#1211, #1253). On its own, chitragupta catches
a rename only when the two PDFs hash the same. The importer knows several
renames chitragupta cannot see, so it writes them.

The owner also wants short citekeys. New keys are already at most 20
characters (#11). Frozen keys from the old bibliography stay long unless they
are renamed, and the owner chose to rename the longest ones through this
block.

## Goals

- Write a `cg-renames v1` block holding every known rename, chains collapsed.
- Record every rename in a private `papers/renames.lock`, so it is
  written again on every later run.
- Rename each included item's citekey that is longer than 30 characters to
  a key from the key rule (16 included keys in the owner's library; 15 more
  belong to items without a PDF and are renamed once those are included).

## Non-goals

- chitragupta reading any lock (ADR-0007 stands).
- Giving a re-added Zotero item its old key back (issue #4).
- A rename for a key retired with no successor (an item deleted from
  Zotero): no row is written.

## Anti-goals

- A key moving to a different paper. A rename points an old key at the
  key of the same paper, never at another one.
- A row chitragupta would reject: a chain, a cycle, or a key that fails
  `citekey_safety`.

## Rename sources

Each source yields `old key -> successor key`, the successor being the key
the same paper has now.

| | When | old | successor |
|---|---|---|---|
| A | bootstrap drops a citekey | the dropped key | the key frozen for the same item |
| B | `--merge-duplicates` merges away an item that has a lock line | its key | the survivor's key |
| C | a lock line's item is gone from the library and a live item's `dc:replaces` names it (a merge in Zotero) | its key | the replacing item's key |
| D | an included item's key is longer than 30 characters | its key | a new key from the key rule |

Zotero records a merge as a `dc:replaces` relation on the kept item, whose
object is the URI of each merged item (`http://zotero.org/users/<user or
local/id>/items/<KEY>`). The owner's library has 148 of them. Source C maps
`<KEY>` to the item ID `zotero:user/<KEY>`.

Sources B and C need the successor's key, so they run after new keys are
assigned. D runs after B and C. A rename never replaces an existing row for
the same old key: the first row recorded wins.

## Case D changes the output contract

A renamed key's item gets a new key, so its `citekeys.lock` line changes
value. The old spelling is reserved under the pseudo item ID
`renamed:<old>`, the way dropped keys are, so it is never given to another
item. The contract in `PROJECT.md` and the design becomes: a citekey never
moves to another paper; it changes spelling only once, when it is longer
than 30 characters, and that rename is recorded. New keys are at most 22
characters (20 plus a clash suffix), so only frozen keys are ever renamed.
Only included items are renamed; a dormant long key is renamed in the run
that includes its item again.

## `renames.lock`

`<old key><TAB><successor key>` lines sorted by old key, read at the start
of a run and written with the other locks. Lines are never removed or
changed. A missing file is an empty lock. A malformed line (no tab, or an old
key listed twice) refuses the run, as for the other locks. The file stays
private to the importer (ADR-0007).

## The `cg-renames v1` block

Built from `renames.lock` on every run:

1. Follow each old key's chain to its last successor (`a -> b`, `b -> c`
   gives `a -> c` and `b -> c`).
2. Keep a row only when the last successor is the key of an included entry,
   the old key is not, and both keys pass `citekey_problem`.
3. Write the rows sorted by old key, after the `cg-collections` block, as
   `@comment{cg-renames v1\n<old>\t<new>\n...}`. No rows, no block.

Keys never repeat across items, so a chain cannot loop. Resolution still
stops at a key it has already visited, and drops that row.

## Summary

The table gains `citekey renames` (the rows added this run). The detail
lines gain `renamed citekey: <old> -> <successor>`, one per row added this run.
A dry run shows both and writes nothing.

## Approaches considered

- **Rows in `citekeys.lock`** (`renamed:<old>\t<new>`): the parser refuses a
  key held by two lines, and the format change would be MAJOR. Rejected.
- **A third column on `dropped:` lines**: older importers would misread the
  key and lose its reservation, and it covers source A only. Rejected.
- **chitragupta reads the locks**: rejected in ADR-0007.
- **`papers/renames.lock` plus the block** (chosen): `citekeys.lock`
  keeps its shape, and the block is regenerated from one private source.

## Versioning

MINOR, 0.3.0: a new optional file and block, and a new behaviour (case D).
`papers/` readers that ignore the block are unaffected. (Owner's call.)

## Real-data expectations (owner's library, fresh bootstrap)

- Source A: 67 rows. Source D: 16 rows, some extending an A row into a chain.
- Sources B and C: 0 rows on a fresh bootstrap; they show on later runs.

## Existing papers directories (builder's calls, settled by the designer)

- **Source A needs a bootstrap.** Only a bootstrap knows which item a
  dropped key belonged to; `dropped:` lines do not record it. A `papers/`
  bootstrapped before 0.3.0 gets rows from B, C and D on its next run, and
  gets A rows only by being bootstrapped again into an empty directory.
  The owner's `papers/` is rebuilt that way. No migration mode is built.
- **A D rename leaves `files/<old key>.pdf` in place.** On a bootstrap, D
  runs before anything is written, so no old file exists. On a later run
  the old file stays and is reported as unreferenced, like any other file
  the run did not write: the importer never deletes.

## Left to the builder

- Module layout (a `renames.py` for the lock and the block is the obvious
  fit) and the exact refusal wording.
- Whether source C reads `dc:replaces` into `Item` or into `Library`.
