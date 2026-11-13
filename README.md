# chitragupta-importer

Supplies papers and a BibTeX file to
[chitragupta](https://github.com/prasadtalasila/chitragupta).
It will be packaged with Poetry and distributed as a wheel.

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
