"""Validation and QA (QA-001 .. QA-007).

Status terminology (QA-005):
* ``EXTRACTED``               - extracted, but did not pass structural checks
* ``STRUCTURALLY_VALID``      - structurally sound, not verified against source
* ``SOURCE_VERIFIED``         - structurally sound AND evidence shows the
                                cleaned values agree with the recovered
                                source (QA-006) — never granted merely
                                because fields are populated
* ``MANUAL_REVIEW_REQUIRED``  - flagged with a human-readable reason (QA-007)
"""

from __future__ import annotations

import difflib
import logging
from typing import Any, Optional

log = logging.getLogger("abcc_recovery.qa.validate")

EXTRACTED = "EXTRACTED"
STRUCTURALLY_VALID = "STRUCTURALLY_VALID"
SOURCE_VERIFIED = "SOURCE_VERIFIED"
MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"

NEAR_DUPLICATE_RATIO = 0.95
SHORT_TEXT_THRESHOLD = 4


def _field_text(record: dict[str, Any]) -> str:
    return " | ".join(
        str(v) for v in (record.get("fields") or {}).values() if v is not None
    )


def _fields_signature(record: dict[str, Any]) -> tuple:
    fields = record.get("fields") or {}
    return tuple(sorted((k, str(v)) for k, v in fields.items()))


# ----------------------------------------------------------------------
# QA-001 structural validation
# ----------------------------------------------------------------------
def structural_check(record: dict[str, Any]) -> list[str]:
    problems = []
    fields = record.get("fields")
    if not isinstance(fields, dict) or not fields:
        problems.append("record has no fields")
    elif all(v is None or v == "" for v in fields.values()):
        problems.append("record is empty (all fields null)")
    return problems


# ----------------------------------------------------------------------
# QA-002 duplicate detection
# ----------------------------------------------------------------------
def find_exact_duplicates(records: list[dict[str, Any]]) -> list[list[str]]:
    """Groups of record_ids whose field values are identical."""
    seen: dict[tuple, list[str]] = {}
    for rec in records:
        seen.setdefault(_fields_signature(rec), []).append(rec["record_id"])
    return [ids for ids in seen.values() if len(ids) > 1]


def find_near_duplicates(
    records: list[dict[str, Any]], ratio: float = NEAR_DUPLICATE_RATIO
) -> list[tuple[str, str, float]]:
    """Possible near-duplicates via difflib similarity on full record text."""
    texts = [(rec["record_id"], _field_text(rec)) for rec in records]
    near: list[tuple[str, str, float]] = []
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            id_a, text_a = texts[i]
            id_b, text_b = texts[j]
            if not text_a or not text_b:
                continue
            # Cheap exact upper-bound prefilters (identical result set):
            # ratio <= 2*min(len)/sum(len), and quick_ratio() is itself an
            # upper bound on ratio(), so pairs failing either can never
            # reach the threshold.  This keeps O(n^2) full-ratio scoring
            # feasible on real datasets of ~1600+ records.
            la, lb = len(text_a), len(text_b)
            if 2.0 * min(la, lb) / (la + lb) < ratio:
                continue
            matcher = difflib.SequenceMatcher(None, text_a, text_b)
            if matcher.quick_ratio() < ratio:
                continue
            score = matcher.ratio()
            if score >= ratio:
                near.append((id_a, id_b, round(score, 4)))
    return near


# ----------------------------------------------------------------------
# QA-003 missing values
# ----------------------------------------------------------------------
def missing_value_stats(records: list[dict[str, Any]]) -> dict[str, int]:
    stats: dict[str, int] = {}
    for rec in records:
        for key, value in (rec.get("fields") or {}).items():
            if value is None or value == "":
                stats[key] = stats.get(key, 0) + 1
            else:
                stats.setdefault(key, stats.get(key, 0))
    return stats


