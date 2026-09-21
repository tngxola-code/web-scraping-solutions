
import logging
from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from ..models import PropertyRecord

logger = logging.getLogger(__name__)


class Mapper:
    def __init__(self, mapping_config: Dict[str, Any]):
        self.config = mapping_config
        self.field_map = mapping_config.get("fields", [])
        self.version = mapping_config.get("version", "unknown")

    @classmethod
    def load_mapping(cls, path: Path) -> "Mapper":
        """Load mapping YAML from file."""
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(data)

    def to_canonical(self, raw: Dict[str, Any], run_id: str, source_file: str) -> PropertyRecord:
        """Transform raw dict (from XML) to PropertyRecord using mapping."""
        # Start with raw values (for provenance)
        data = {"raw_values": raw.copy()}

        for field_def in self.field_map:
            src_path = field_def.get("source_path")
            canonical = field_def.get("canonical_name")
            transform = field_def.get("transform", "string")
            required = field_def.get("required", False)
            nullable = field_def.get("nullable", True)

            value = raw.get(src_path)  # simple lookup; more complex XPath would be implemented separately
            if value is None and required:
                logger.warning(f"Required field {canonical} missing")
                # We'll record validation note later

            # Apply transformation
            if value is not None:
                try:
                    if transform == "decimal":
                        value = self._to_decimal(value)
                    elif transform == "string":
                        value = self._to_string(value)
                    elif transform == "integer":
                        value = self._to_integer(value)
                    # Add more transforms as needed
                except Exception as e:
                    logger.warning(f"Transform error for {canonical}: {e}")
                    value = None
                    # Record exception

            data[canonical] = value

        # Fill required fields with defaults
        data["run_id"] = run_id
        data["source_file"] = source_file
        data["source_year"] = 2026  # from config

        # Create record
        record = PropertyRecord(**data)
        # Add validation status if missing required fields, etc.
        return record

    @staticmethod
    def _to_decimal(v):
        if isinstance(v, (int, float)):
            return v
        if isinstance(v, str):
            # Remove thousands separators and other formatting
            v = v.replace(",", "").replace(" ", "").strip()
            if not v:
                return None
            return float(v)  # or Decimal
        return v

    @staticmethod
    def _to_string(v):
        if v is None:
            return None
        return str(v).strip()

    @staticmethod
    def _to_integer(v):
        if isinstance(v, int):
            return v
        if isinstance(v, str):
            v = v.replace(",", "").strip()
            if not v:
                return None
            return int(v)
        return v