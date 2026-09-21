"""Source lineage and provenance (LIN-001 .. LIN-004)."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any, Optional


@dataclass
class SourceProvenance:
    """LIN-004 provenance for one recovered source file."""

    source_id: str  # LIN-001 stable internal source id
    original_url: str  # original ABCC URL
    recovered_url: Optional[str]  # archive/replay URL actually used
    archive_timestamp: Optional[str]
    filename: str
    file_type: Optional[str]
    file_size: Optional[int]
    sha256: Optional[str]
    retrieval_date: Optional[str]
    extraction_method: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def export_row(self) -> dict[str, Any]:
        """Row shape used by the 05_SOURCE_PROVENANCE worksheet."""
        return {
            "source_id": self.source_id,
            "original_url": self.original_url,
            "recovered_url": self.recovered_url,
            "archive_timestamp": self.archive_timestamp,
            "filename": self.filename,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "sha256": self.sha256,
            "retrieval_date": self.retrieval_date,
            "extraction_method": self.extraction_method,
        }


def build_provenance(
    source_id: str,
    selected: dict[str, Any],
    retrieval_date: Optional[str] = None,
    extraction_method: Optional[str] = None,
) -> SourceProvenance:
    """Create provenance from the recovery report's selected source."""
    return SourceProvenance(
        source_id=source_id,
        original_url=selected.get("original_url", ""),
        recovered_url=selected.get("archive_url"),
        archive_timestamp=selected.get("archive_timestamp"),
        filename=os.path.basename(selected.get("saved_path") or "unknown"),
        file_type=selected.get("detected_file_type"),
        file_size=selected.get("file_size"),
        sha256=selected.get("sha256"),
        retrieval_date=retrieval_date,
        extraction_method=extraction_method,
    )


def record_lineage(record: dict[str, Any]) -> dict[str, Any]:
    """LIN-002: the traceability fields of a single clean record."""
    return {
        "record_id": record.get("record_id"),
        "raw_id": record.get("raw_id"),
        "source_id": record.get("source_id"),
        "source_file": record.get("source_file"),
        "sheet": record.get("sheet"),
        "page": record.get("page"),
        "row_number": record.get("row_number"),
        "seq": record.get("seq"),
    }
