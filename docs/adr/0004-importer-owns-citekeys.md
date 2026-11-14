# The importer creates citekeys and freezes them

Zotero stores no citation key (0 of 644 items in the reference library) and
builds one at export time, so 86 keys carry an export-order `-1` suffix that
a later export can move to another paper. The importer therefore assigns
every key itself and records it in `papers/citekeys.lock` against the
source's item id; a written key never changes spelling and never moves to
another paper, even after its item is deleted. Keys drafts already cite are
frozen by a one-time bootstrap from the existing `bibliography-groups.bib`,
matched by PDF content hash first (497 of 498 match). New keys follow the
shape of the frozen ones, `<author>_<titleword>_<year>`, with clash suffixes
assigned once.

## Considered Options

- **Use only a key the person stored in the reference manager, leaving out
  items without one** (chitragupta-importer#1). Rejected: needs every key
  typed into Zotero by hand, and the format would not stay consistent.
- **Write keys back into Zotero's Citation Key field.** Rejected: the
  importer never writes to a reference manager's files.

## Consequences

- A paper deleted and re-added in Zotero gets a new item id and therefore a
  new key (chitragupta-importer#4 tracks giving it the old one back).
- Every key, frozen or new, must pass chitragupta's `citekey_safety` rule,
  because the key also names `files/<citekey>.pdf`; an unsafe frozen key
  stops the bootstrap (none of the 644 is unsafe).
