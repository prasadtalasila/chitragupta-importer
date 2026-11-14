# Repository scaffold: uv package, agent guidance, GitHub templates

Status: draft for approval. Part (A) of two; part (B), the Zotero
importer, has its own design
([2026-11-13-zotero-importer-design.md](2026-11-13-zotero-importer-design.md)).

## Intent

Turn this repository into a uv-managed Python package with a working,
tested, empty CLI, so part (B) starts on a settled base. Adopt the
agent guidance and coding standards of the sibling projects without
their project-specific weight.

## Goals

- `uv sync`, `uv run pytest`, `uv run chitragupta-importer --version`
  and `uv build` all work from a fresh clone.
- Agent guidance in the DTaaS layout: `AGENTS.md` (general),
  `PROJECT.md` (this repository), `CLAUDE.md` (imports both),
  `.github/copilot-instructions.md` (points to both).
- GitHub templates copied from chitragupta and adapted.
- README describes the importer and the uv workflow.

## Non-goals

- No GitHub workflows, `dependabot.yml` or `actionlint.yaml`: templates
  only.
- No skills, hooks or `.claude/` settings from chitragupta.
- No importer behaviour; that is part (B).
- No C1/C2 ratchet register or scan test. The 25-line function and
  250-line file limits are stated in `AGENTS.md` as review rules.

## Approaches considered

| Choice | Picked | Rejected, and why |
| --- | --- | --- |
| Layout | `src/chitragupta_importer/` (uv `--package` default; tests import the installed package) | flat package as in chitragupta: tests can pass against the working tree but fail installed |
| CLI | click: one stable dependency, built-in path checks, `CliRunner` for tests; DTaaS's `cli/` uses it | argparse: no dependency but hand-written subcommand dispatch and path checks; typer: more dependencies (click, rich, typing-extensions) for coloured help |
| Linters | ruff (check + format) and pylint, configs adapted from chitragupta | ruff only: drops the `.pylintrc` both sibling projects use |

## Design

Files added or changed:

```text
pyproject.toml                 name chitragupta-importer, version 0.1.0,
                               requires-python >=3.12, MIT,
                               [project.scripts] chitragupta-importer,
                               build backend uv_build,
                               dependencies: click,
                               [dependency-groups] dev: pytest,
                               pytest-cov, ruff, pylint;
                               [tool.ruff] line-length 100;
                               [tool.pytest], [tool.coverage] branch on
uv.lock                        committed
.python-version                3.12
.pylintrc                      from chitragupta, trimmed to rules that
                               apply here
src/chitragupta_importer/__init__.py    __version__ from package metadata
src/chitragupta_importer/__main__.py    click group `main`, --version
tests/test_cli.py              via click's CliRunner: --version prints
                               the version; no args prints help
AGENTS.md                      DTaaS AGENTS.md, near verbatim (drop the
                               "3D model files" exception)
PROJECT.md                     new: autonomy, behaviour rules, uv build
                               and test commands, verifying a change,
                               shipping cycle, code standards, commit
                               message format, semver
CLAUDE.md                      @AGENTS.md and @PROJECT.md only
.github/copilot-instructions.md    points to AGENTS.md and PROJECT.md
.github/pull_request_template.md   chitragupta's, test plan and checklist
                                   rewritten for uv; merge_pr.py,
                                   .venv-full and enrich items removed;
                                   citekey invariant reworded for an
                                   importer that creates keys
.github/ISSUE_TEMPLATE/bug_report.md       copied, names adapted
.github/ISSUE_TEMPLATE/feature_request.md  copied, names adapted
.github/RELEASE_TEMPLATE.md        copied, names adapted
README.md                      what the importer does, the papers/
                               output layout, uv install and dev
                               commands; Poetry mention removed; the
                               rc-daemon section kept
.gitignore                     add .venv/, dist/, .coverage, caches
```

`scripts/rc-daemon.sh` and its env example stay as they are.

`PROJECT.md` takes from chitragupta's `DEVELOPER-AGENTS.md` only what
applies to a small package: the four behaviour rules, the commit
message format (imperative title, bulleted body, 72 columns, no PR
number by hand), semver bump rules, and "claim a pass only after
seeing it". Its commands table:

| Task | Command |
| --- | --- |
| Install | `uv sync` |
| Test | `uv run pytest --cov --cov-report=term-missing` |
| Lint | `uv run ruff check . && uv run ruff format --check . && uv run pylint src tests` |
| Build | `uv build` |

## Left to the builder

- Exact pylint rules kept from chitragupta's `.pylintrc`.
- Wording of `PROJECT.md` beyond the sections listed.
- Installing uv on this host (it is not installed).
