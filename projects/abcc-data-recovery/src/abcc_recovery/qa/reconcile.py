"""Record-count reconciliation (REC-001 .. REC-004)."""

from __future__ import annotations

import logging
from typing import Any, Optional

log = logging.getLogger("abcc_recovery.qa.reconcile")


def reconcile(
    raw_records: list[dict[str, Any]],
    clean_records: list[dict[str, Any]],
    source_record_count: Optional[int] = None,
    exact_duplicate_groups: Optional[list[list[str]]] = None,
) -> dict[str, Any]:
    """Reconcile extracted/clean counts against the source (REC-001).

    ``source_record_count`` is only meaningful when the source exposes a
    determinable count (e.g. spreadsheet data rows).  Duplicates created by
    extraction (same source position extracted twice) are distinguished from
    duplicates genuinely present in the source (REC-003).
    """
    extracted = len(raw_records)
    clean = len(clean_records)

    # REC-003: extraction duplicates re-use the same source position.
    positions = [
        (
            r.get("source_id"),
            r.get("sheet"),
            r.get("page"),
            r.get("row_number"),
            r.get("seq"),
        )
        for r in raw_records
    ]
    seen_positions: set[tuple] = set()
    extraction_duplicates = 0
    for pos in positions:
        if pos in seen_positions:
            extraction_duplicates += 1
        else:
            seen_positions.add(pos)

    source_duplicate_count = sum(len(g) - 1 for g in (exact_duplicate_groups or []))
    source_duplicate_count = max(0, source_duplicate_count - extraction_duplicates)

    missing = None
    if source_record_count is not None:
        # REC-002: records present in the source but absent from extraction
        missing = max(0, source_record_count - extracted)

    status_counts: dict[str, int] = {}
    for rec in clean_records:
        status = rec.get("qa_status", "UNKNOWN")
        status_counts[status] = status_counts.get(status, 0) + 1

    result = {
        "source_records": source_record_count,
        "extracted_records": extracted,
        "clean_records": clean,
        "extraction_duplicates": extraction_duplicates,
        "source_duplicates": source_duplicate_count,
        "missing_from_extraction": missing,
        "source_verified": status_counts.get("SOURCE_VERIFIED", 0),
        "manual_review_required": status_counts.get("MANUAL_REVIEW_REQUIRED", 0),
        "reconciled": (
            source_record_count is None
            or (extracted == source_record_count and extraction_duplicates == 0)
        ),
    }
    # REC-004 human-readable summary
    lines = []
    if source_record_count is not None:
        lines.append(f"Source records: {source_record_count}")
    lines.append(f"Extracted records: {extracted}")
    lines.append(f"Clean records: {clean}")
    lines.append(f"Source verified: {result['source_verified']}")
    lines.append(f"Manual review required: {result['manual_review_required']}")
    result["summary_lines"] = lines
    log.info("[qa] Running reconciliation: %s", "; ".join(lines))
    return result
