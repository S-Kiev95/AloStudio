"""Unit tests for the CSV + XLSX serialisers — pure, no IO."""

from __future__ import annotations

import io
import zipfile
from xml.etree import ElementTree as ET

import pytest

from app.core.exporters import (
    CSV_MEDIA_TYPE,
    XLSX_MEDIA_TYPE,
    rows_to_csv,
    rows_to_xlsx,
)

pytestmark = pytest.mark.unit


def test_csv_has_bom_header_and_escaping():
    body = rows_to_csv(
        ["ID", "Nombre", "Nota"],
        [[1, "Ángela", 'dijo "hola", ok'], [2, "Beto", ""]],
    )
    assert body.startswith(b"\xef\xbb\xbf")  # UTF-8 BOM for Excel
    text = body.decode("utf-8-sig")
    lines = text.splitlines()
    assert lines[0] == "ID,Nombre,Nota"
    # A value containing a comma + quotes is CSV-quoted + accents survive.
    assert lines[1] == '1,Ángela,"dijo ""hola"", ok"'
    assert lines[2] == "2,Beto,"


def test_xlsx_is_a_valid_single_sheet_workbook():
    body = rows_to_xlsx(
        "Reporte agent", ["ID", "Nombre"], [[7, "Ángela"], [8, "Beto"]]
    )
    zf = zipfile.ZipFile(io.BytesIO(body))
    parts = set(zf.namelist())
    assert {
        "[Content_Types].xml",
        "_rels/.rels",
        "xl/workbook.xml",
        "xl/_rels/workbook.xml.rels",
        "xl/worksheets/sheet1.xml",
    } <= parts
    # Every part is well-formed XML.
    for name in parts:
        ET.fromstring(zf.read(name))
    sheet = zf.read("xl/worksheets/sheet1.xml").decode("utf-8")
    # Numbers land as numeric cells; strings as inline strings.
    assert '<c r="A2" t="n"><v>7</v></c>' in sheet
    assert "Ángela" in sheet and 'r="B2" t="inlineStr"' in sheet


def test_xlsx_escapes_xml_and_pins_bool_to_number():
    body = rows_to_xlsx("S", ["h"], [["<b> & 'x'"], [True]])
    sheet = zipfile.ZipFile(io.BytesIO(body)).read(
        "xl/worksheets/sheet1.xml"
    ).decode("utf-8")
    assert "&lt;b&gt; &amp; " in sheet  # angle brackets + ampersand escaped
    # bool is an int subclass but must serialise as 0/1, never "True".
    assert '<c r="A3" t="n"><v>1</v></c>' in sheet
    assert "True" not in sheet


def test_media_type_constants():
    assert CSV_MEDIA_TYPE.startswith("text/csv")
    assert XLSX_MEDIA_TYPE.endswith("spreadsheetml.sheet")
