# Export only items with a valid PDF, one PDF each

An item is exported only if it has a PDF attachment that exists on disk;
every other item is left out and listed with its reason, and gets no lock
line (bootstrap reserves no key for it; if it gains a PDF later it gets a
new key). chitragupta can only cite a paper it has parsed from a PDF, so a
PDF-less entry adds nothing to the corpus. An item with several PDFs (19 in
the reference library) exports exactly one, the one whose file name has the
lowest SHA-256 hash, ties broken by full path: deterministic, independent of
attachment order, and matching chitragupta, which reads only the first PDF.
It is copied to `papers/files/<citekey>.pdf`.
