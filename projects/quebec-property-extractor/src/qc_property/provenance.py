import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any
from pydantic import BaseModel, Field
import json


class RunManifest(BaseModel):
    run_id: str
    municipality: str
    source_year: int
    source_index_url: str
    source_xml_url: Optional[str] = None
    source_sha256: Optional[str] = None
    source_byte_size: Optional[int] = None
    retrieval_timestamp: Optional[datetime] = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    status: str  # SUCCESS, FAILED, REVIEW_REQUIRED
    counts: Dict[str, int] = Field(default_factory=dict)
    parser_version: str = "2026"
    application_version: str = "0.1.0"
    errors: list[str] = Field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), indent=2, default=str)

    @classmethod
    def from_json(cls, path: Path) -> "RunManifest":
        with open(path) as f:
            data = json.load(f)
        return cls(**data)


def compute_sha256(file_path: Path, chunk_size: int = 8192) -> str:
    """Compute SHA-256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            sha256.update(chunk)
    return sha256.hexdigest()