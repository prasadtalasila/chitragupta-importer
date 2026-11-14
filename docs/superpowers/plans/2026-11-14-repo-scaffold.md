# Repo Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make this repository a uv-managed Python package with a tested, empty click CLI, DTaaS-style agent guidance and chitragupta's GitHub templates.

**Architecture:** `src/` layout package `chitragupta_importer`, a click group as the console entry point, pytest via click's `CliRunner`. Agent guidance split into `AGENTS.md` (general) and `PROJECT.md` (this repo), imported by `CLAUDE.md`.

**Tech Stack:** uv, uv_build, Python >=3.12, click, pytest, pytest-cov, ruff, pylint.

**Spec:** `docs/superpowers/specs/2026-11-13-repo-scaffold-design.md`

**Reference sources** (clone shallow into a scratch directory, never into the repo):
- `https://github.com/prasadtalasila/chitragupta` (`.pylintrc`, `.github/` templates, `DEVELOPER-AGENTS.md`)
- `https://github.com/INTO-CPS-Association/DTaaS` (`AGENTS.md`, `PROJECT.md`, `CLAUDE.md`, `.github/copilot-instructions.md`)

## Global Constraints

- Distribution name `chitragupta-importer`, import package `chitragupta_importer`, console script `chitragupta-importer`.
- Version `0.1.0`; `requires-python = ">=3.12"`; license MIT; build backend `uv_build`.
- Runtime dependency: `click` only. Dev group: `pytest`, `pytest-cov`, `ruff`, `pylint`.
- `[tool.ruff] line-length = 100`; coverage with `branch = true`.
- Functions under 25 lines, files under 250 lines.
- No GitHub workflows, `dependabot.yml`, `actionlint.yaml`, skills, hooks or `.claude/` settings.
- `scripts/rc-daemon.sh` and `scripts/rc-daemon.env.example` are not modified.
- Commit messages: imperative title; body of `- Verb ...` bullets wrapped at 72 columns; end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. `python -m chitragupta_importer --version` works, not only the console script: covered in Task 1 (`test_module_entry_point`).
2. `--version` output follows `pyproject.toml` rather than a hard-coded string: covered in Task 1 (`test_version_matches_metadata`).
3. The built wheel contains the package and the entry point: covered in Task 1, Step 7.
4. Linters pass on the scaffold itself, so later work starts green: covered in Task 2.
5. Every relative link in the new Markdown files resolves: covered in Tasks 3 to 5 (link check step).

---

### Task 1: uv package with a click CLI

**Files:**
- Create: `pyproject.toml`, `.python-version`, `uv.lock` (generated), `src/chitragupta_importer/__init__.py`, `src/chitragupta_importer/__main__.py`
- Modify: `.gitignore` (append `.venv/`, `dist/`, `.coverage`, `.pytest_cache/`, `.ruff_cache/`, `__pycache__/`)
- Test: `tests/test_cli.py`

**Interfaces:**
- Produces: `chitragupta_importer.__version__: str`; `chitragupta_importer.__main__.main: click.Group`, which part (B) adds subcommands to with `@main.command()`.

- [ ] **Step 1: Install uv if missing**

Run: `command -v uv || curl -LsSf https://astral.sh/uv/install.sh | sh`, then `uv --version`
Expected: a version line.

- [ ] **Step 2: Write `pyproject.toml` and `.python-version`**

`pyproject.toml` holds the Global Constraints values: `[project]` (name, version, description "Import reference-manager libraries into the papers/ directory chitragupta reads.", readme, license, requires-python, `dependencies = ["click"]`), `[project.scripts] chitragupta-importer = "chitragupta_importer.__main__:main"`, `[dependency-groups] dev = [...]`, `[build-system] requires = ["uv_build"]`, `build-backend = "uv_build"`, `[tool.ruff]`, `[tool.pytest.ini_options] testpaths = ["tests"]`, `[tool.coverage.run] branch = true, source = ["chitragupta_importer"]`. `.python-version` contains `3.12`.

