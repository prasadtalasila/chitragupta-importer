# chitragupta-importer

Reads a reference manager's library (its database and attachment
storage) and writes one consistent `papers/` directory for
[chitragupta](https://github.com/prasadtalasila/chitragupta). chitragupta
reads only that directory and never learns the importer exists.
Zotero is the first supported reference manager.

## Usage

The first import run freezes the citekeys of an existing bibliography (for
example a Zotero BibTeX export) in a new citekey lock:

```bash
chitragupta-importer zotero --data-dir ~/Zotero --out papers --bootstrap old.bib
```

Every later import run reads the locks in `papers/` and needs no
`--bootstrap`:

```bash
chitragupta-importer zotero --data-dir ~/Zotero --out papers
```

An import run reads the personal library only; `zotero.sqlite` is opened
read-only and nothing is written outside `--out`. It prints a summary:
included items, left-out items by reason, new citekeys, collection
changes and files in `papers/files/` it did not write. A refused import
run writes nothing.

Duplicate items in the library (same item type, same title ignoring case
and punctuation, and a shared DOI or identical PDF) are merged before
anything else, as a Zotero merge would: the item added first survives and
gains the others' attachments, collections and tags. Each other item is
reported as `duplicate <item ID> of <item ID>` and gets no entry and no
citekey. When the bibliography given to `--bootstrap` has several entries
for one merged item, one citekey is frozen and the summary lists the others
as `dropped citekey: ...`, so drafts citing them can be updated. A later
merge in Zotero that keeps the default master keeps the frozen citekey.

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
