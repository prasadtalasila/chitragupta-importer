# Duplicate items are merged in code, keeping Zotero's default master

The Zotero data holds 34 groups of duplicate items (same type, same title,
shared DOI or PDF), and the existing bibliography has an entry for each copy
in 24 of them. The importer merges each group itself before anything else:
one survivor carries the group's attachments, collections and tags, the
others are reported as duplicates. The survivor is the item Zotero's own
merge would keep by default (oldest date added), so cleaning up in Zotero
later with the default master changes no frozen citekey. When several
existing entries name one merged item, bootstrap freezes one key by a fixed
rule and lists the rest as dropped, so drafts citing them can be updated.

## Considered Options

- **Merge only in Zotero.** Cleans the library, but the importer would still
  refuse on the next duplicate and still needs the dropped-key rule.
- **Give the survivor every entry's key.** Impossible: an entry has one
  citekey and chitragupta reads no aliases.

## Consequences

- Merging in Zotero with a non-default master retires the frozen key and
  creates a new one (see chitragupta-importer#4).
- The grouping takes any items and a pluggable survivor rule, ready for
  duplicates across reference managers once an import run reads several
  libraries.