- [ ] **Step 3: Write the failing tests in `tests/test_cli.py`**

```python
import subprocess
import sys
from importlib.metadata import version

from click.testing import CliRunner

from chitragupta_importer.__main__ import main


def test_version_matches_metadata():
    result = CliRunner().invoke(main, ["--version"])
    assert result.exit_code == 0
    assert version("chitragupta-importer") in result.output
    assert version("chitragupta-importer") == "0.1.0"


def test_no_arguments_prints_help():
    result = CliRunner().invoke(main, [])
    assert "Usage:" in result.output


def test_module_entry_point():
    done = subprocess.run(
        [sys.executable, "-m", "chitragupta_importer", "--version"],
        capture_output=True, text=True, check=True,
    )
    assert "0.1.0" in done.stdout
```

- [ ] **Step 4: Run them to verify they fail**

Run: `uv sync && uv run pytest -v`
Expected: FAIL on import of `chitragupta_importer.__main__` (module missing).

- [ ] **Step 5: Implement the package**

`__init__.py`: `__version__ = importlib.metadata.version("chitragupta-importer")`.
`__main__.py`: `main` is a `@click.group()` with `@click.version_option(package_name="chitragupta-importer")` and a docstring that becomes the help text; `if __name__ == "__main__": main()`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest --cov --cov-report=term-missing -v`
Expected: 3 passed; 100% line and branch coverage except the `__name__ == "__main__"` guard (mark it `# pragma: no cover`).

- [ ] **Step 7: Build and inspect the wheel**

