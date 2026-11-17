"""Rendering entries, the name table and the bibliography as BibTeX text."""

import re
from collections.abc import Sequence
from dataclasses import replace

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
# Zotero's publicationTitle and the fields it stands for in other item types.
_PUBLICATION_SOURCES = (
    "publicationTitle proceedingsTitle bookTitle websiteTitle blogTitle forumTitle "
    "programTitle encyclopediaTitle dictionaryTitle"
).split()
_BOOKTITLE_TYPES = ("conferencePaper", "bookSection")
_CASE_PROTECTED = ("title", "shorttitle", "series", "type", "booktitle")
_ROLE_FIELDS = {
    "author": "author",
    "editor": "editor",
    "seriesEditor": "editor",
    "contributor": "collaborator",
}
# A `<label>: <value>` line of Zotero's `extra` that becomes the item's field.
_EXTRA_LINE_FIELDS = {"publisher": "publisher", "issn": "ISSN", "doi": "DOI"}
_MONTHS = "jan feb mar apr may jun jul aug sep oct nov dec".split()
_SPECIALS = "#$%&_"
_TEXT_COMMANDS = {
    "\\": r"{\textbackslash}",
    "|": r"{\textbar}",
    "<": r"{\textless}",
    ">": r"{\textgreater}",
    "~": r"{\textasciitilde}",
    "^": r"{\textasciicircum}",
}
_LETTERS_AND_DIGITS = re.compile(r"[^\W_]+")
_PAGE_DASHES = re.compile("[-\u2012-\u2015\u2212]+")


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
        if char in _TEXT_COMMANDS:
            out.append(_TEXT_COMMANDS[char])
        elif char in unpaired:
            out.append("\\" + char if index in paired else unpaired[char])
        elif char in _SPECIALS:
            out.append("\\" + char)
        else:
            out.append(char)
    return "".join(out)


def _encode_unpaired_braces(text: str) -> str:
    """Percent-encode the unpaired `{` and `}` of a URL or DOI; the rest stays raw."""
    paired = _paired_braces(text)
    encoded = {"{": "%7B", "}": "%7D"}
    return "".join(
        encoded[char] if char in encoded and index not in paired else char
        for index, char in enumerate(text)
    )


def _protect_case(value: str) -> str:
    """Brace each run of letters and digits holding an upper-case letter.

    A run that starts the value is left alone when its only upper-case letter is
    its first, as in Zotero's built-in exporter.
    """

    def brace(match: re.Match) -> str:
        run = match.group()
        rest = run[1:] if match.start() == 0 else run
        return f"{{{run}}}" if any(c.isupper() for c in rest) else run

    return _LETTERS_AND_DIGITS.sub(brace, value)


def _take_extra_lines(item: Item) -> Item:
    """Move `Publisher:`, `ISSN:` and `DOI:` lines of `extra` into the item's empty fields.

    The lines leave `extra` (and so `note`) even when the item's own field wins.
    """
    fields = dict(item.fields)
    kept = []
    for line in fields.get("extra", "").split("\n"):
        label, colon, value = line.partition(":")
        name = _EXTRA_LINE_FIELDS.get(label.strip().casefold())
        if name is None or not colon or not value.strip():
            kept.append(line)
        elif not fields.get(name):
            fields[name] = value.strip()
    fields["extra"] = "\n".join(kept)
    return replace(item, fields=fields)


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


def _escaped_fields(item: Item) -> dict[str, str]:
    """The fields whose values are Zotero text, escaped (and case-protected where due)."""
    fields = {name: _escape(_first(item, sources)) for name, sources in _SIMPLE_FIELDS.items()}
    fields["title"] = _escape(item.fields.get("title", ""))
    publication = "booktitle" if item.item_type in _BOOKTITLE_TYPES else "journal"
    fields[publication] = _escape(_first(item, _PUBLICATION_SOURCES))
    for name in _CASE_PROTECTED:
        fields[name] = _protect_case(fields.get(name, ""))
    fields["pages"] = _PAGE_DASHES.sub("--", fields["pages"])
    fields["keywords"] = _escape(", ".join(item.tags))
    return fields


def _field_values(citekey: str, item: Item, slug_paths: Sequence[str]) -> dict[str, str]:
    fields = _escaped_fields(item)
    fields.update(_creator_fields(item))
    fields.update(_date_fields(item))
    fields["url"] = _encode_unpaired_braces(item.fields.get("url", ""))
    fields["doi"] = _encode_unpaired_braces(item.fields.get("DOI", ""))
    fields["urldate"] = item.fields.get("accessDate", "")[:10]
    fields["file"] = f"Full Text PDF:files/{citekey}.pdf:application/pdf"
    fields["cg-collections"] = _escape(", ".join(slug_paths))
    return fields


def render_entry(citekey: str, item: Item, slug_paths: Sequence[str]) -> str:
    """One entry: non-empty fields in FIELD_ORDER, one per line, tab-indented."""
    values = _field_values(citekey, _take_extra_lines(item), slug_paths)
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
