# Zotero importer: from a Zotero library to chitragupta's `papers/`

Status: draft for approval. Part (B) of two; builds on the scaffold in
[2026-11-13-repo-scaffold-design.md](2026-11-13-repo-scaffold-design.md).
Refines GitHub issue #1, and overrides it where noted.

## Intent and the why

chitragupta reads exactly one thing: `papers/bibliography.bib` and the
PDFs beside it. It never learns where they came from. Getting that
directory out of a reference manager is today a manual Zotero export
with two defects:

- **Unstable citekeys.** Zotero stores no citation key (0 of 644 items
  in the reference library have one) and builds keys at export time.
  86 keys carry an order-dependent `-1` suffix, so a later export can
  swap two papers' keys under drafts that cite them.
- **Lost collections.** Zotero's own exporter drops collection
  membership; the current `groups` field comes from a separate script
  in chitragupta that its own docs call a violation of the project's
  spirit.

This package is a CLI that reads a reference manager's own storage and
writes a deterministic, reviewable `papers/` directory. Zotero is the
first source; Mendeley and others follow with the same output.

## Goals

1. Read a Zotero library (`zotero.sqlite` and its `storage/`)
   read-only.
2. Write `papers/bibliography.bib`, `papers/files/<citekey>.pdf` and a
   citekey index, `papers/citekeys.lock`.
3. **Citekeys are created by the importer and never change** once
   written. The keys drafts already cite, from the existing
   `bibliography-groups.bib`, are frozen exactly as spelled.
4. Export only items that have a PDF; leave out and list the rest.
5. Running twice on an unchanged library gives byte-identical output.
   Adding a paper changes only that paper's lines.
