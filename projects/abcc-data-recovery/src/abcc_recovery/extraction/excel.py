"""Spreadsheet/CSV extraction (EXL-001 .. EXL-004, FD-003).

Preserves worksheets, columns, row order, values and headings exactly as
recovered.  The raw copy is produced before any transformation (EXL-002).

Formula handling (EXL-004): cached (calculated) values are extracted as the
delivered values; every cell that held a formula is recorded in
``formula_cells`` so no formula is silently removed.  Formula text is never
re-executed and is kept for documentation only (SPEC section 23).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from ..recovery import file_detector

log = logging.getLogger("abcc_recovery.extraction.excel")

try:  # optional dependency for legacy .xls
    import xlrd  # type: ignore
except ImportError:  # pragma: no cover - depends on environment
    xlrd = None


class ExtractionError(Exception):
    """ERR-003: extraction errors identify the failing source/sheet/page."""


def _cell_value(value: Any) -> Any:
    """Convert cell values to JSON-safe primitives without altering them."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)  # dates and other objects -> ISO-ish string


def _extract_xlsx(path: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    import io

    from openpyxl import load_workbook

    # Load from bytes, not the path: the real type was already established
    # by content (FD-001), and a recovered filename may carry a misleading
    # extension that openpyxl would otherwise reject.
    with open(path, "rb") as fh:
        payload = fh.read()
    wb_values = load_workbook(io.BytesIO(payload), data_only=True, read_only=False)
    wb_formulas = load_workbook(io.BytesIO(payload), data_only=False, read_only=False)
    sheets: list[dict[str, Any]] = []
    formula_cells: list[dict[str, Any]] = []
    for name in wb_values.sheetnames:
        ws_v = wb_values[name]
        ws_f = wb_formulas[name]
        raw_rows: list[list[Any]] = []
        for row in ws_v.iter_rows():
            raw_rows.append([_cell_value(cell.value) for cell in row])
        # EXL-004: record cells that contain formulas
        for row in ws_f.iter_rows():
            for cell in row:
                if isinstance(cell.value, str) and cell.value.startswith("="):
                    formula_cells.append(
                        {"sheet": name, "cell": cell.coordinate, "formula": cell.value}
                    )
        # trim fully-empty trailing rows/cols for the raw copy
        while raw_rows and all(v is None or v == "" for v in raw_rows[-1]):
            raw_rows.pop()
        sheets.append({"name": name, "raw_rows": raw_rows})
    return sheets, formula_cells


def _extract_xls(path: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if xlrd is None:
        raise ExtractionError(
            f"{os.path.basename(path)}: legacy .xls requires the optional 'xlrd' package"
        )
    book = xlrd.open_workbook(path)
    sheets = []
    for sheet in book.sheets():
        raw_rows = [
            [_cell_value(sheet.cell_value(r, c)) for c in range(sheet.ncols)]
            for r in range(sheet.nrows)
        ]
        while raw_rows and all(v is None or v == "" for v in raw_rows[-1]):
            raw_rows.pop()
        sheets.append({"name": sheet.name, "raw_rows": raw_rows})
    return sheets, []


def _extract_csv(path: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    with open(path, "rb") as fh:
        data = fh.read()
    rows = file_detector.read_csv_rows(data)
    return [{"name": "csv", "raw_rows": rows}], []


def extract_spreadsheet(path: str) -> dict[str, Any]:
    """Extract all sheets from a recovered spreadsheet/CSV file.

    The file's real type is detected from magic bytes (FD-001/FD-003), never
    from the extension alone.
    """
    with open(path, "rb") as fh:
        head = fh.read(8192)
    detected = file_detector.detect_file_type(head)
    if detected == file_detector.TYPE_HTML:
        raise ExtractionError(
            f"{os.path.basename(path)}: HTML content rejected (FD-004); not a spreadsheet"
        )
    if detected not in (
        file_detector.TYPE_XLSX,
        file_detector.TYPE_XLS,
        file_detector.TYPE_CSV,
    ):
        raise ExtractionError(
            f"{os.path.basename(path)}: content is '{detected}', not a spreadsheet (ERR-002)"
        )
    try:
        if detected == file_detector.TYPE_XLSX:
            sheets, formulas = _extract_xlsx(path)
            method = "openpyxl"
        elif detected == file_detector.TYPE_XLS:
            sheets, formulas = _extract_xls(path)
            method = "xlrd"
        else:
            sheets, formulas = _extract_csv(path)
            method = "csv-sniff"
    except ExtractionError:
        raise
    except Exception as exc:  # noqa: BLE001 - ERR-003: identify failing source
        raise ExtractionError(
            f"{os.path.basename(path)}: extraction failed: {exc}"
        ) from exc
    log.info(
        "[extraction] Extracted %d sheet(s) from %s (%s)",
        len(sheets),
        os.path.basename(path),
        method,
    )
    return {
        "source_file": path,
        "file_type": detected,
        "extraction_method": method,
        "sheets": sheets,
        "formula_cells": formulas,
    }


def records_from_extraction(
    extraction: dict[str, Any], source_id: str
) -> list[dict[str, Any]]:
    """Flatten extracted sheets into raw records with lineage (EXL-003, LIN-002).

    The first non-empty row of each sheet is treated as the heading row; all
    remaining rows become records keyed by those headings.  No business
    schema is imposed (RAW-003).
    """
    records: list[dict[str, Any]] = []
    seq = 0
    for sheet in extraction["sheets"]:
        rows = sheet["raw_rows"]
        headings: Optional[list[str]] = None
        for row_index, row in enumerate(rows, start=1):
            if headings is None:
                if any(v not in (None, "") for v in row):
                    headings = [
                        str(v).strip() if v not in (None, "") else f"column_{i + 1}"
                        for i, v in enumerate(row)
                    ]
                continue
            if all(v in (None, "") for v in row):
                continue  # skip fully empty rows
            seq += 1
            fields = {
                headings[i]: _cell_value(row[i]) if i < len(row) else None
                for i in range(len(headings))
            }
            records.append(
                {
                    "raw_id": f"RAW-{seq:06d}",
                    "source_id": source_id,
                    "source_file": os.path.basename(extraction["source_file"]),
                    "sheet": sheet["name"],
                    "page": None,
                    "row_number": row_index,
                    "seq": seq,
                    "fields": fields,
                }
            )
    return records
