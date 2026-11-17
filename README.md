# chitragupta-importer

Reads a reference manager's library (its database and attachment
storage) and writes one consistent `papers/` directory for
[chitragupta](https://github.com/prasadtalasila/chitragupta). chitragupta
reads only that directory and never learns the importer exists.
Zotero is the first supported reference manager.

## Usage

Find the Zotero data directory (it holds `zotero.sqlite` and `storage/`)
under Zotero Settings → Advanced → Files and Folders. Check the first import
run before writing anything: it freezes the citekeys of an existing
bibliography (for example a Zotero BibTeX export) in a new citekey lock,
merges duplicate items and prints what it would do:

```bash
chitragupta-importer zotero --data-dir ~/Zotero --out papers \
    --bootstrap old.bib --merge-duplicates --dry-run
```

Then run it for real:

```bash
chitragupta-importer zotero --data-dir ~/Zotero --out papers \
    --bootstrap old.bib --merge-duplicates
```

Every later import run reads the locks in `papers/` and needs no
`--bootstrap`:

```bash
chitragupta-importer zotero --data-dir ~/Zotero --out papers --merge-duplicates
```

`chitragupta-importer zotero --help`:

```text
 Usage: chitragupta-importer zotero [OPTIONS]

 Import the personal Zotero library into a papers directory.
 Reads zotero.sqlite read-only, writes the bibliography, the locks and the main
 PDFs under --out, and prints a summary. A refused import run writes nothing
 and exits 1.

╭─ Locations ──────────────────────────────────────────────────────────────────╮
│ *  --data-dir   DIRECTORY  Zotero data directory, holding zotero.sqlite and  │
│                            storage/; only read. Zotero shows it under Zotero │
│                            Settings → Advanced → Files and Folders.          │
│                            [required]                                        │
│ *  --out        DIRECTORY  Papers directory to write; created if missing.    │
│                            Nothing is written outside it. [required]         │
│    --bootstrap  FILE       Existing bibliography whose citekeys to freeze in │
│                            a new citekey lock; first import run only.        │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Behaviour ──────────────────────────────────────────────────────────────────╮
│ --merge-duplicates  Merge each duplicate group into one item instead of      │
│                     refusing the import run.                                 │
│ --dry-run           Print the summary a real import run would print, but     │
│                     write nothing.                                           │
╰──────────────────────────────────────────────────────────────────────────────╯
╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --help  Show this message and exit.                                          │
╰──────────────────────────────────────────────────────────────────────────────╯

 Examples

 First import run, checked before anything is written:
   chitragupta-importer zotero --data-dir ~/Zotero --out papers \
       --bootstrap old.bib --merge-duplicates --dry-run

 The same first import run, for real:
   chitragupta-importer zotero --data-dir ~/Zotero --out papers \
       --bootstrap old.bib --merge-duplicates

 Every later import run (no --bootstrap; the locks hold the citekeys):
   chitragupta-importer zotero --data-dir ~/Zotero --out papers \
       --merge-duplicates
```

An import run reads the personal library only; `zotero.sqlite` is opened
read-only and nothing is written outside `--out`. It prints a summary: a
table of counts (included items, left-out items by reason, new citekeys,
duplicates, the bootstrap counts and dropped citekeys, files in
`papers/files/` it did not write), then one line per collection change,
duplicate, dropped citekey, unreferenced file and skipped library. A
refused import run writes nothing, prints `Error:` and one problem per line
to stderr and exits 1. In a terminal the output is coloured; piped or
redirected it is plain text.

Duplicate items in the library are items with the same item type, the same
title ignoring case and punctuation, and a shared DOI, URL or identical PDF;
when bootstrapping, an existing entry whose URL matches several items that
its title cannot tell apart makes those items duplicates too. By default an
import run that finds duplicates lists each group (item IDs and titles),
writes nothing and exits 1. `--merge-duplicates` merges each group, as a
Zotero merge would.

The survivor is the item with its own PDF (among several, the one added
first); it gains the others' collections and tags, and their attachments
only when it has no PDF of its own. Each other item is reported as
`duplicate <item ID> of <item ID>` and gets no entry and no citekey. When
the bibliography given to `--bootstrap` has several entries for one item
(a survivor merged here, or an item whose copies were already merged in
Zotero), one citekey is frozen and the summary lists the others as
`dropped citekey: ...`, so drafts citing them can be updated; a dropped
citekey is retired in the citekey lock and never given to another item. A
later merge in Zotero that keeps the same item keeps the frozen citekey.

`--dry-run` does everything but write: it creates and changes nothing
under `--out`, refuses whatever a real import run would refuse, and prints
the summary a real import run would print, after a first line
`dry run: nothing written`.

The papers directory:

```text
papers/
├── bibliography.bib      the name table, then one entry per included item
├── citekeys.lock         item ID -> citekey; a written citekey never changes
├── collections.lock      collection ID -> segment slug, parent and name
└── files/
    └── <citekey>.pdf     the item's main PDF
```

Each entry lists the slug paths of the collections its item is directly in,
in `cg-collections`; the name table (a `@comment{cg-collections v1 ...}`
block at the top) gives each slug path its collection's own name.

The design is in
[docs/superpowers/specs/2026-11-13-zotero-importer-design.md](docs/superpowers/specs/2026-11-13-zotero-importer-design.md).

## Install and develop

The project is managed with [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run chitragupta-importer --version
```

Test, lint and build commands are in [PROJECT.md](PROJECT.md).

## Remote Control daemon

`scripts/rc-daemon.sh` keeps `claude remote-control` running in a detached
tmux session and restarts it when it exits (Claude Code gives up after
10 minutes of persistent errors).

```bash
# one-time: trust the workspace and accept the Remote Control consent
claude remote-control        # answer the prompts, then Ctrl-C

scripts/rc-daemon.sh start   # also: stop | restart | status | attach | log
```

Settings live in `scripts/rc-daemon.env.example`. To change them, copy it to
`scripts/rc-daemon.env` (gitignored) and edit the copy, or override one
setting per run: `RC_NAME=other scripts/rc-daemon.sh start`.
Needs `tmux`, `claude` and `python3` on `PATH`.
