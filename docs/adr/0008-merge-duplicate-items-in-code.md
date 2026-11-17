# Duplicate items are merged in code, on request

The Zotero data holds 48 groups of duplicate items (same type and title, with
a shared DOI, URL or PDF). Zotero's exporter keeps every copy as its own
entry, the later one with a `-1` clash suffix, so the existing bibliography
has an entry for each copy. An import run finds the groups itself and, by
default, lists them and refuses to write; with `--merge-duplicates` it keeps
one survivor per group (the copy with its own PDF, else the oldest) and
reports the rest. Bootstrap freezes the key of the entry that matched the
survivor's own PDF and lists the other keys as dropped, so drafts citing
them can be updated; `--dry-run` shows all of this before anything is
written.

## Considered Options

- **Merge only in Zotero.** Cleans the library, but the importer would still
  need the dropped-key rule for the existing bibliography.
- **Keep every copy, as Zotero's exporter does.** Gives chitragupta two
  entries and two PDFs for one work.
- **Survivor = Zotero's default merge master (the oldest).** Rejected: the
  copy with the PDF is the one worth keeping.

## Consequences

- Merging in Zotero later with a master other than the survivor retires the
  frozen key and creates a new one (see chitragupta-importer#4).
- A URL alone groups items only through a bootstrap tie that the title
  cannot break, so a generic URL shared by distinct works does not merge them.
- The grouping takes any items and a pluggable survivor rule, ready for
  duplicates across reference managers once an import run reads several
  libraries.
