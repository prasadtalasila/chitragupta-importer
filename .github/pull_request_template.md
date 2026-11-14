# Title

[A succinct, imperative title describing the change's effect, e.g. "List
Zotero items left out for having no PDF". This becomes the
squashed commit title on `main`; don't add the PR number by hand.]

## Type of Change

- [ ] New feature
- [ ] Bug fix
- [ ] Documentation update
- [ ] Refactoring
- [ ] Security patch
- [ ] Test coverage

## Description

[Why this change, not just what it is -- the motivating problem or gap, and
the reasoning behind the approach taken over the alternatives. Reference an
issue number where one exists.]

<!-- Commit message: the squash commit body, exactly as it will land on
main. Write it inside the fence below: "- Verb ..." bullets (Fix, Add,
Remove), continuation lines indented two spaces, every line at most 72
characters, no closing keywords (put "Closes #N" in the Description).
Keep the section to the fence alone. Nothing else in this description
is copied into the commit. -->

## Commit message

```text
```

## What changed, from the user's point of view

[Bulleted, concrete, from the reader's perspective -- command examples where
relevant, not a restatement of the diff.]

## Impact

[Version bump taken and why (PATCH/MINOR/MAJOR -- see PROJECT.md).
New dependencies, changes to the `papers/` output or a CLI option's shape, or
anything an existing user would have to change how they invoke. Write "none"
if there is none.]

## Test plan

What was actually run, not what was intended (see PROJECT.md,
"Verifying a change"):

- [ ] `uv run pytest --cov --cov-report=term-missing` -- still 100% line
      and branch coverage
- [ ] `uv run ruff check . && uv run ruff format --check . && uv run
      pylint src tests`
- [ ] `uv build`
- [ ] At least one real run against a reference-manager library, not
      only the test fixtures -- [name it here]

## Checklist

- [ ] A failing test was written first, and confirmed failing, for each
      behaviour added or bug fixed.
- [ ] No existing citekey in `citekeys.lock` changes spelling or moves to
      another paper.
- [ ] Corresponding documentation updated, with each claim owned by exactly
      one document.

## Additional information

[Anything else reviewers should know.]
