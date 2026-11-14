# Collection names travel in the bib; both locks are private to the importer

Slugs alone cannot be matched to a request like "an essay on digital twin
platforms", so chitragupta needs collection names. They go in a
`@comment{cg-collections v1 ...}` table at the top of `bibliography.bib`
(slug path, tab, the collection's own name), not in `collections.lock`.
chitragupta reads neither `citekeys.lock` nor `collections.lock`: the bib
plus `files/` stays a self-contained input that cannot drift from a sidecar,
and the locks stay free to change shape with the importer.

## Considered Options

- **chitragupta reads `collections.lock`.** It already holds every name, but
  it would become a shared contract, a bib copied without it loses its names,
  and an interrupted run could leave names out of step with slugs.
- **chitragupta reads `citekeys.lock` to catch renamed keys**
  (chitragupta-importer#1). Rejected: the importer never renames a key, and
  chitragupta's ledger already stores a `pdf_hash` per citekey, which detects
  "same PDF, new key" from any source.
