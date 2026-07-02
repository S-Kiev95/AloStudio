"""Tabular exporters — CSV + a minimal hand-rolled XLSX.

Both take ``(headers, rows)`` where ``rows`` is a list of row-lists and
each cell is a ``str | int | float | None``; ints/floats land as numeric
cells, everything else as text.

Why hand-roll the XLSX (rather than pull in ``openpyxl``): a single
data-grid sheet needs only five tiny OOXML parts, so we keep the
dependency-free posture the rest of the codebase follows (cf. the
hand-rolled SigV4 presigner). The output uses *inline strings*
(``t="inlineStr"``) so there's no shared-string table to maintain — the
structure is the canonical Excel-openable minimum (Content_Types +
package/workbook rels + one worksheet).
"""

from __future__ import annotations

import csv
import io
import zipfile
from typing import Any
from xml.sax.saxutils import escape, quoteattr

XLSX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
CSV_MEDIA_TYPE = "text/csv; charset=utf-8"


def rows_to_csv(headers: list[str], rows: list[list[Any]]) -> bytes:
    """Serialise to UTF-8 CSV with a BOM.

    The leading BOM makes Excel open the file as UTF-8 (so accented
    Spanish names render correctly) rather than the locale codepage.
    """
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerows(rows)
    return ("\ufeff" + buf.getvalue()).encode("utf-8")


def _col_letter(index: int) -> str:
    """0 → ``A``, 25 → ``Z``, 26 → ``AA`` (spreadsheet column names)."""
    letters = ""
    n = index + 1
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def _cell_xml(col: int, row: int, value: Any) -> str:
    ref = f"{_col_letter(col)}{row}"
    # ``bool`` is an ``int`` subclass — pin it to 0/1 numeric so it never
    # renders as an inline "True"/"False" string.
    if isinstance(value, bool):
        return f'<c r="{ref}" t="n"><v>{int(value)}</v></c>'
    if isinstance(value, (int, float)):
        return f'<c r="{ref}" t="n"><v>{value}</v></c>'
    text = escape("" if value is None else str(value))
    return (
        f'<c r="{ref}" t="inlineStr">'
        f'<is><t xml:space="preserve">{text}</t></is></c>'
    )


def _sanitize_sheet_name(name: str) -> str:
    """Excel sheet names: ≤31 chars, none of ``[]:*?/\\``."""
    cleaned = "".join(c for c in name if c not in set("[]:*?/\\")).strip()
    return (cleaned or "Sheet1")[:31]


def rows_to_xlsx(
    sheet_name: str, headers: list[str], rows: list[list[Any]]
) -> bytes:
    """Serialise to a single-sheet ``.xlsx`` workbook (inline strings)."""
    sheet_name = _sanitize_sheet_name(sheet_name)
    row_xml: list[str] = []
    for r_idx, row in enumerate([headers, *rows], start=1):
        cells = "".join(
            _cell_xml(c_idx, r_idx, value)
            for c_idx, value in enumerate(row)
        )
        row_xml.append(f'<row r="{r_idx}">{cells}</row>')
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns='
        '"http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(row_xml)}</sheetData>'
        "</worksheet>"
    )
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns='
        '"http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType='
        '"application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" ContentType='
        '"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/worksheets/sheet1.xml" ContentType='
        '"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        "</Types>"
    )
    root_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns='
        '"http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type='
        '"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/></Relationships>'
    )
    workbook = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns='
        '"http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r='
        '"http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets><sheet name={quoteattr(sheet_name)} "
        'sheetId="1" r:id="rId1"/></sheets></workbook>'
    )
    workbook_rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns='
        '"http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type='
        '"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        'Target="worksheets/sheet1.xml"/></Relationships>'
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", root_rels)
        zf.writestr("xl/workbook.xml", workbook)
        zf.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        zf.writestr("xl/worksheets/sheet1.xml", sheet)
    return buf.getvalue()


__all__ = [
    "CSV_MEDIA_TYPE",
    "XLSX_MEDIA_TYPE",
    "rows_to_csv",
    "rows_to_xlsx",
]
