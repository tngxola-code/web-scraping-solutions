"""Driver for the real recovery run (2026-09-03).

Network recovery was performed out-of-band (this sandbox has no network
access to archive.org); the recovered source file, its SHA-256 and the full
archive evidence trail were supplied and verified before this script ran
(see reports/recovery_candidates.json).  This driver therefore replaces
only the *download* step of ``stage_recover`` with the verified evidence,
and runs every other stage through the pipeline's own modules:

  extraction.excel.extract_spreadsheet / records_from_extraction
  processing.normalize.normalize_records
  qa.validate.validate_records
  qa.reconcile.reconcile
  export.excel.create_workbook / export.csv.write_csv
  processing.lineage.build_provenance

The 'ABCC Clauses' sheet is the authoritative extraction source for the
clean dataset; 'FuzzyLookup_AddIn_Undo_Sheet' (an Excel Fuzzy Lookup
add-in artifact) and 'Change History' are preserved verbatim in the raw
layer only.

Usage:
    python scripts/run_real_pipeline.py
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import unicodedata
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from abcc_recovery.cli import (PipelineContext, _json_dump,  # noqa: E402
                               _json_load, _log)
from abcc_recovery.export import csv as csv_export  # noqa: E402
from abcc_recovery.export import excel as excel_export  # noqa: E402
from abcc_recovery.extraction import excel as excel_extraction  # noqa: E402
from abcc_recovery.processing import lineage, normalize  # noqa: E402
from abcc_recovery.qa import reconcile as reconcile_mod  # noqa: E402
from abcc_recovery.qa import validate as validate_mod  # noqa: E402
from abcc_recovery.recovery import file_detector  # noqa: E402

# ------------------------------------------------------------------
# Verified recovery evidence (see reports/recovery_candidates.json).
# The download itself was performed out-of-band via browser tooling
# because this sandbox has no network route to archive.org.
# ------------------------------------------------------------------
SOURCE_FILENAME = "abcc_agreement_clauses_spreadsheet_excel_version.xlsx"
EXPECTED_SHA256 = "1129fc015224bcc95504a99012d5d848d409917ef0163eb44d711711fc61971a"
EXPECTED_SIZE = 589212
ORIGINAL_URL = (
    "https://www.abcc.gov.au/sites/default/files/"
    "abcc_agreement_clauses_spreadsheet_excel_version.xlsx"
)
ARCHIVE_URL = (
    "http://web.archive.org/web/20220312011833/"
    "https://www.abcc.gov.au/sites/default/files/"
    "abcc_agreement_clauses_spreadsheet_excel_version.xlsx"
)
ARCHIVE_TIMESTAMP = "20220312011833"
WAYBACK_DIGEST = "QSVP27B5JZCKQIDWADPJRXQFTGU2RQAK"
RETRIEVAL_DATE = "2026-09-03"
RESOURCE_PAGE_SNAPSHOT = (
    "http://web.archive.org/web/20220320160705/"
    "https://www.abcc.gov.au/resources/agreement-clauses"
)
AUTHORITATIVE_SHEET = "ABCC Clauses"
ARTIFACT_SHEET = "FuzzyLookup_AddIn_Undo_Sheet"
SOURCE_ID = "SRC-0001"  # LIN-001


def build_recovery_report(ctx: PipelineContext, source_path: str) -> dict[str, Any]:
    """Compose reports/recovery_report.json (SPEC s16) from real evidence."""
    evidence = _json_load(os.path.join(ctx.dir_reports, "recovery_candidates.json"))
    best = evidence["best_candidate"]
    candidates = evidence["candidates"]

    archive_queries = [
        {"query": q["query"], "result": q["result"]} for q in evidence["queries"]
    ]
    # Snapshots discovered per the CDX evidence (real capture counts).
    snapshots_discovered = (
        6 + 36 + 3 + 5
    )  # pdf exact + page + xlsx + excel_version.xlsx

    selected = {
        "original_url": ORIGINAL_URL,
        "archive_url": ARCHIVE_URL,
        "archive_timestamp": ARCHIVE_TIMESTAMP,
        "detected_file_type": "xlsx",
        "sha256": EXPECTED_SHA256,
        "file_size": EXPECTED_SIZE,
        "saved_path": source_path,
        "discovered_via": "resource_page_link",
    }
    rejected = []
    for cand in candidates:
        if cand["archive_url"] == best["archive_url"]:
            continue
        if cand["digest"] == "3GVYWRGN5Q62YFSZZ36XO5BXNFF5PQTR":
            reason = (
                "rejected: older content generation (2019/2020 digest "
                "3GVYWRGN5Q62YFSZZ36XO5BXNFF5PQTR); superseded by the "
                "20220312 content update"
            )
        else:
            reason = (
                "rejected: PDF fallback not needed — the original XLSX "
                "spreadsheet was recovered (SR-002 priority order)"
            )
        rejected.append(
            {
                "original_url": cand["original_url"],
                "archive_url": cand["archive_url"],
                "archive_timestamp": cand["timestamp"],
                "http_status": cand["statuscode"],
                "detected_file_type": cand["format"],
                "wayback_digest": cand["digest"],
                "error": reason,
            }
        )

    report = {
        "status": "RECOVERED",
        "retrieval_date": RETRIEVAL_DATE,
        "urls_searched": sorted(
            {
                "https://www.abcc.gov.au/sites/default/files/abcc_agreement_clauses_spreadsheet.pdf",
                "https://www.abcc.gov.au/resources/agreement-clauses",
                "https://www.abcc.gov.au/sites/default/files/abcc_agreement_clauses_spreadsheet.xlsx",
                "https://www.abcc.gov.au/sites/default/files/abcc_agreement_clauses_spreadsheet_excel_version.xlsx",
                "https://www.abcc.gov.au/sites/default/files/abcc_agreement_clauses_spreadsheet.csv",
                "https://www.abcc.gov.au/sites/default/files/abcc_agreement_clauses_spreadsheet.xls",
            }
        ),
        "archive_queries": archive_queries,
        "snapshots_discovered": snapshots_discovered,
        "files_considered": len(candidates),
        "files_accepted": [
            {
                **{
                    k: selected[k]
                    for k in (
                        "original_url",
                        "archive_url",
                        "archive_timestamp",
                        "detected_file_type",
                        "sha256",
                        "file_size",
                        "saved_path",
                        "discovered_via",
                    )
                },
                "wayback_digest": WAYBACK_DIGEST,
                "http_status": "200",
                "mimetype": (
                    "application/vnd.openxmlformats-officedocument."
                    "spreadsheetml.sheet"
                ),
            }
        ],
        "files_rejected": rejected,
        "checksums": {ORIGINAL_URL: EXPECTED_SHA256},
        "recovery_errors": [],
        "selected_source": selected,
        "selection_reason": best["reason"],
        "verification": {
            "sha256_verified_against_downloaded_file": True,
            "magic_bytes": "PK\\x03\\x04 (genuine XLSX/ZIP container)",
            "linked_from_archived_resource_page": RESOURCE_PAGE_SNAPSHOT,
            "linked_as": "Download all Agreement Clauses (Excel)",
            "download_method": (
                "out-of-band browser download from the Wayback replay URL; "
                "sandbox shell has no network route to archive.org"
            ),
        },
        "attempts": [
            {
                "url": ARCHIVE_URL,
                "archive_timestamp": ARCHIVE_TIMESTAMP,
                "http_status": 200,
                "detected_file_type": "xlsx",
                "file_size": EXPECTED_SIZE,
                "sha256": EXPECTED_SHA256,
                "outcome": "DOWNLOADED",
                "saved_path": source_path,
            }
        ],
    }
    _json_dump(os.path.join(ctx.dir_reports, "recovery_report.json"), report)
    return report


def main() -> int:
    ctx = PipelineContext(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    source_path = os.path.join(ctx.dir_source, SOURCE_FILENAME)

    # --- integrity gate (FD-001/FD-005) -------------------------------
    _log("[file] Verifying recovered source integrity")
    with open(source_path, "rb") as fh:
        payload = fh.read()
    sha = hashlib.sha256(payload).hexdigest()
    if sha != EXPECTED_SHA256 or len(payload) != EXPECTED_SIZE:
        _log(
            f"[file] FAILED: checksum/size mismatch (sha256={sha}, size={len(payload)})"
        )
        return 1
    detected = file_detector.detect_file_type(payload[:8192])
    if detected != file_detector.TYPE_XLSX:
        _log(f"[file] FAILED: unexpected content type {detected}")
        return 1
    _log(f"[file] Detected {detected.upper()}; SHA-256 verified ({sha[:16]}...)")

    # --- recovery report (from verified evidence) ----------------------
    _log("[recovery] Writing recovery report from verified evidence")
    recovery_report = build_recovery_report(ctx, source_path)

    # --- extraction (EXL-001..004, RAW-001) ----------------------------
    _log("[extraction] Extracting all worksheets")
    extraction = excel_extraction.extract_spreadsheet(source_path)
    raw_records = excel_extraction.records_from_extraction(extraction, SOURCE_ID)
    sheet_counts: dict[str, int] = {}
    for rec in raw_records:
        sheet_counts[rec["sheet"]] = sheet_counts.get(rec["sheet"], 0) + 1
    for sheet, count in sheet_counts.items():
        _log(f"[extraction]   sheet {sheet!r}: {count} raw records")

    formula_cells = extraction.get("formula_cells", [])
    formula_cols = sorted({c["cell"].rstrip("0123456789") for c in formula_cells})
    _log(f"[extraction] {len(formula_cells)} formula cells documented (EXL-004)")

    meta = {
        "source_id": SOURCE_ID,
        "source_file": source_path,
        "file_type": extraction["file_type"],
        "extraction_method": "openpyxl (data_only cached values; formula cells documented, not re-executed)",
        "sheets": {s["name"]: len(s["raw_rows"]) for s in extraction["sheets"]},
        "authoritative_sheet": AUTHORITATIVE_SHEET,
        "artifact_sheet_note": (
            f"'{ARTIFACT_SHEET}' is an Excel Fuzzy Lookup add-in artifact "
            "embedded in the source workbook (a stale snapshot duplicating "
            "the clause data). Preserved verbatim in the raw layer; excluded "
            "from the clean dataset."
        ),
        "formula_cells": formula_cells,
        "formula_summary": (
            f"{len(formula_cells)} formula cells, all trivial row counters "
            f"('=<prev>+1') in column(s) {formula_cols} of '{ARTIFACT_SHEET}' "
            f"and '{AUTHORITATIVE_SHEET}'. Cached values used; formulas "
            "documented here, never re-executed (EXL-004, SPEC s23)."
        ),
        "partial": False,
    }
    _json_dump(os.path.join(ctx.dir_raw, "raw_records.json"), raw_records)
    _json_dump(os.path.join(ctx.dir_raw, "extraction_meta.json"), meta)
    _log(f"[extraction] {len(raw_records)} raw records extracted (immutable raw layer)")

    # --- normalisation (NR-001..005; authoritative sheet only) ---------
    _log(
        f"[normalise] Building clean dataset from authoritative sheet {AUTHORITATIVE_SHEET!r}"
    )
    auth_raw = [r for r in raw_records if r["sheet"] == AUTHORITATIVE_SHEET]
    clean_records = normalize.normalize_records(auth_raw)
    source_record_count = len(auth_raw)

    # --- number-column reconciliation ----------------------------------
    numbers = []
    for rec in clean_records:
        value = (rec.get("fields") or {}).get("Number")
        numbers.append(
            int(value) if value is not None and str(value).isdigit() else value
        )
    int_numbers = [n for n in numbers if isinstance(n, int)]
    non_integer = [n for n in numbers if not isinstance(n, int)]
    number_counts: dict[int, int] = {}
    for n in int_numbers:
        number_counts[n] = number_counts.get(n, 0) + 1
    duplicate_numbers = sorted(n for n, c in number_counts.items() if c > 1)
    gaps = sorted(set(range(min(int_numbers), max(int_numbers) + 1)) - set(int_numbers))
    number_reconciliation = {
        "number_min": min(int_numbers),
        "number_max": max(int_numbers),
        "numbers_present": len(int_numbers),
        "non_integer_numbers": non_integer,
        "duplicate_numbers": duplicate_numbers,
        "gap_numbers": gaps,
        "gap_note": (
            "Gaps in the Number sequence are consistent with the workbook's "
            "own 'Change History' sheet (e.g. clauses 840, 938, 1010, 916, "
            "584 and 878 are recorded there as removed; numbers extend to "
            "1655 following repeated additions). Gaps not individually "
            "listed in the change history are noted, not fabricated."
        ),
    }
    _log(
        f"[qa] Number column: {len(int_numbers)} records, range "
        f"{min(int_numbers)}-{max(int_numbers)}, {len(gaps)} gaps, "
        f"{len(duplicate_numbers)} duplicate numbers"
    )

    # --- QA + reconciliation -------------------------------------------
    _log("[qa] Running structural validation and duplicate detection")
    findings = validate_mod.validate_records(clean_records, auth_raw)
    _log("[qa] Running reconciliation")
    reconciliation = reconcile_mod.reconcile(
        auth_raw,
        clean_records,
        source_record_count=source_record_count,
        exact_duplicate_groups=findings.get("exact_duplicate_groups"),
    )
    # REC-004: extend the human-readable summary with real number-column facts
    reconciliation["summary_lines"].append(
        f"Clause numbers: {len(int_numbers)} present in range "
        f"{min(int_numbers)}-{max(int_numbers)}; {len(gaps)} gaps "
        f"({', '.join(str(g) for g in gaps)}); {len(duplicate_numbers)} "
        "duplicate clause numbers"
    )
    reconciliation["summary_lines"].append(
        f"Source-true artifact: '{ARTIFACT_SHEET}' "
        f"({sheet_counts.get(ARTIFACT_SHEET, 0)} rows) duplicates clause "
        "data inside the source workbook itself; excluded from the clean "
        "dataset, preserved in raw (REC-003: not an extraction duplicate)"
    )
    reconciliation["summary_lines"].append(
        f"'Change History' sheet ({sheet_counts.get('Change History', 0)} "
        "raw rows) preserved in raw; not clause records"
    )
    reconciliation["number_reconciliation"] = number_reconciliation

    _json_dump(os.path.join(ctx.dir_clean, "clean_records.json"), clean_records)
    qa_report = {
        "source_record_count": source_record_count,
        "extracted_record_count": len(raw_records),
        "extracted_records_by_sheet": sheet_counts,
        "authoritative_sheet_records": len(auth_raw),
        "clean_record_count": len(clean_records),
        "duplicate_count": findings.get("exact_duplicate_count", 0),
        "near_duplicate_pairs": len(findings.get("near_duplicates", [])),
        "missing_value_stats": findings.get("missing_value_stats", {}),
        "source_verified_count": reconciliation.get("source_verified", 0),
        "manual_review_count": reconciliation.get("manual_review_required", 0),
        "formula_cells_documented": len(formula_cells),
        "number_reconciliation": number_reconciliation,
        "reconciliation": reconciliation,
        "findings": findings,
    }
    _json_dump(os.path.join(ctx.dir_reports, "qa_report.json"), qa_report)
    _log(
        f"[qa] {len(clean_records)} clean records; "
        f"{reconciliation['manual_review_required']} flagged for manual review"
    )

    # --- export ---------------------------------------------------------
    _log("[export] Building workbook and CSV")
    provenance = lineage.build_provenance(
        source_id=SOURCE_ID,
        selected=recovery_report["selected_source"],
        retrieval_date=RETRIEVAL_DATE,
        extraction_method=meta["extraction_method"],
    )

    # Count cells changed by typographic-character normalisation (NFKC plus
    # smart-quote/dash/ellipsis replacement) for the LIN-003/NR-002
    # transparency disclosure. Pure whitespace-artefact changes (nbsp, BOM,
    # zero-width space) are excluded from this count.
    _WS_ARTEFACTS = ("\u00a0", "\ufeff", "\u200b")  # nbsp, BOM, zero-width space
    _TYPO_FIXES = {
        bad: good
        for bad, good in normalize._ENCODING_FIXES.items()
        if bad not in _WS_ARTEFACTS
    }

    def _strip_ws_artefacts(value: str) -> str:
        return value.replace("\u00a0", " ").replace("\ufeff", "").replace("\u200b", "")

    def _typo_variant(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        text = unicodedata.normalize("NFKC", _strip_ws_artefacts(value))
        for bad, good in _TYPO_FIXES.items():
            text = text.replace(bad, good)
        return text

    typo_counts = {}
    for col in ("Clause Wording", "Clause Title", "Advice - Comments"):
        typo_counts[col] = sum(
            1
            for rec in auth_raw
            if isinstance((rec.get("fields") or {}).get(col), str)
            and _typo_variant(rec["fields"][col])
            != _strip_ws_artefacts(rec["fields"][col])
        )
    _log(
        f"[export] Typographic-character normalisation changed "
        f"{typo_counts['Clause Wording']} Clause Wording / "
        f"{typo_counts['Clause Title']} Clause Title / "
        f"{typo_counts['Advice - Comments']} Comments cells"
    )

    readme_info = {
        "purpose": (
            "Historical Australian Building and Construction Commission "
            "(ABCC) Agreement Clauses dataset, recovered from a discontinued "
            "public URL via the Internet Archive Wayback Machine and "
            "delivered in a clean, traceable, validated form."
        ),
        "source": f"{ORIGINAL_URL} (recovered from {ARCHIVE_URL})",
        "recovery_method": (
            "Wayback Machine recovery: CDX index research identified 5 "
            "captures of the exact XLSX URL; the 2022-03-12 01:18:33 UTC "
            "capture (digest QSVP27B5JZCKQIDWADPJRXQFTGU2RQAK) holds the "
            "newest content generation and is the exact file the ABCC "
            "resource page linked as 'Download all Agreement Clauses "
            "(Excel)' (archived page snapshot 20220320160705). File "
            "integrity verified by SHA-256 "
            f"{EXPECTED_SHA256}."
        ),
        "recovery_date": RETRIEVAL_DATE,
        "extraction_method": meta["extraction_method"],
        "limitations": (
            "Authoritative data comes from the 'ABCC Clauses' worksheet "
            f"({len(auth_raw)} clause records). The workbook also contains "
            f"'{ARTIFACT_SHEET}' ({sheet_counts.get(ARTIFACT_SHEET, 0)} "
            "rows), an Excel Fuzzy Lookup add-in artifact: a stale snapshot "
            "duplicating clause data, kept verbatim in 02_RAW_DATA but "
            "excluded from 03_CLEAN_DATA. The 'Change History' sheet "
            "(amendment log, not clause records) is likewise raw-only. "
            f"{len(formula_cells)} formula cells (trivial '=<prev>+1' row "
            "counters in column A of both data sheets) were replaced by "
            "their cached values and are documented in "
            "data/raw/extraction_meta.json (EXL-004); no formula was "
            "silently discarded. Clause numbers run 1-"
            f"{max(int_numbers)} with {len(gaps)} gaps consistent with the "
            "workbook's own change history. Internal REC-/RAW-/SRC- "
            "identifiers are generated by this tool and are NOT original "
            "ABCC identifiers. Records marked MANUAL_REVIEW_REQUIRED in "
            "03_CLEAN_DATA/04_QA_REPORT need human review before reliance. "
            "Normalisation disclosure (LIN-003/NR-002 transparency): the "
            "clean layer (03_CLEAN_DATA) applies Unicode NFKC normalisation "
            "plus smart-quote/dash/ellipsis replacement "
            "(\u2013/\u2014\u2192-, \u2018/\u2019\u2192', \u201c/\u201d\u2192\", "
            "\u2026\u2192...), which changed typographic characters in "
            f"{typo_counts['Clause Wording']} Clause Wording / "
            f"{typo_counts['Clause Title']} Clause Title / "
            f"{typo_counts['Advice - Comments']} Comments cells. This is a "
            "character-level transformation only and does not alter wording "
            "or meaning; the original characters remain recoverable "
            "verbatim in 02_RAW_DATA and the raw layer (NR-003)."
        ),
    }
    os.makedirs(ctx.dir_output, exist_ok=True)
    xlsx_path = os.path.join(ctx.dir_output, excel_export.WORKBOOK_NAME)
    csv_path = os.path.join(ctx.dir_output, csv_export.CSV_NAME)
    excel_export.create_workbook(
        raw_records=raw_records,
        clean_records=clean_records,
        qa_findings=findings,
        reconciliation=reconciliation,
        provenance_rows=[provenance.export_row()],
        readme_info=readme_info,
        out_path=xlsx_path,
    )
    csv_export.write_csv(clean_records, csv_path)
    _log("[export] Workbook created")
    _log("[export] CSV created")

    # --- SPEC section 26 outcome block ----------------------------------
    _log("")
    _log("Recovery: SUCCESS")
    _log("Extraction: SUCCESS")
    _log("Validation: COMPLETE")
    _log("Reconciliation: COMPLETE")
    _log(f"Manual Review: {reconciliation['manual_review_required']}")
    _log("Output: CREATED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
