"""Normalised match keys of items: DOI, title and PDF content hash."""

import re
from hashlib import sha256
from pathlib import Path

from chitragupta_importer.model import Item
from chitragupta_importer.pdfs import is_pdf

_DOI_PREFIX = re.compile(r"^(https://doi\.org/|http://dx\.doi\.org/|doi:)")
_EXTRA_DOI = re.compile(r"^DOI:(.*)$", re.MULTILINE)


def hash_file(path: Path) -> str:
    """The SHA-256 hex digest of the file's bytes."""
    return sha256(path.read_bytes()).hexdigest()


def item_pdf_hashes(item: Item) -> set[str]:
    """Hashes of the item's PDF attachments found on disk."""
    return {
        hash_file(a.path)
        for a in item.attachments
        if is_pdf(a) and a.path is not None and a.path.is_file()
    }


def normal_doi(text: str) -> str:
    """Lower-case the DOI and strip a resolver or `doi:` prefix."""
    return _DOI_PREFIX.sub("", text.strip().lower()).strip()


def normal_title(text: str) -> str:
    """Case-fold the title and keep only its letters and digits."""
    return "".join(c for c in text.casefold() if c.isalnum())


def item_dois(item: Item) -> set[str]:
    """Normalised DOIs from the field `DOI` and `DOI:` lines of `extra`; may hold ""."""
    extra = _EXTRA_DOI.findall(item.fields.get("extra", ""))
    return {normal_doi(text) for text in [item.fields.get("DOI", ""), *extra]}
