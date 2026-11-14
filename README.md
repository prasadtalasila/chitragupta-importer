# chitragupta-importer

Reads a reference manager's library (its database and attachment
storage) and writes one consistent `papers/` directory for
[chitragupta](https://github.com/prasadtalasila/chitragupta). chitragupta
reads only that directory and never learns the importer exists.
Zotero is the first supported reference manager.

```text
papers/
├── bibliography.bib      one entry per item that has a PDF
├── citekeys.lock         item id -> citekey; a written key never changes
└── files/
    └── <citekey>.pdf
```

**Status:** repository scaffold only. The Zotero import is designed in
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
