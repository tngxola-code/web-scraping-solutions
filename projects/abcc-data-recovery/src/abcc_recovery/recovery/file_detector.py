"""Signature-based file type detection (FD-001 .. FD-005).

The actual bytes of a recovered file determine its type.  Filename
extensions, archive URLs and HTTP Content-Type headers are never trusted
on their own.
"""

from __future__ import annotations

import csv
import hashlib
import io

PDF_MAGIC = b"%PDF-"
ZIP_MAGIC = b"PK\x03\x04"
OLE2_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

TYPE_PDF = "pdf"
TYPE_XLSX = "xlsx"
TYPE_XLS = "xls"
TYPE_CSV = "csv"
TYPE_HTML = "html"
TYPE_UNKNOWN = "unknown"

_HTML_MARKERS = (b"<!doctype html", b"<html", b"<head", b"<body", b"<title")


def sha256_hex(data: bytes) -> str:
    """SHA-256 checksum of raw bytes (FD-005)."""
    return hashlib.sha256(data).hexdigest()


def looks_like_html(data: bytes) -> bool:
    """FD-004: detect HTML replay/error pages served instead of a document."""
    head = data[:4096].lstrip().lower()
    return any(marker in head for marker in _HTML_MARKERS)


def looks_like_csv(data: bytes) -> bool:
    """Heuristic CSV sniff: decodable text with a consistent delimiter."""
    try:
        text = data[:8192].decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = data[:8192].decode("latin-1")
        except UnicodeDecodeError:
            return False
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return False
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
    except csv.Error:
        dialect = None
    if dialect is not None:
        try:
            parsed = [next(csv.reader([ln], dialect)) for ln in lines[:5]]
        except csv.Error:
            parsed = []
        # require at least two lines that parse to >1 column to avoid
        # misclassifying plain text; a lone header line is still CSV
        if parsed and all(len(row) > 1 for row in parsed):
            return True
        if len(lines) == 1 and parsed and len(parsed[0]) > 1:
            return True
    # fallback when the sniffer fails (e.g. header-only file)
    if any(d in lines[0] for d in ",;\t"):
        if len(lines) == 1:
            return True
        hits = sum(1 for ln in lines[:10] if any(d in ln for d in ",;\t"))
        return hits >= max(2, len(lines[:10]) // 2)
    return False


def detect_file_type(data: bytes) -> str:
    """Detect the real type of *data* from its content (FD-001).

    Returns one of: pdf, xlsx, xls, csv, html, unknown.
    """
    if not data:
        return TYPE_UNKNOWN
    if data[:5] == PDF_MAGIC:
        return TYPE_PDF
    if data[:4] == ZIP_MAGIC:
        return TYPE_XLSX  # OOXML spreadsheets are ZIP containers
    if data[:8] == OLE2_MAGIC:
        return TYPE_XLS  # OLE2 compound document (legacy .xls)
    if looks_like_html(data):
        return TYPE_HTML
    if looks_like_csv(data):
        return TYPE_CSV
    return TYPE_UNKNOWN


def is_valid_document(data: bytes) -> bool:
    """True if the bytes are a processable document (not HTML/unknown)."""
    return detect_file_type(data) in {TYPE_PDF, TYPE_XLSX, TYPE_XLS, TYPE_CSV}


def sniff_csv_dialect(text: str) -> csv.Dialect:
    """Return the sniffed CSV dialect for decoded text (',' default)."""
    try:
        return csv.Sniffer().sniff(text[:8192], delimiters=",;\t|")
    except csv.Error:
        return csv.excel


def read_csv_rows(data: bytes) -> list[list[str]]:
    """Decode CSV bytes into rows using the sniffed dialect."""
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    dialect = sniff_csv_dialect(text)
    reader = csv.reader(io.StringIO(text), dialect)
    return [row for row in reader]
