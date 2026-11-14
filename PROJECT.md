# Project Instructions

Instructions specific to chitragupta-importer, for contributors and
coding agents alike. `AGENTS.md` holds the general coding guidelines;
this file holds what cannot be inferred from them.

## Autonomy

Work through the full cycle for routine changes without pausing at each
step. Pause only for irreversible actions (force-push, history rewrite,
deletion, publishing) or requirements with two defensible readings that
lead to materially different work.

## Behaviour

**Think before coding.** State assumptions. Where several readings
exist, present them rather than choosing silently.

**Simplicity first.** Write the minimum that solves the stated problem.
No speculative abstraction, unrequested configurability, or defensive
handling for impossible states.

**Surgical changes.** Every changed line traces to the task. Match local
style. Remove imports your change orphans; report pre-existing dead code
instead of deleting it in the same diff.

**Goal-driven execution.** Turn the task into a check you can run.
"Fix the bug" becomes "write a failing test, then make it pass."

## Build and test commands

The project is managed with [uv](https://docs.astral.sh/uv/).

| Task | Command |
| :--- | :--- |
| Install | `uv sync` |
| Test | `uv run pytest --cov --cov-report=term-missing` |
| Lint | `uv run ruff check . && uv run ruff format --check . && uv run pylint src tests` |
| Build | `uv build` |

## Verifying a change

Run the test and lint commands above. Line and branch coverage stays at
100%. Compare against the merge base before reporting a regression: run
the same command there and compare counts. Report pre-existing failures;
do not fix them in the same diff.

Claim something passes only after seeing it pass.

## Shipping

1. Branch from the default branch. Never commit to it directly.
1. Commit following the format below.
1. Sweep documentation your change made stale. Search the repository for
   paths, names and numbers you moved.
1. Open a pull request using `.github/pull_request_template.md`.
1. Address review, then merge.

## Commit messages

- **Title:** imperative mood, concise, describing the change's effect.
  Pull requests are squash-merged and the PR title becomes the commit
  title. Never add the PR number by hand; GitHub appends it.
- **Body:** a blank line, then bullets that each start with a
  present-tense verb (Fix, Add, Remove) and name a concrete change. No
  preamble. Lines wrap at 72 characters; continuation lines are indented
  two spaces.
- **No closing keywords** (`Closes #N`) in the commit; they belong in
  the PR description.

## Versioning

Semantic versioning, in `pyproject.toml`'s `[project].version`, bumped
by the most significant change in a release:

- **PATCH:** bug fixes, documentation, tests, CI.
- **MINOR:** new backward-compatible behaviour, such as a new source
  reference manager or a new optional CLI option.
- **MAJOR:** a change to the `papers/` output format, the
  `citekeys.lock` format, or an existing CLI option's shape.

## Code standards

ruff (`pyproject.toml`) and pylint (`.pylintrc`) enforce style. Run them
rather than reasoning about style. pylint also enforces the size limits
from `AGENTS.md`: at most 25 statements per function and 250 lines per
module. Add a dependency only when the task requires it.

## Output contract

The importer writes only inside the output `papers/` directory and
never writes to a reference manager's own files; `zotero.sqlite` is
opened read-only. A citekey, once written to `papers/citekeys.lock`,
never changes spelling and never moves to another paper. The design is
in `docs/superpowers/specs/2026-11-13-zotero-importer-design.md`.