def significant_fields(records: list[dict[str, Any]]) -> set[str]:
    """Fields populated in at least half of the records (QA-003)."""
    if not records:
        return set()
    counts: dict[str, int] = {}
    for rec in records:
        for key, value in (rec.get("fields") or {}).items():
            if value is not None and value != "":
                counts[key] = counts.get(key, 0) + 1
    threshold = max(1, len(records) // 2)
    return {k for k, c in counts.items() if c >= threshold}


# ----------------------------------------------------------------------
# QA-004 suspicious extraction
# ----------------------------------------------------------------------
def suspicious_flags(record: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    for key, value in (record.get("fields") or {}).items():
        if not isinstance(value, str) or not value:
            continue
        text = value.strip()
        if len(text) < SHORT_TEXT_THRESHOLD and not text.isdigit():
            flags.append(f"unusually short text in '{key}': {text!r}")
        if text.endswith(("-", ",", ";", "(")):
            flags.append(f"possibly truncated text in '{key}'")
        lowered = text.lower()
        if lowered.startswith(("page ", "www.", "http")) and len(text) < 40:
            flags.append(f"possible page header/footer content in '{key}'")
    return flags


# ----------------------------------------------------------------------
# QA-006 source verification evidence
# ----------------------------------------------------------------------
def verify_against_source(
    clean_record: dict[str, Any], raw_record: Optional[dict[str, Any]]
) -> tuple[bool, str]:
    """Evidence that cleaned values agree with the recovered source.

    Verification = every cleaned field value is exactly the value the
    documented normalisation produces from the raw record; any deviation
    means the clean dataset no longer matches the source.
    """
    if raw_record is None:
        return False, "no raw record available for comparison"
    from ..processing.normalize import clean_column_name, normalize_value

    raw_fields = raw_record.get("fields") or {}
    clean_fields = clean_record.get("fields") or {}
    for key, value in clean_fields.items():
        raw_key = key if key in raw_fields else None
        if raw_key is None:
            for candidate in raw_fields:
                if clean_column_name(candidate) == key:
                    raw_key = candidate
                    break
        if raw_key is None:
            return False, f"field '{key}' not present in raw record"
        if normalize_value(raw_fields[raw_key]) != value:
            return False, f"clean value for '{key}' differs from raw source value"
    return True, "cleaned values match raw source after documented cleaning"


# ----------------------------------------------------------------------
# Status assignment (QA-005 / QA-007)
# ----------------------------------------------------------------------
def assign_status(
    structural_problems: list[str],
    flags: list[str],
    verified: bool,
    verification_attempted: bool = True,
) -> str:
    if structural_problems:
        return EXTRACTED
    if flags:
        return MANUAL_REVIEW_REQUIRED
    if verified:
        return SOURCE_VERIFIED
    if verification_attempted:
        # verification evidence was sought but did not confirm agreement
        return MANUAL_REVIEW_REQUIRED
    return STRUCTURALLY_VALID


def validate_records(
    clean_records: list[dict[str, Any]],
    raw_records: Optional[list[dict[str, Any]]] = None,
    verify_source: bool = True,
) -> dict[str, Any]:
    """Run all QA checks; annotates records with qa_status/review_notes."""
    raw_by_id = {r.get("raw_id"): r for r in (raw_records or [])}
    sig_fields = significant_fields(clean_records)

    exact_dups = find_exact_duplicates(clean_records)
    dup_members = {rid for group in exact_dups for rid in group[1:]}
    near_dups = find_near_duplicates(clean_records)

    for rec in clean_records:
        problems = structural_check(rec)
        flags = suspicious_flags(rec)
        notes: list[str] = []
        for problem in problems:
            notes.append(f"structural: {problem}")
        if rec["record_id"] in dup_members:
            flags.append("exact duplicate of an earlier record")
        for key in sig_fields:
            value = (rec.get("fields") or {}).get(key)
            if (value is None or value == "") and not problems:
                flags.append(f"missing value in significant field '{key}'")
        verified = False
        verification_attempted = False
        if not problems:
            if verify_source:
                verification_attempted = True
                verified, evidence = verify_against_source(
                    rec, raw_by_id.get(rec.get("raw_id"))
                )
                if not verified:
                    notes.append(f"source verification failed: {evidence}")
        status = assign_status(problems, flags, verified, verification_attempted)
        rec["qa_status"] = status
        rec["review_notes"] = notes + [f"flag: {f}" for f in flags]

    status_counts: dict[str, int] = {}
    for rec in clean_records:
        status_counts[rec["qa_status"]] = status_counts.get(rec["qa_status"], 0) + 1

    findings = {
        "total_records": len(clean_records),
        "structural_problems": sum(
            1 for r in clean_records if r["qa_status"] == EXTRACTED
        ),
        "exact_duplicate_groups": exact_dups,
        "exact_duplicate_count": sum(len(g) - 1 for g in exact_dups),
        "near_duplicates": near_dups,
        "missing_value_stats": missing_value_stats(clean_records),
        "significant_fields": sorted(sig_fields),
        "status_counts": status_counts,
        "manual_review_records": [
            {"record_id": r["record_id"], "review_notes": r["review_notes"]}
            for r in clean_records
            if r["qa_status"] == MANUAL_REVIEW_REQUIRED
        ],
    }
    log.info(
        "[qa] Validation complete: %d records, %d flagged for review",
        len(clean_records),
        len(findings["manual_review_records"]),
    )
    return findings
