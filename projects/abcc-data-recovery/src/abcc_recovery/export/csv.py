"""CSV export (SPEC section 15).

The CSV is generated from the *clean* dataset only and never replaces the
Excel deliverable.
"""

from __future__ import annotations

import csv
import logging
from typing import Any

from .excel import ExportError, _field_columns

log = logging.getLogger("abcc_recovery.export.csv")

CSV_NAME = "ABCC_Agreement_Clauses.csv"

_META_COLUMNS = [
    "record_id",
    "raw_id",
    "source_id",
    "source_file",
    "sheet",
    "page",
    "row_number",
]

# qa_status comes last so the CSV column order matches the 03_CLEAN_DATA sheet.
_EXTRA_COLUMNS = ["qa_status"]


def write_csv(clean_records: list[dict[str, Any]], out_path: str) -> str:
    """Write ABCC_Agreement_Clauses.csv from clean records."""
    fields = _field_columns(clean_records)
    headers = _META_COLUMNS + fields + _EXTRA_COLUMNS
    try:
        with open(out_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(headers)
            for rec in clean_records:
                row = [rec.get(c) for c in _META_COLUMNS]
                row += [(rec.get("fields") or {}).get(f) for f in fields]
                row += [rec.get(c) for c in _EXTRA_COLUMNS]
                writer.writerow(row)
    except Exception as exc:  # noqa: BLE001 - ERR-005
        raise ExportError(f"CSV export failed: {exc}") from exc
    log.info("[export] CSV created: %s", out_path)
    return out_path