Run: `uv build && python3 -m zipfile -l dist/*.whl | grep -E '__main__.py|entry_points.txt'`
Expected: both files listed.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml .python-version uv.lock .gitignore src tests
git commit   # title: "Add uv package skeleton with a click CLI"
```

---

### Task 2: Linter configuration

**Files:**
- Create: `.pylintrc`
- Modify: `pyproject.toml` (`[tool.ruff.lint] select = ["E", "F", "BLE", "RUF100"]`, as chitragupta)

**Interfaces:**
- Consumes: the package and tests from Task 1.
- Produces: the lint command in `PROJECT.md` (Task 3).

- [ ] **Step 1: Copy chitragupta's `.pylintrc` and trim it**

Keep general settings and message controls; drop anything naming chitragupta paths, plugins or modules. Set `max-line-length=100`, `max-statements=25`.

- [ ] **Step 2: Run all linters**

Run: `uv run ruff check . && uv run ruff format --check . && uv run pylint src tests`
Expected: exit 0, pylint score 10.00/10. Fix code, not config, for any finding.

- [ ] **Step 3: Commit** (title: "Add ruff and pylint configuration")

---

### Task 3: Agent guidance

**Files:**
- Create: `AGENTS.md`, `PROJECT.md`, `CLAUDE.md`, `.github/copilot-instructions.md`

**Interfaces:**
- Consumes: commands from Tasks 1 and 2.

- [ ] **Step 1: `AGENTS.md`**: DTaaS's `AGENTS.md` verbatim, except drop "(except 3D model files)" from RESTRICTIONS. Its PROJECT INSTRUCTIONS paragraph keeps pointing to `PROJECT.md`.

- [ ] **Step 2: `PROJECT.md`** with exactly these sections:
  - **Autonomy** and **Behaviour**: DTaaS's text, unchanged.
  - **Build and test commands**: the spec's table (Install `uv sync`; Test `uv run pytest --cov --cov-report=term-missing`; Lint `uv run ruff check . && uv run ruff format --check . && uv run pylint src tests`; Build `uv build`).
  - **Verifying a change**: DTaaS's text with the command table above.
  - **Shipping**: DTaaS's list, minus the analysis-services step.
  - **Commit messages**: chitragupta's rules (imperative title, PR title is the squash title, never add the PR number by hand, `- Verb` bullets, 72 columns, two-space continuation, no closing keyword).
  - **Versioning**: semver PATCH/MINOR/MAJOR, adapted from chitragupta (MAJOR = a change to the `papers/` output format, the lock format, or CLI arguments).
  - **Code standards**: ruff and pylint enforce style; functions under 25 lines, files under 250; add a dependency only when the task needs it.
  - **Output contract**: one paragraph: the importer writes only under the output `papers/` directory, never writes to a reference manager's files, and a citekey once written never changes.

- [ ] **Step 3: `CLAUDE.md`**: DTaaS's `CLAUDE.md` verbatim (`@AGENTS.md`, `@PROJECT.md`).

- [ ] **Step 4: `.github/copilot-instructions.md`**: DTaaS's, minus the skills line.

- [ ] **Step 5: Link check**

Run: `grep -oE '\]\([^)#]+' AGENTS.md PROJECT.md CLAUDE.md .github/copilot-instructions.md | sed -E 's/.*\]\(//' | sort -u` and confirm each path exists relative to its file.
Expected: every path exists.

- [ ] **Step 6: Commit** (title: "Add agent guidance adopted from DTaaS and chitragupta")

---

### Task 4: GitHub templates

**Files:**
- Create: `.github/pull_request_template.md`, `.github/ISSUE_TEMPLATE/bug_report.md`, `.github/ISSUE_TEMPLATE/feature_request.md`, `.github/RELEASE_TEMPLATE.md`

- [ ] **Step 1: Copy the four files from chitragupta.**

- [ ] **Step 2: Adapt the PR template**
  - Remove the `scripts/merge_pr.py --check` sentence from the commit-message comment; keep the empty `text` fence.
  - "Impact" points to `PROJECT.md` (Versioning) instead of `DEVELOPER-AGENTS.md`.
  - Test plan items: `uv run pytest --cov --cov-report=term-missing` (100% line and branch), the lint command from `PROJECT.md`, `uv build`, and one real run against a Zotero library (name it).
  - Checklist: replace the citekey item with "No existing citekey in `citekeys.lock` changes spelling or moves to another paper".

- [ ] **Step 3: Adapt the issue and release templates**: replace chitragupta names, commands and links with this project's; no other change.

- [ ] **Step 4: Check for leftovers**

Run: `grep -rnE 'chitragupta/|poetry|DEVELOPER-AGENTS|merge_pr|venv-full|enrich|SOUL' .github`
Expected: no output (mentions of chitragupta as the consumer, without a trailing `/`, are fine).

- [ ] **Step 5: Commit** (title: "Add PR, issue and release templates from chitragupta")

---

### Task 5: README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Rewrite the top section**
  - What it does: reads reference-manager libraries (Zotero first) and writes one `papers/` directory chitragupta reads, which never learns of the importer.
  - Output layout block: `papers/bibliography.bib`, `papers/files/<citekey>.pdf`, `papers/citekeys.lock`.
  - Status line: scaffold only; the Zotero import is designed in `docs/superpowers/specs/2026-11-13-zotero-importer-design.md`.
  - Install and development: `uv sync`, `uv run chitragupta-importer --version`, and a pointer to `PROJECT.md` for test, lint and build.
  - Remove "packaged with Poetry".

- [ ] **Step 2: Keep the "Remote Control daemon" section unchanged.**

- [ ] **Step 3: Verify**

Run: `grep -ni poetry README.md; uv run chitragupta-importer --version`
Expected: no Poetry match; `chitragupta-importer, version 0.1.0`.

- [ ] **Step 4: Run the full check once more**

Run: `uv run pytest --cov && uv run ruff check . && uv run ruff format --check . && uv run pylint src tests && uv build`
Expected: all exit 0.

- [ ] **Step 5: Commit** (title: "Rewrite README for the uv package")
