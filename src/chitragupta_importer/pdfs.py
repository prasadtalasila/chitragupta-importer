"""Choosing an item's main PDF, or naming why the item is left out."""

from enum import StrEnum
from hashlib import sha256
from pathlib import Path

from chitragupta_importer.model import Attachment, Item


class LeftOutReason(StrEnum):
    """Why an item has no main PDF on disk and is left out of the import run."""

    NO_ATTACHMENT = "no attachment"
    NO_PDF_ATTACHMENT = "no PDF attachment"
    PDF_MISSING_ON_DISK = "PDF missing on disk"


def is_pdf(attachment: Attachment) -> bool:
    """Whether the attachment is a PDF, by content type or `.pdf` file name."""
    return attachment.content_type == "application/pdf" or (
        attachment.file_name.lower().endswith(".pdf")
    )


def main_pdf(item: Item) -> Path | LeftOutReason:
    """Return the path of the item's main PDF, or why the item is left out.

    Among PDF attachments on disk, the main PDF is the one whose file name
    has the lowest SHA-256 hash; equal names are ordered by full path.
    """
    if not item.attachments:
        return LeftOutReason.NO_ATTACHMENT
    pdfs = [attachment for attachment in item.attachments if is_pdf(attachment)]
    if not pdfs:
        return LeftOutReason.NO_PDF_ATTACHMENT
    on_disk = [
        (sha256(pdf.file_name.encode()).hexdigest(), str(pdf.path), pdf.path)
        for pdf in pdfs
        if pdf.path is not None and pdf.path.is_file()
    ]
    if not on_disk:
        return LeftOutReason.PDF_MISSING_ON_DISK
    return min(on_disk)[2]
