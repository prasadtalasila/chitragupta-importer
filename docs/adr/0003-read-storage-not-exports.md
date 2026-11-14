# Read the reference manager's own storage, not its BibTeX export

The importer opens `zotero.sqlite` read-only (and later each manager's own
store) rather than parsing a `.bib` export or calling an API. Only the
storage has stable item ids, collection ids and hierarchy, and attachment
paths together: Zotero's own export drops collections and builds citekeys at
export time; Better BibTeX's keys differ from the ones drafts cite and its
exports in the reference library carry no `file` fields; the local and web
APIs need Zotero running or credentials. The cost, an internal schema with no
compatibility promise, is contained by refusing any schema version the
importer does not know (Zotero `userdata` 121 today). The importer never
writes to a reference manager's files.
