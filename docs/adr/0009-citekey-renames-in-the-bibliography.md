# Citekey renames travel in the bibliography; long frozen keys are renamed once

When a citekey leaves the bibliography and the same paper has another key,
drafts citing the old key should be rewritten without anyone doing it by
hand. chitragupta 7.0.0 reads an optional `@comment{cg-renames v1 ...}`
block of `old<TAB>new` rows and does exactly that; on its own it catches a
rename only when the two PDFs hash the same. The importer knows the renames
chitragupta cannot see (a dropped citekey, an item merged here or in Zotero),
records every one in a private `papers/renames.lock`, and writes the block
from it on each run, chains followed to the last successor. The owner also
wants short keys, so a frozen citekey longer than 30 characters is renamed
once to a key from the key rule, its old spelling reserved as
`renamed:<old>` in `citekeys.lock`. This amends ADR-0004: a citekey still
never moves to another paper, but it may change spelling that once.

## Considered Options

- **Rows in `citekeys.lock`** (`renamed:<old>` -> new): the lock refuses a key
  held by two lines, and changing its format is a breaking change.
- **A survivor column on `dropped:` lines**: an older importer would misread
  the key and lose its reservation, and it covers dropped citekeys only.
- **chitragupta reads the locks**: rejected in ADR-0007.

## Consequences

- `citekeys.lock` keeps its format; `renames.lock` is new and private, and
  the block is optional for any reader of `papers/`.
- A dropped citekey's successor is known only during a bootstrap.
- A renamed key's old PDF stays in `files/` and is reported as unreferenced.
