# One package imports from many reference managers

This package will read Zotero first and Mendeley, JabRef and others later,
each as a source module producing the same item records and the same
`papers/` output. This supersedes chitragupta-importer#1's plan of one
sibling package per reference manager: one package keeps one citekey rule,
one lock, one slug rule and one output writer, so the output stays
consistent across sources.
