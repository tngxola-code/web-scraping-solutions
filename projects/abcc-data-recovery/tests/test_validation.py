"""Validation tests (SPEC section 22): duplicates, missing values,
suspicious records, status assignment and source-verification rules."""

from __future__ import annotations

from abcc_recovery.processing.normalize import normalize_records
from abcc_recovery.qa import reconcile as reconcile_mod
from abcc_recovery.qa import validate as v


def _raw(fields, seq, sheet="S", row=None):
    return {
        "raw_id": f"RAW-{seq:06d}",
        "source_id": "SRC-0001",
        "source_file": "fixture.xlsx",
        "sheet": sheet,
        "page": None,
        "row_number": row if row is not None else seq + 1,
        "seq": seq,
        "fields": fields,
    }


def _clean(raw_records):
    return normalize_records(raw_records)


CLAUSE = "The parties must comply with the terms of this agreement at all times."


# ----------------------------------------------------------------------
# QA-002 duplicates
# ----------------------------------------------------------------------
def test_exact_duplicate_detection():
    raw = [
        _raw({"Clause": CLAUSE, "No": "1"}, 1),
        _raw({"Clause": CLAUSE, "No": "1"}, 2),
        _raw({"Clause": "A different clause entirely.", "No": "2"}, 3),
    ]
    clean = _clean(raw)
    findings = v.validate_records(clean, raw)
    assert findings["exact_duplicate_count"] == 1
    assert findings["exact_duplicate_groups"] == [["REC-000001", "REC-000002"]]
    dup = clean[1]
    assert dup["qa_status"] == v.MANUAL_REVIEW_REQUIRED
    assert any("duplicate" in note for note in dup["review_notes"])  # QA-007


def test_near_duplicate_detection():
    raw = [
        _raw({"Clause": CLAUSE}, 1),
        _raw({"Clause": CLAUSE.replace("this agreement", "the agreement")}, 2),
        _raw({"Clause": "Completely unrelated content about something else."}, 3),
    ]
    clean = _clean(raw)
    findings = v.validate_records(clean, raw)
    assert findings["near_duplicates"]
    ids = {findings["near_duplicates"][0][0], findings["near_duplicates"][0][1]}
    assert ids == {"REC-000001", "REC-000002"}


# ----------------------------------------------------------------------
# QA-003 missing values
# ----------------------------------------------------------------------
def test_missing_value_stats_and_flags():
    raw = [
        _raw({"Clause": CLAUSE, "No": "1"}, 1),
        _raw({"Clause": CLAUSE, "No": None}, 2),
        _raw({"Clause": CLAUSE, "No": "3"}, 3),
    ]
    clean = _clean(raw)
    findings = v.validate_records(clean, raw)
    assert findings["missing_value_stats"]["No"] == 1
    flagged = [r for r in clean if r["qa_status"] == v.MANUAL_REVIEW_REQUIRED]
    assert any(r["fields"]["No"] is None for r in flagged)


# ----------------------------------------------------------------------
# QA-004 suspicious extraction
# ----------------------------------------------------------------------
def test_suspicious_records_flagged():
    raw = [
        _raw({"Clause": "ab"}, 1),  # unusually short
        _raw({"Clause": "This text ends abruptly-"}, 2),  # truncated-looking
        _raw({"Clause": CLAUSE}, 3),
    ]
    clean = _clean(raw)
    findings = v.validate_records(clean, raw)
    assert clean[0]["qa_status"] == v.MANUAL_REVIEW_REQUIRED
    assert any("short" in n for n in clean[0]["review_notes"])
    assert clean[1]["qa_status"] == v.MANUAL_REVIEW_REQUIRED
    assert any("truncated" in n for n in clean[1]["review_notes"])
    assert clean[2]["qa_status"] == v.SOURCE_VERIFIED


# ----------------------------------------------------------------------
# QA-005 / QA-006 status assignment & source verification
# ----------------------------------------------------------------------
def test_status_assignment_levels():
    raw = [
        _raw({"Clause": CLAUSE}, 1),  # verified against source
        _raw({"Clause": None}, 2),  # empty -> EXTRACTED
    ]
    clean = _clean(raw)
    v.validate_records(clean, raw)
    assert clean[0]["qa_status"] == v.SOURCE_VERIFIED
    assert clean[1]["qa_status"] == v.EXTRACTED


def test_source_verified_requires_evidence_not_populated_fields():
    """QA-005/006: populated fields alone never grant SOURCE_VERIFIED."""
    raw = [_raw({"Clause": CLAUSE}, 1)]
    clean = _clean(raw)
    # no source verification performed -> only STRUCTURALLY_VALID
    v.validate_records(clean, raw, verify_source=False)
    assert clean[0]["qa_status"] == v.STRUCTURALLY_VALID

    # clean value deviates from the recovered source -> verification fails
    clean2 = _clean(raw)
    clean2[0]["fields"]["Clause"] = "A materially different clause text."
    v.validate_records(clean2, raw)
    assert clean2[0]["qa_status"] == v.MANUAL_REVIEW_REQUIRED
    assert any("verification failed" in n for n in clean2[0]["review_notes"])


def test_verify_against_source_directly():
    raw = [_raw({"Clause": CLAUSE}, 1)]
    clean = _clean(raw)
    ok, _reason = v.verify_against_source(clean[0], raw[0])
    assert ok
    ok, reason = v.verify_against_source(clean[0], None)
    assert not ok and "raw" in reason


def test_empty_dataset_structural_finding():
    findings = v.validate_records([], [])
    assert findings["total_records"] == 0


# ----------------------------------------------------------------------
# REC-001..004 reconciliation
# ----------------------------------------------------------------------
def test_reconciliation_summary():
    raw = [_raw({"Clause": f"{CLAUSE} (clause {i})"}, i) for i in range(1, 4)]
    clean = _clean(raw)
    findings = v.validate_records(clean, raw)
    result = reconcile_mod.reconcile(
        raw,
        clean,
        source_record_count=3,
        exact_duplicate_groups=findings["exact_duplicate_groups"],
    )
    assert result["reconciled"] is True
    assert result["source_records"] == 3
    assert result["extracted_records"] == 3
    assert result["source_verified"] == 3
    assert any(
        line.startswith("Extracted records: 3") for line in result["summary_lines"]
    )


def test_reconciliation_detects_missing_source_records():
    raw = [_raw({"Clause": CLAUSE}, 1)]
    clean = _clean(raw)
    result = reconcile_mod.reconcile(raw, clean, source_record_count=3)
    assert result["missing_from_extraction"] == 2
    assert result["reconciled"] is False


def test_extraction_vs_source_duplicates():
    # same source position extracted twice -> extraction duplicate (REC-003)
    first = _raw({"Clause": CLAUSE}, 1)
    raw = [first, dict(first)]
    clean = _clean(raw)
    findings = v.validate_records(clean, raw)
    result = reconcile_mod.reconcile(
        raw,
        clean,
        source_record_count=1,
        exact_duplicate_groups=findings["exact_duplicate_groups"],
    )
    assert result["extraction_duplicates"] == 1
    assert result["reconciled"] is False
