"""Rendering entries, the name table and the bibliography as BibTeX text."""

import re
from collections.abc import Sequence

from chitragupta_importer.model import Item

FIELD_ORDER = (
    "address type series title volume edition copyright isbn issn shorttitle url doi abstract "
    "language number urldate institution school booktitle journal publisher author collaborator "
    "editor month year note keywords pages file cg-collections"
).split()

_ARTICLE_TYPES = ("journalArticle", "magazineArticle", "newspaperArticle")
_ENTRY_TYPES = {
    **dict.fromkeys(_ARTICLE_TYPES, "article"),
    "conferencePaper": "inproceedings",
    "bookSection": "incollection",
    "book": "book",
    "report": "techreport",
    "thesis": "phdthesis",
    "manuscript": "unpublished",
}

# Entry field <- the Zotero fields it is taken from, first non-empty wins.
_SIMPLE_FIELDS = {
    "address": ("place",),
    "type": ("reportType", "thesisType", "genre"),
    "series": ("series",),
    "volume": ("volume",),
    "edition": ("edition",),
    "copyright": ("rights",),
    "isbn": ("ISBN",),
    "issn": ("ISSN",),
    "shorttitle": ("shortTitle",),
    "abstract": ("abstractNote",),
    "language": ("language",),
    "number": ("issue", "number", "reportNumber"),
    "institution": ("institution",),
    "school": ("university",),
    "publisher": ("publisher", "repository", "company"),
    "note": ("extra",),
    "pages": ("pages",),
}
_BOOKTITLE_SOURCES = ("publicationTitle", "proceedingsTitle", "bookTitle")
_ROLE_FIELDS = {"author": "author", "editor": "editor", "contributor": "collaborator"}
_MONTHS = "jan feb mar apr may jun jul aug sep oct nov dec".split()
_SPECIALS = "#$%&_"
_DOI_IN_EXTRA = re.compile(r"^DOI:\s*(\S+)", re.IGNORECASE | re.MULTILINE)


def _paired_braces(text: str) -> set[int]:
    """Indices of the `{` and `}` in `text` that pair up with each other."""
    paired: set[int] = set()
    opened: list[int] = []
    for index, char in enumerate(text):
        if char == "{":
            opened.append(index)
        elif char == "}" and opened:
            paired.update((opened.pop(), index))
    return paired


def _escape(text: str) -> str:
    """Escape Zotero text for a braced BibTeX value; the result stays brace-balanced."""
    paired = _paired_braces(text)
    unpaired = {"{": r"\textbraceleft{}", "}": r"\textbraceright{}"}
    out = []
    for index, char in enumerate(text):
        if char == "\\":
            out.append(r"\textbackslash{}")
        elif char in unpaired:
            out.append("\\" + char if index in paired else unpaired[char])
        elif char in _SPECIALS:
            out.append("\\" + char)
        else:
            out.append(char)
    return "".join(out)


def _protect_case(value: str) -> str:
    """Brace every word after the first that contains an upper-case letter."""
    first, *rest = value.split(" ")
    words = [f"{{{word}}}" if any(c.isupper() for c in word) else word for word in rest]
    return " ".join([first, *words])


def _first(item: Item, names: Sequence[str]) -> str:
    return next((item.fields[name] for name in names if item.fields.get(name)), "")


def _creator_fields(item: Item) -> dict[str, str]:
    names: dict[str, list[str]] = {}
    for creator in item.creators:
        field = _ROLE_FIELDS.get(creator.role)
        if field is None:
            continue
        if creator.single_field:
            name = f"{{{_escape(creator.last)}}}"
        else:
            name = ", ".join(_escape(part) for part in (creator.last, creator.first) if part)
        names.setdefault(field, []).append(name)
    return {field: " and ".join(values) for field, values in names.items()}


def _date_fields(item: Item) -> dict[str, str]:
    date = item.fields.get("date", "")
    year = re.search(r"\d{4}", date)
    if year is None:
        return {}
    fields = {"year": year.group()}
    month = re.match(r"\d{4}-(\d{2})-", date)
    if month and 1 <= int(month.group(1)) <= 12:
        fields["month"] = _MONTHS[int(month.group(1)) - 1]
    return fields


def _doi(item: Item) -> str:
    if item.fields.get("DOI"):
        return item.fields["DOI"]
    match = _DOI_IN_EXTRA.search(item.fields.get("extra", ""))
    return match.group(1) if match else ""


def _escaped_fields(item: Item) -> dict[str, str]:
    """The fields whose values are Zotero text, escaped (and case-protected where due)."""
    fields = {name: _escape(_first(item, sources)) for name, sources in _SIMPLE_FIELDS.items()}
    fields["title"] = _protect_case(_escape(item.fields.get("title", "")))
    if item.item_type in _ARTICLE_TYPES:
        fields["journal"] = _escape(item.fields.get("publicationTitle", ""))
    else:
        fields["booktitle"] = _protect_case(_escape(_first(item, _BOOKTITLE_SOURCES)))
    fields["keywords"] = _escape(", ".join(item.tags))
    return fields


def _field_values(citekey: str, item: Item, slug_paths: Sequence[str]) -> dict[str, str]:
    fields = _escaped_fields(item)
    fields.update(_creator_fields(item))
    fields.update(_date_fields(item))
    fields["url"] = item.fields.get("url", "")
    fields["doi"] = _doi(item)
    fields["urldate"] = item.fields.get("accessDate", "")[:10]
    fields["file"] = f"Full Text PDF:files/{citekey}.pdf:application/pdf"
    fields["cg-collections"] = _escape(", ".join(slug_paths))
    return fields


def render_entry(citekey: str, item: Item, slug_paths: Sequence[str]) -> str:
    """One entry: non-empty fields in FIELD_ORDER, one per line, tab-indented."""
    values = _field_values(citekey, item, slug_paths)
    lines = [f"@{_ENTRY_TYPES.get(item.item_type, 'misc')}{{{citekey},\n"]
    for name in FIELD_ORDER:
        value = values.get(name, "")
        if value:
            written = value if name == "month" else f"{{{value}}}"
            lines.append(f"\t{name} = {written},\n")
    lines.append("}\n")
    return "".join(lines)


def _escape_name(name: str) -> str:
    """A name for the name table: paired braces escaped, an unpaired one a space."""
    paired = _paired_braces(name)
    return "".join(
        ("\\" + char if index in paired else " ") if char in "{}" else char
        for index, char in enumerate(name)
    )


def render_name_table(rows: Sequence[tuple[str, str]]) -> str:
    """The `cg-collections v1` comment block of `(slug path, own name)` rows; "" for none."""
    if not rows:
        return ""
    body = "".join(f"{slug_path}\t{_escape_name(name)}\n" for slug_path, name in rows)
    return f"@comment{{cg-collections v1\n{body}}}\n"


def render_bibliography(name_table: str, entries: Sequence[str]) -> str:
    """The name table (when non-empty) then the entries, one blank line between blocks."""
    blocks = [name_table, *entries] if name_table else list(entries)
    return "\n".join(blocks)
