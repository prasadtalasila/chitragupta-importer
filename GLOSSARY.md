# chitragupta-importer

Reads a reference manager's own storage and writes one papers directory
that chitragupta drafts from, without chitragupta knowing where it came
from.

## Sources

**Reference manager**:
An application a person keeps their papers in, such as Zotero, Mendeley or
JabRef.
_Avoid_: citation manager, bibliography manager

**Collection**:
A named, nestable folder a person sorts items into inside a reference
manager; an item can be in many.
_Avoid_: group, folder, category, shelf

**Data directory**:
Where a reference manager keeps its own storage; for Zotero, the folder
holding `zotero.sqlite` and `storage/`.
_Avoid_: profile, database (for the whole folder)

**Library**:
One reference manager's set of items: a Zotero personal library, or one
Zotero group library.
_Avoid_: corpus, collection (for the whole set)

**Item**:
One record in a library: a paper, book, chapter or web page with its
metadata and attachments. One item becomes at most one entry.
_Avoid_: paper, reference, document

**Item ID**:
The reference manager's own stable identifier for an item, together with its
library, such as `zotero:user/ABCD2345`.
_Avoid_: source id, item key

**Collection ID**:
The reference manager's own stable identifier for a collection, together
with its library.
_Avoid_: source id, collection key

**Attachment**:
A file stored with an item in a reference manager, such as a PDF or an HTML
snapshot.

**Main PDF**:
The one PDF attachment of an item that is imported: the one whose file name
has the lowest hash.
_Avoid_: primary PDF, full text

**Duplicate group**:
Items of one library that are the same work: same item type, same
normalised title, and a shared DOI, URL or identical PDF bytes; or items an
existing entry ties at the URL level that the title cannot separate.
_Avoid_: duplicate set, clones

**Survivor**:
The one item of a duplicate group that is imported: the one with its own
PDF, else the oldest; it carries the group's collection memberships and
tags, and the others are reported as duplicates of it.
_Avoid_: master, canonical item

## Import

**Import run**:
One execution of the importer, reading exactly one library and rewriting
the papers directory.
_Avoid_: export, sync

**Included item**:
An item with a main PDF on disk, which becomes an entry.
_Avoid_: exported item

**Left-out item**:
An item with no PDF on disk, which the import run lists and skips.
_Avoid_: skipped item, dropped item

## Output

**Papers directory**:
The directory the importer writes and chitragupta reads: the bibliography,
the PDFs under `files/`, and the importer's two locks.
_Avoid_: corpus, output folder, export

**Bibliography**:
The one BibTeX file the importer writes, `papers/bibliography.bib`.
_Avoid_: bib, bib file, BibTeX file

**Existing bibliography**:
A bibliography written before the importer existed, read once by bootstrap
for the citekeys drafts already cite.

**Entry**:
One record in the bibliography, made from one included item.
_Avoid_: item, reference

**Consumer**:
chitragupta, the only reader of the papers directory, which never learns
the importer exists.

## Citekeys

**Citekey**:
The identifier an entry is cited by, which also names its PDF.
_Avoid_: citation key, bibkey, key

**Safe citekey**:
A citekey with no character or form that cannot appear in a file name on
Linux, macOS or Windows; every citekey must be safe.
_Avoid_: valid citekey, legal citekey

**Frozen citekey**:
A citekey that, once written, never changes spelling and never moves to a
different item.
_Avoid_: stable key, pinned key

**Key rule**:
The pattern a new citekey is built from, `<author>_<titleword>_<year>`
shortened to at most 20 characters (the author part to at most 10), with a
clash suffix assigned once.

**Citekey lock**:
The importer's permanent record of every citekey it has assigned, by item
ID, in `citekeys.lock`.
_Avoid_: index, registry, mapping

**Clash suffix**:
The `-N` added once to the second and later claimants of the same citekey,
or of the same segment slug among siblings, and never changed afterwards.
_Avoid_: disambiguator, counter

**Bootstrap**:
The one-time first import that freezes the citekeys drafts already cite,
taken from an existing bibliography.

## Collections in the output

**Segment slug**:
The lower-case `[a-z0-9-]` form of one collection's name, frozen to that
collection.

**Slug path**:
The segment slugs of a collection and its ancestors, from the root, joined
by `.`, such as `tide-pools.tp-gauges`.
_Avoid_: collection path, group path

**Collection lock**:
The importer's permanent record of every collection that has held an
included item, by collection ID, with its segment slug, parent and name,
in `collections.lock`.
_Avoid_: index, registry, mapping

**Direct membership**:
An item's placement in a collection, made by a person in the reference
manager.

**Implied membership**:
An item's membership in every ancestor of a collection it is directly in;
never written, always derived from slug paths.

**Display path**:
The names of a collection and its ancestors, from the root, joined by
` / `, such as `Tide Pools / TP Gauges`; only shown or matched whole,
never split back into names.
_Avoid_: collection path, full name

**`cg-collections`**:
The bibliography field listing the slug paths of an item's direct
memberships.
_Avoid_: groups, collections

**Name table**:
The block at the top of the bibliography that gives each slug path its
collection's own name.

## Change over time

**Retired**:
Said of a citekey or collection whose item or collection is gone from the
library: its record is kept and it is never reused, except that a collection
re-created under the same parent with the same name may take back its
retired segment slug.
_Avoid_: deleted, stale

**Dormant citekey**:
The citekey of an item that still exists but is currently left out; it
is kept, not reused, and returns when the item is included again.
_Avoid_: suspended, inactive

**Dropped citekey**:
A citekey of the existing bibliography that bootstrap did not freeze because
another entry for the same item (a survivor, or an item merged in Zotero) was
frozen instead. It is kept in `citekeys.lock` as a line with the pseudo item
ID `dropped:<citekey>` and the citekey itself as the value, for example
`dropped:smith_tides_2020-1<TAB>smith_tides_2020-1`: the lock holds one item
ID per line and no item holds the key, and the value is what keeps the
spelling from being given to another item.
_Avoid_: lost key, alias

**Rename**:
A collection keeping its collection ID and parent but changing its name;
its slug path does not change.

**Move**:
A collection keeping its collection ID but changing its parent; its segment
slug stays and its slug path follows the new parent.
