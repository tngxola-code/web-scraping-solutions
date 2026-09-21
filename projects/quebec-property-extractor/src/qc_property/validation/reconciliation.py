from typing import List, Dict, Any
from ..models import PropertyRecord


def reconcile(records: List[PropertyRecord], exceptions: List[Dict]) -> Dict[str, int]:
    """Compute reconciliation counts."""
    counts = {
        "parsed": len(records) + len(exceptions),
        "valid": 0,
        "warning": 0,
        "invalid": 0,
        "duplicate": 0,
        "exception": len(exceptions),
        "exported": 0,
    }
    for rec in records:
        status = rec.validation_status
        if status == "VALID":
            counts["valid"] += 1
            counts["exported"] += 1  # by default export valid only
        elif status == "WARNING":
            counts["warning"] += 1
            counts["exported"] += 1  # policy: export warnings too
        elif status == "INVALID":
            counts["invalid"] += 1
        elif status == "DUPLICATE":
            counts["duplicate"] += 1
    # reconciliation check: parsed = valid + warning + invalid + duplicate + exception
    total = counts["valid"] + counts["warning"] + counts["invalid"] + counts["duplicate"] + counts["exception"]
    if total != counts["parsed"]:
        raise ValueError(f"Reconciliation mismatch: parsed {counts['parsed']} != sum {total}")
    return counts