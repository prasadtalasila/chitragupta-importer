# Release notes template

GitHub has no hook that picks this file up automatically -- copy everything
below the horizontal rule into the GitHub Release body by hand when cutting
a release, leaving this preamble behind. The git tag message is not the
release notes. For how the version number itself is chosen, see
[PROJECT.md](https://github.com/prasadtalasila/chitragupta-importer/blob/main/PROJECT.md),
"Versioning" (absolute, so it still resolves if this preamble
is pasted somewhere by accident).

---

# v<version> -- <YYYY-MM-DD>

## Summary

[Bulleted highlights, written for a reader who wasn't following along
commit-by-commit -- what changed and why it matters, not a raw commit log.]

## What's Changed

- <PR title> by @<author> in <link>

**Full Changelog**: https://github.com/prasadtalasila/chitragupta-importer/compare/v<previous>...v<version>

## In Detail

[Only for a larger release: elaborate the most significant items above under
their own subheadings. Omit this section entirely for a small one.]

## Upgrading

[Only when the release is MAJOR, or otherwise needs an existing user to
change how they invoke the importer or read its output -- the CLI option
that changed shape, a change to the `papers/` layout or the
`citekeys.lock` format, whether a fresh import is required. Omit if nothing is needed.]
