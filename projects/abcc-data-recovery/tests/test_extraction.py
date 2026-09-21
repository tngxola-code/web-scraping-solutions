"""Extraction tests (SPEC section 22): Excel/CSV/PDF fixtures, multiline
handling and empty-input handling."""

from __future__ import annotations

import os
import shutil

import pytest

from abcc_recovery.extraction import excel as xl
from abcc_recovery.extraction import pdf as pdf_mod
from abcc_recovery.extraction.excel import ExtractionError
from abcc_recovery.processing.normalize import normalize_records
from tests.fixtures import (PAGE1_LINES, make_csv, make_empty_csv,
                            make_empty_xlsx, make_pdf, make_scanned_pdf)

HAS_REPORTLAB = True
try:
    import reportlab  # noqa: F401
except ImportError:
    HAS_REPORTLAB = False


# ----------------------------------------------------------------------
# Excel / CSV
# ----------------------------------------------------------------------
def test_excel_extraction_preserves_structure(xlsx_fixture):
    result = xl.extract_spreadsheet(xlsx_fixture)
    assert result["file_type"] == "xlsx"
    names = [s["name"] for s in result["sheets"]]
    assert names == ["Clauses", "Extra"]  # EXL-003 all sheets inspected
    first = result["sheets"][0]
    assert first["raw_rows"][0] == ["Clause No", "Clause Text", "Notes"]  # EXL-001
    # EXL-001 row order preserved
    assert first["raw_rows"][1][0] == "1"
    assert first["raw_rows"][2][0] == "2"


def test_excel_formula_cells_recorded(xlsx_fixture):
    """EXL-004: cached values extracted; formula cells documented."""
    result = xl.extract_spreadsheet(xlsx_fixture)
    assert result["formula_cells"], "formula cells must be recorded"
    cell = result["formula_cells"][0]
    assert cell["sheet"] == "Clauses"
    assert cell["formula"].startswith("=")


def test_records_from_excel_have_lineage(xlsx_fixture):
    result = xl.extract_spreadsheet(xlsx_fixture)
    records = xl.records_from_extraction(result, "SRC-0001")
    assert len(records) == 7  # 5 rows on Clauses + 2 rows on Extra
    assert records[0]["raw_id"] == "RAW-000001"
    assert records[0]["sheet"] == "Clauses"
    assert records[0]["row_number"] == 2
    assert records[-1]["sheet"] == "Extra"
    assert records[0]["fields"]["Clause No"] == "1"


def test_csv_extraction(csv_fixture):
    result = xl.extract_spreadsheet(csv_fixture)
    assert result["file_type"] == "csv"
    records = xl.records_from_extraction(result, "SRC-0001")
    assert len(records) == 3
    # embedded comma must survive as one field
    assert records[2]["fields"]["Clause Text"] == "Third clause, with comma"


def test_empty_inputs_produce_no_records(tmp_path):
    empty_xlsx = make_empty_xlsx(str(tmp_path / "empty.xlsx"))
    records = xl.records_from_extraction(xl.extract_spreadsheet(empty_xlsx), "SRC-0001")
    assert records == []

    empty_csv = make_empty_csv(str(tmp_path / "empty.csv"))
    records = xl.records_from_extraction(xl.extract_spreadsheet(empty_csv), "SRC-0001")
    assert records == []


def test_html_is_rejected_not_extracted(tmp_path):
    fake = tmp_path / "replay.pdf"  # extension lies; content is HTML
    fake.write_bytes(b"<!DOCTYPE html><html><body>error page</body></html>")
    with pytest.raises(ExtractionError):
        xl.extract_spreadsheet(str(fake))


# ----------------------------------------------------------------------
# PDF
# ----------------------------------------------------------------------
def test_pdf_extraction_multiline_and_cross_page(pdf_fixture):
    result = pdf_mod.extract_pdf(pdf_fixture)
    assert result["file_type"] == "pdf"
    records = pdf_mod.records_from_pdf(result, "SRC-0001")
    assert records, "expected clause records from fixture PDF"
    texts = [r["fields"]["clause_text"] for r in records]

    # PDF-008: multiline clause stays connected
    joined = [t for t in texts if "first agreement clause" in t]
    assert joined and "second physical line" in joined[0]

    # PDF-007: repeated headers/footers/page numbers excluded
    for text in texts:
        assert "Australian Building and Construction Commission" != text
        assert not text.strip().lower().startswith("page ")

    # PDF-006: page numbers retained
    assert all(r["page"] for r in records)

    if HAS_REPORTLAB and len(records) >= 3:
        # PDF-009: clause spanning pages one and two is a single record
        cross = [
            r
            for r in records
            if "long clause beginning on page one" in r["fields"]["clause_text"]
        ]
        assert cross, "cross-page clause missing"
        assert "finishing on page two" in cross[0]["fields"]["clause_text"]
        assert cross[0]["pages"] == [1, 2]


def test_pdf_repeated_line_detection():
    pages = [
        ["HEADER", "1. Clause one", "FOOTER"],
        ["HEADER", "2. Clause two", "FOOTER"],
    ]
    repeated = pdf_mod.detect_repeated_lines(pages)
    assert "header" in repeated and "footer" in repeated
    body = pdf_mod.filter_body_lines(pages[0], repeated)
    assert body == ["1. Clause one"]


def test_pdf_rejects_non_pdf(tmp_path):
    fake = tmp_path / "fake.pdf"
    fake.write_bytes(b"PK\x03\x04 not a pdf at all")
    with pytest.raises(ExtractionError):
        pdf_mod.extract_pdf(str(fake))


def test_scanned_pdf_requires_ocr(tmp_path):
    """PDF-005: no embedded text -> OCR only; graceful error if unavailable."""
    scanned = make_scanned_pdf(str(tmp_path / "scanned.pdf"))
    try:
        import pytesseract  # noqa: F401

        has_pytesseract = True
    except ImportError:
        has_pytesseract = False
    if shutil.which("tesseract") is None or not has_pytesseract:
        with pytest.raises(ExtractionError) as excinfo:
            pdf_mod.extract_pdf(scanned)
        assert "OCR" in str(excinfo.value) or "tesseract" in str(excinfo.value).lower()
    else:
        # OCR available: the scanned page is used, never native text
        result = pdf_mod.extract_pdf(scanned)
        assert result["extraction_method"] == "ocr"


def test_normalisation_preserves_raw_and_assigns_ids(xlsx_fixture):
    result = xl.extract_spreadsheet(xlsx_fixture)
    raw_records = xl.records_from_extraction(result, "SRC-0001")
    snapshot = [dict(r, fields=dict(r["fields"])) for r in raw_records]
    clean = normalize_records(raw_records)
    assert clean[0]["record_id"] == "REC-000001"  # NR-005 internal id
    assert raw_records == snapshot  # NR-001 raw layer unchanged
    # NR-002: whitespace collapsed; NR-004: missing stays null
    whitespace_rec = [
        c
        for c in clean
        if c["fields"].get("Clause Text") == "Leading and trailing whitespace"
    ]
    assert whitespace_rec
    clause2 = [c for c in clean if c["fields"].get("Clause No") == "2"][0]
    assert clause2["fields"]["Notes"] is None
