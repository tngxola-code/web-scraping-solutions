import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from ..provenance import RunManifest


def write_manifest(run_id: str, summary: Dict[str, int], sha256: str, size: int,
                   source_url: str, status: str = "SUCCESS") -> RunManifest:
    """Build and return RunManifest object."""
    manifest = RunManifest(
        run_id=run_id,
        municipality="Québec",
        source_year=2026,
        source_index_url="https://donneesouvertes.affmunqc.net/role/indexRole2026.csv",
        source_xml_url=source_url,
        source_sha256=sha256,
        source_byte_size=size,
        retrieval_timestamp=datetime.utcnow(),
        completed_at=datetime.utcnow(),
        status=status,
        counts=summary,
    )
    return manifest