"""Non-destructive normalisation (NR-001 .. NR-005).

Produces a SEPARATE clean dataset; raw records are never modified
(NR-001).  Cleaning is limited to whitespace/encoding/line-break artefacts
and never alters legal meaning (NR-002).  Missing values stay null —
nothing is guessed (NR-004).  Each clean record receives a stable internal
identifier (REC-000001, ...) which is never presented as a source/ABCC
identifier (NR-005).
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any, Optional

log = logging.getLogger("abcc_recovery.processing.normalize")

_WS_RUN_RE = re.compile(r"\s+")

# Common mojibake/artefact replacements that unambiguously restore the
# intended character (encoding issues only, NR-002).
_ENCODING_FIXES = {
    "\u00a0": " ",  # non-breaking space
    "\ufeff": "",  # BOM
    "\u200b": "",  # zero-width space
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2013": "-",
    "\u2014": "-",
    "\u2026": "...",
}


def clean_text(value: str) -> str:
    """Whitespace/encoding/line-break cleanup without altering meaning."""
    text = unicodedata.normalize("NFKC", value)
    for bad, good in _ENCODING_FIXES.items():
        text = text.replace(bad, good)
    # obvious PDF line-break artefacts: collapse internal newlines/runs
    text = _WS_RUN_RE.sub(" ", text)
    return text.strip()


def clean_column_name(name: str) -> str:
    """Column-name consistency (NR-002): stripped, single-spaced."""
    return _WS_RUN_RE.sub(" ", unicodedata.normalize("NFKC", str(name))).strip()


def normalize_value(value: Any) -> Any:
    """Clean a single value; None/empty stay None (NR-004)."""
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = clean_text(value)
        return cleaned if cleaned != "" else None
    return value


def normalize_records(raw_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build the clean dataset from raw records (NR-001).

    Raw records are left untouched; lineage fields are copied so every clean
    record remains traceable to its raw record and source position
    (LIN-002).
    """
    clean: list[dict[str, Any]] = []
    for idx, raw in enumerate(raw_records, start=1):
        fields = {
            clean_column_name(k): normalize_value(v)
            for k, v in (raw.get("fields") or {}).items()
        }
        clean.append(
            {
                "record_id": f"REC-{idx:06d}",  # NR-005 internal id, NOT a source id
                "raw_id": raw.get("raw_id"),
                "source_id": raw.get("source_id"),
                "source_file": raw.get("source_file"),
                "sheet": raw.get("sheet"),
                "page": raw.get("page"),
                "pages": raw.get("pages"),
                "row_number": raw.get("row_number"),
                "seq": raw.get("seq"),
                "fields": fields,
            }
        )
    log.info("[normalise] Produced %d clean records", len(clean))
    return clean
