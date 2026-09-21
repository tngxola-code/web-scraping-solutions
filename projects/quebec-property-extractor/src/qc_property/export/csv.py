import csv
import logging
from pathlib import Path
from typing import List
from ..models import PropertyRecord

logger = logging.getLogger(__name__)


def export_csv(records: List[PropertyRecord], output_path: Path):
    """Export records to UTF-8 CSV."""
    logger.info(f"Exporting CSV to {output_path}")
    if not records:
        logger.warning("No records to export")
        return

    # Use model fields as column headers, excluding raw_values
    field_names = [f for f in PropertyRecord.model_fields if f != "raw_values"]
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=field_names)
        writer.writeheader()
        for rec in records:
            row = {k: getattr(rec, k) for k in field_names}
            # Convert non-string types to string for CSV
            for k, v in row.items():
                if v is not None and not isinstance(v, (str, int, float)):
                    row[k] = str(v)
            writer.writerow(row)