6. Carry collection membership into each entry (format: see
   [Collections](#collections-deferred)).

## Non-goals

- Writing to `zotero.sqlite` or any Zotero file. Ever.
- Sources other than Zotero in this version.
- Annotations (377 in the reference library), notes, HTML snapshots and
  other non-PDF attachments.
- Reading chitragupta's ledger, drafts or `content/`. Naming drafts
  that cite a changed key is chitragupta's job (its `sync` reads the
  lock).
- A runtime dependency on chitragupta.

## Anti-goals

The importer fails its purpose, even if every test passes, if:

- a citekey that was ever written changes spelling or moves to a
  different paper;
- any file outside `papers/` is written, or `zotero.sqlite` is opened
  writable;
- output differs between two runs on the same input.

## Constraints from chitragupta (the consumer)

- `file = {Desc:path:mimetype}`, `;`-separated, with `\:` and `\;`
  escapes (`chitragupta/bib_escapes.py`). chitragupta takes the first
  PDF that exists.
- Every attachment path must resolve inside the bib's directory, or
  chitragupta refuses the entry and exits nonzero.
- `groups` is read by `chitragupta/bib_collections.py`: a plain
  `split(",")`, then `>` for nesting, whitespace normalised. It has no
  escape handling.

## Reference data

`/workspace/papers` holds the library this is designed against:

| What | Count |
| --- | --- |
| Regular items (not attachments, notes, annotations; not deleted) | 644 |
| Entries in `bibliography-groups.bib` | 644, 592 with a `file` field |
| Entries with at least one PDF attachment | 498 |
| ...whose PDF matches a file in `Zotero/storage/` by content hash | 497 |
| ...whose PDF is missing on disk | 1 |
| ...with more than one PDF | 19 |
| Collections | 108, depth up to 4, none with `,` or `>` in the name, 7 names reused in different branches |
| Zotero `userdata` schema version | 121 |

`bibliography-groups.bib` is `bibliography.bib` plus a `groups` field.

## Approaches considered

| Approach | Verdict |
| --- | --- |
| **Read `zotero.sqlite` directly, read-only** | Picked (issue #1). The only source with stable item ids, collections and attachment paths together. Cost: Zotero's schema has no compatibility promise, handled by refusing unknown schema versions. |
| Parse Zotero's or Better BibTeX's `.bib` exports | Rejected. Neither has stable ids; the built-in export drops collections; Better BibTeX keys differ from the frozen ones and its exports in the reference data carry no `file` fields. |
| Zotero's local or web API | Rejected. Needs Zotero running or network and credentials, for no gain over the database. |

## Design

### Pipeline

```text
zotero.sqlite + storage/ ──► source reader ──► Item records
                                                  │
existing bib (bootstrap) ──► key matcher ─────────┤
citekeys.lock ───────────────────────────────────►│ key assignment
                                                  ▼
                               bib writer + PDF copier ──► papers/
```

- **Source reader** (`sources/zotero.py`): turns the database into
  plain `Item` records: source id, item type, fields, creators, PDF
  attachments (absolute paths in `storage/`), collection memberships.
  Skips items in `deletedItems` and collections in
  `deletedCollections`. A later source adds a sibling module producing
  the same records; no plugin machinery is built now.
- **Key assignment** (`keys.py`): reads the lock, freezes known keys,
  creates keys for new items.
- **Writer** (`bib.py`, `files.py`): writes the bib, copies PDFs,
  writes the lock.

### Opening the database

- Open with a `file:` URI, `mode=ro`, absolute path, UNC-safe (as
  `populate_bib_groups.py` in chitragupta does).
- Read `version` where `schema = 'userdata'`; refuse any value other
  than the known ones (121 today) with a message naming the version.
- Zotero holds a lock while running. Builder's call how to read safely
  (copy to a temp file first, or `immutable=1`), as long as the
  original is never opened writable.

### Source ids

`zotero:<library>/<itemKey>`, where `<library>` is `user` for the
personal library and `group-<groupID>` for a group library, because an
8-character key is unique only within one library. My call: export the
personal library only in this version and list group libraries as
skipped (the reference library has none).

### Citekeys

Stored in `papers/citekeys.lock`: one line per item ever exported,
`<source id>\t<citekey>`, sorted by source id, UTF-8, LF.

Rules, in order:

1. A source id in the lock keeps its key. Always.
2. A source id not in the lock gets a new key from the key rule.
3. A key in the lock is never given to another item, even after its
   item is deleted or loses its PDF. Lines are never removed.
   A paper deleted from Zotero and added again has a new item key, so
   it gets a new citekey; the old one stays retired. Matching it back
   to its old key is tracked as a separate issue.
4. A new key that clashes takes the next free suffix, Zotero's habit
   and the shape of the frozen keys: the first item keeps the bare key,
   the next gets `-1`, then `-2`, skipping any spelling already in the
   lock. Within one run, items are taken in order of source id, so the
   result does not depend on database row order. Assigned once, then
   frozen by rule 1. (My call.)
5. Every key, new or frozen, must pass chitragupta's `citekey_safety`
   rule, because the key also names `files/<citekey>.pdf`. (Copy the
   rule, ~30 lines, per issue #1.) An unsafe new key stops the run,
   naming the item; an unsafe frozen key stops bootstrap, so it is
   fixed in the bib and drafts before the first import. 0 of 644
   frozen keys in the reference data fail it.

**Key rule for new items** (my call, to keep the format consistent with
the frozen keys): the shape Zotero's built-in exporter uses,
`<first creator's last name>_<first significant title word>_<year>`,
lower case, ASCII-folded, `noauthor` and `nodate` when missing. The
builder pins the exact normalisation by making the rule reproduce the
frozen keys of the reference data (ignoring `-N` suffixes) and reports
the match rate; it should be close to 100%.

**Bootstrap** (first run, no lock yet, `--bootstrap <bib>`): match each
entry of the existing bib to a Zotero item, then write the lock from
those matches before assigning anything new.

- Match by content hash of the entry's PDF against `storage/` first
  (497 of 498 match in the reference data), then DOI, then URL, then
  normalised title.
- Only matched entries whose item has a valid PDF get a lock line.
  The rest (146 in the reference data) get none and are not exported;
  an item that gains a PDF later gets a new key from the rule.
- An entry matching no item, or more than one, is listed and gets no
  lock line. An item claimed by two entries is an error; the run stops.
- The run prints matched, unmatched and ambiguous counts. Nothing is
  written if any entry is ambiguous.
- `--bootstrap` with a lock already present is refused: bootstrap is
  a one-time step. (My call.)
- Overrides issue #1, which had the person type keys into Zotero's
  Citation Key field.

### Which items are exported

- Only items with at least one PDF attachment (content type
  `application/pdf`, or a `.pdf` file name) that exists on disk.
- Every left-out item is reported with its reason: no attachment, no
  PDF attachment, PDF missing on disk. The run still succeeds.
- Several PDFs: hash each PDF's file name with SHA-256, export the one
  with the lowest hash; tie on equal names broken by full path.
- The PDF is copied to `papers/files/<citekey>.pdf`, replaced only if
  its content changed. Files in `papers/files/` the run did not write
  are reported, not deleted.

### The bib entry

- One entry per exported item, ordered by citekey; fields in a fixed
  order; one formatting style; UTF-8, LF.
- Entry types and fields mapped from Zotero's item types and fields the
  way Zotero's built-in BibTeX translator maps them, so that for frozen
  entries the output matches `bibliography-groups.bib` field for field,
  except `file` and anything the translator does at random. The builder
  measures and reports the remaining differences.
- `file = {Full Text PDF:files/<citekey>.pdf:application/pdf}`, escaped
  per `bib_escapes.py`.

### Collections (deferred)

The format needs its own design, coming after this document is
approved. Until then the builder writes `groups` the way chitragupta
reads it today: full paths from the root, ` > ` between levels, `, `
between paths, sorted. That is safe on the reference data because no
name contains `,` or `>`; a name that does stops the run with a
message.

Inputs to that later design, from a survey of Zotero, JabRef, Mendeley,
EndNote, BibDesk and Citavi:

- Every one lets an item be in many collections; Zotero, JabRef,
  Mendeley and Citavi nest without limit, EndNote two levels, BibDesk
  none.
- Almost none put hierarchy in BibTeX; JabRef's own `groups` field
  means leaf names plus a `jabref-meta` tree, so our paths read as odd
  flat groups in JabRef.
- Names are not identities (duplicates, renames); every source has
  stable collection ids.
- Candidate: an `@comment{chitragupta-collections: …}` tree with stable
  ids, plus paths per entry; escaping needs a matching chitragupta
  change.

### CLI

```text
chitragupta-importer zotero --data-dir <Zotero dir> --out <papers dir>
                            [--bootstrap <existing .bib>]
```

`--data-dir` holds `zotero.sqlite` and `storage/`. Exit 0 on success,
nonzero on refusal (unknown schema, ambiguous bootstrap, bootstrap with
an existing lock, unsafe new key, collection name with a separator). A summary goes to stdout: exported,
left out by reason, new keys, unreferenced files.

### Writes

Each output file is written to a temp file in `papers/` and renamed,
so an interrupted run leaves the old file intact. The lock is written
last.

## Testing

- Fixture: a small synthetic `zotero.sqlite` built in the tests from
  the real schema (no private library data in the repository).
- Determinism: run twice, compare bytes; add an item, compare diffs.
- Key freezing: delete and re-add, rename, title change, clash.
- Reference-data checks (run by hand, not in CI, since the data is
  private): bootstrap match counts, key-rule match rate, field diff
  against `bibliography-groups.bib`.
- Coverage 100% line and branch, as issue #1 asks.

## Left to the builder

- Module names beyond those above; data class shapes.
- How the database is read while Zotero runs.
- The title-normalisation details in bootstrap matching.
- Exact Zotero-to-BibTeX field mapping, within the "match the built-in
  translator" rule.

## Open, to settle later

- The collections format (above).
- The CI round trip through `python -m chitragupta.corpus sync` that
  issue #1 asks for: there are no workflows yet (part A copies
  templates only).
