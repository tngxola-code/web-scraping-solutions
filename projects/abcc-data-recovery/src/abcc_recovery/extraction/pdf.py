"""PDF extraction (PDF-001 .. PDF-009, FD-002).

Strategy selection happens *after* inspecting the actual PDF (PDF-001):

1. native embedded text is preferred (PDF-002);
2. table-aware extraction is attempted for structured tables (PDF-003);
3. coordinate/positional extraction handles visually structured columns
   that are not recognised as tables (PDF-004);
4. OCR is a last resort for scanned PDFs without embedded text (PDF-005) and
   is optional — if pytesseract/tesseract is unavailable a clear
   ExtractionError is raised instead of fabricating data.

Repeated headers/footers/page numbers are excluded via repeated-line
detection (PDF-007); multiline clauses are joined (PDF-008); records
spanning page boundaries are kept together (PDF-009); the originating page
number(s) are retained on every record (PDF-006).
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Optional

from ..recovery import file_detector
from .excel import ExtractionError, _cell_value

log = logging.getLogger("abcc_recovery.extraction.pdf")

# A line that starts a new logical record (clause/example numbering).
RECORD_START_RE = re.compile(
    r"^\s*(\(?\d+[\.\):]\s+|example\s+\d+|clause\s+\d+|section\s+\d+)", re.IGNORECASE
)
# Bare page numbers / folios.
PAGE_NUMBER_RE = re.compile(r"^\s*(page\s+)?\d+(\s+of\s+\d+)?\s*$", re.IGNORECASE)


def _normalise_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip()).lower()


def detect_repeated_lines(pages_lines: list[list[str]], min_pages: int = 2) -> set[str]:
    """PDF-007: lines repeated across pages are headers/footers/navigation."""
    seen_on: dict[str, set[int]] = {}
    for idx, lines in enumerate(pages_lines):
        for line in {_normalise_line(ln) for ln in lines if ln.strip()}:
            seen_on.setdefault(line, set()).add(idx)
    return {ln for ln, pages in seen_on.items() if len(pages) >= min_pages}


def filter_body_lines(lines: list[str], repeated: set[str]) -> list[str]:
    """Drop repeated header/footer lines and bare page numbers (PDF-007)."""
    body = []
    for line in lines:
        if not line.strip():
            continue
        if _normalise_line(line) in repeated:
            continue
        if PAGE_NUMBER_RE.match(line):
            continue
        body.append(line.strip())
    return body


def join_lines_into_records(
    page_lines: list[tuple[int, str]],
) -> list[dict[str, Any]]:
    """Join physical lines into logical clause records (PDF-008/PDF-009).

    Lines are processed in reading order across page boundaries, so a clause
    continuing onto the next page stays in the same record (PDF-009).  A line
    matching RECORD_START_RE begins a new record; anything else is a
    continuation of the current record (PDF-008).
    """
    records: list[dict[str, Any]] = []
    current: Optional[dict[str, Any]] = None
    any_markers = any(RECORD_START_RE.match(ln) for _, ln in page_lines)
    for page_no, line in page_lines:
        starts_new = RECORD_START_RE.match(line) is not None if any_markers else True
        if starts_new or current is None:
            current = {"text": line.strip(), "pages": [page_no]}
            records.append(current)
        else:
            current["text"] = (current["text"] + " " + line.strip()).strip()
            if page_no not in current["pages"]:
                current["pages"].append(page_no)
    return records


def _positional_rows(page: Any) -> list[list[str]]:
    """PDF-004: cluster words into columns by x-position for one page."""
    words = page.extract_words()
    if not words:
        return []
    lines: dict[int, list[dict[str, Any]]] = {}
    for w in words:
        key = round(float(w["top"]) / 3.0)
        lines.setdefault(key, []).append(w)
    rows = []
    for key in sorted(lines):
        row_words = sorted(lines[key], key=lambda w: float(w["x0"]))
        # split into column cells at large horizontal gaps
        cells: list[str] = []
        last_x1: Optional[float] = None
        for w in row_words:
            if last_x1 is not None and float(w["x0"]) - last_x1 > 20 and cells:
                cells.append(w["text"])
            else:
                if cells:
                    cells[-1] = cells[-1] + " " + w["text"]
                else:
                    cells.append(w["text"])
            last_x1 = float(w["x1"])
        if len(cells) > 1:  # only visually multi-column rows qualify
            rows.append(cells)
    return rows


def _ocr_pdf(pdf: Any) -> list[str]:
    """PDF-005: OCR fallback — optional, fails gracefully if unavailable."""
    try:
        import pytesseract  # type: ignore
    except ImportError as exc:
        raise ExtractionError(
            "PDF has no embedded text and OCR is unavailable "
            "(optional dependency 'pytesseract' is not installed)"
        ) from exc
    texts = []
    try:
        for page in pdf.pages:
            image = page.to_image(resolution=200)
            texts.append(pytesseract.image_to_string(image.original))
    except pytesseract.TesseractNotFoundError as exc:  # type: ignore[attr-defined]
        raise ExtractionError(
            "PDF has no embedded text and the tesseract binary is not available; "
            "OCR cannot be performed in this environment"
        ) from exc
    return texts


def extract_pdf(path: str) -> dict[str, Any]:
    """Extract a recovered PDF into page-aware raw content (PDF-001)."""
    with open(path, "rb") as fh:
        head = fh.read(1024)
    if file_detector.detect_file_type(head) != file_detector.TYPE_PDF:
        raise ExtractionError(
            f"{os.path.basename(path)}: not a genuine PDF (FD-002/ERR-002)"
        )
    import pdfplumber

    try:
        pdf = pdfplumber.open(path)
    except Exception as exc:  # noqa: BLE001 - ERR-003
        raise ExtractionError(
            f"{os.path.basename(path)}: cannot open PDF: {exc}"
        ) from exc

    with pdf:
        page_count = len(pdf.pages)
        log.info(
            "[extraction] Extracting %d pages from %s",
            page_count,
            os.path.basename(path),
        )
        pages_lines: list[list[str]] = []
        tables: list[tuple[int, list[list[Any]]]] = []
        positional: list[tuple[int, list[list[str]]]] = []
        for idx, page in enumerate(pdf.pages, start=1):
            try:
                text = page.extract_text() or ""
                lines = [ln for ln in text.splitlines()]
                pages_lines.append(lines)
                try:
                    for table in page.extract_tables() or []:
                        if (
                            table
                            and len(table) >= 2
                            and any(len(r) >= 2 for r in table)
                        ):
                            tables.append((idx, table))
                except Exception:  # noqa: BLE001 - table detection is best-effort
                    pass
                if not lines:
                    rows = _positional_rows(page)
                    if rows:
                        positional.append((idx, rows))
            except Exception as exc:  # noqa: BLE001 - ERR-003 identifies the page
                raise ExtractionError(
                    f"{os.path.basename(path)} page {idx}: extraction failed: {exc}"
                ) from exc

        method = "pdfplumber-text"
        if (
            not any(any(ln.strip() for ln in lines) for lines in pages_lines)
            and not tables
        ):
            # PDF-005: no usable embedded text anywhere -> OCR last resort
            ocr_texts = _ocr_pdf(pdf)
            pages_lines = [[ln for ln in t.splitlines()] for t in ocr_texts]
            method = "ocr"

    repeated = detect_repeated_lines(pages_lines)
    body_pages = [filter_body_lines(lines, repeated) for lines in pages_lines]
    page_line_pairs = [
        (idx, ln) for idx, lines in enumerate(body_pages, start=1) for ln in lines
    ]

    if tables:
        method = "pdfplumber-tables"
    elif positional and not page_line_pairs:
        method = "pdfplumber-positional"

    return {
        "source_file": path,
        "file_type": "pdf",
        "extraction_method": method,
        "page_count": page_count,
        "page_line_pairs": page_line_pairs,
        "tables": tables,
        "positional_rows": positional,
    }


def records_from_pdf(
    extraction: dict[str, Any], source_id: str
) -> list[dict[str, Any]]:
    """Build raw records with page-level lineage (PDF-006, LIN-002)."""
    records: list[dict[str, Any]] = []
    seq = 0
    base = os.path.basename(extraction["source_file"])

    if extraction["tables"]:
        for page_no, table in extraction["tables"]:
            headings = [
                str(_cell_value(c) or f"column_{i + 1}").strip() or f"column_{i + 1}"
                for i, c in enumerate(table[0])
            ]
            for row in table[1:]:
                if not row or all(c in (None, "") for c in row):
                    continue
                seq += 1
                fields = {
                    headings[i]: _cell_value(row[i]) if i < len(row) else None
                    for i in range(len(headings))
                }
                records.append(
                    {
                        "raw_id": f"RAW-{seq:06d}",
                        "source_id": source_id,
                        "source_file": base,
                        "sheet": None,
                        "page": page_no,
                        "row_number": None,
                        "seq": seq,
                        "fields": fields,
                    }
                )
        return records

    if extraction["positional_rows"]:
        for page_no, rows in extraction["positional_rows"]:
            headings = rows[0]
            for row in rows[1:]:
                seq += 1
                fields = {
                    headings[i]: row[i] if i < len(row) else None
                    for i in range(len(headings))
                }
                records.append(
                    {
                        "raw_id": f"RAW-{seq:06d}",
                        "source_id": source_id,
                        "source_file": base,
                        "sheet": None,
                        "page": page_no,
                        "row_number": None,
                        "seq": seq,
                        "fields": fields,
                    }
                )
        return records

    for rec in join_lines_into_records(extraction["page_line_pairs"]):
        seq += 1
        records.append(
            {
                "raw_id": f"RAW-{seq:06d}",
                "source_id": source_id,
                "source_file": base,
                "sheet": None,
                "page": rec["pages"][0],
                "pages": rec["pages"],
                "row_number": None,
                "seq": seq,
                "fields": {"clause_text": rec["text"]},
            }
        )
    return records
