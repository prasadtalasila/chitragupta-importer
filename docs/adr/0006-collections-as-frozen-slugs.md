# Collections reach chitragupta as frozen slug paths in `cg-collections`

Each collection gets a segment slug (lower-case `[a-z0-9-]`) frozen per
collection id in `papers/collections.lock`; a collection's slug path joins
segments from the root with `.`, and each entry lists its slug paths in a
`cg-collections` field. A rename in the reference manager therefore changes
no slug, so drafts that recorded a collection scope keep working; a move
changes the path; same-named siblings stay distinct.

## Considered Options

- **Keep `groups` with `>` between levels.** Rejected: `>` is shell output
  redirection (an unquoted `--collection A > B` writes a file), names are not
  escaped, and a rename silently breaks every stored scope.
- **`/` paths of names with JSON Pointer escaping.** Readable and cheap, but
  renames and moves still break stored scopes and a move can merge two
  same-named siblings.
- **`::` or `.` between names.** Every shell-safe separator already occurs in
  the reference library's labels (`::` and `/` in tags, `.` in
  `Industry 5.0`).

## Consequences

- The field is namespaced `cg-` because `collection` already names BibTeX and
  biblatex entry types (`@incollection`, `@collection`) and CSL's series
  variables. Reference managers keep their own words (Zotero collections,
  JabRef groups, Mendeley folders).
- The importer no longer writes `groups`; no backward compatibility.
- chitragupta must change to read the field (filed as a chitragupta issue).
