# Import lives in a separate package; chitragupta reads only the bib and PDFs

Reading a reference manager's storage moves out of chitragupta into this
package, which writes a `papers/` directory (`bibliography.bib` plus
`files/`) and nothing else that chitragupta reads. chitragupta never learns
the importer exists, keeps its one-reader rule for bibliographic data, and is
insulated from reference managers' schema changes, which land on this
package's release cadence instead. The output is a diffable artefact a person
can review before `corpus sync`.

## Considered Options

- **An import layer inside chitragupta.** Rejected: bends the one-reader
  rule and makes a reference manager's database a core input.
- **A `chitragupta[zotero]` extra.** Rejected: same schema-churn cost inside
  the core distribution.
- **A runtime dependency on chitragupta for shared helpers.** Rejected: the
  shared pieces are a few small functions; the output grammar is held as a
  contract instead.

Source: chitragupta-importer#1.
