"""Command-line interface (SPEC sections 19, 20, 26).

Usage:
    abcc-recovery run | recover | extract | validate | export

``run`` executes the full pipeline.  All stages fail safely: if no
authoritative source is recovered, no dataset or output workbook is
generated and the recovery report records ``SOURCE_NOT_RECOVERED``.
"""

from __future__ import annotations

import argparse
import glob
import json
import logging
import os
import sys
from typing import Any, Optional

from .export import csv as csv_export
from .export import excel as excel_export
from .extraction import excel as excel_extraction
from .extraction import pdf as pdf_extraction
from .extraction.excel import ExtractionError
from .processing import lineage, normalize
from .qa import reconcile as reconcile_mod
from .qa import validate as validate_mod
from .recovery import file_detector
from .recovery.downloader import Downloader
from .recovery.source_discovery import (STATUS_RECOVERED, SourceDiscovery,
                                        load_sources_config)
from .recovery.wayback import WaybackClient

log = logging.getLogger("abcc_recovery.cli")

EXIT_OK = 0
EXIT_RECOVERY_FAILED = 1
EXIT_PIPELINE_FAILED = 2
EXIT_EXPORT_FAILED = 3

RAW_RECORDS = "raw_records.json"
EXTRACTION_META = "extraction_meta.json"
CLEAN_RECORDS = "clean_records.json"
RECOVERY_REPORT = "recovery_report.json"
QA_REPORT = "qa_report.json"


def _log(message: str) -> None:
    print(message, flush=True)


def _json_dump(path: str, payload: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, ensure_ascii=False, default=str)


def _json_load(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


class PipelineContext:
    def __init__(self, base_dir: str, config_path: Optional[str] = None) -> None:
        self.base_dir = base_dir
        self.config_path = config_path or os.path.join(
            base_dir, "config", "sources.yaml"
        )
        self.dir_source = os.path.join(base_dir, "data", "source")
        self.dir_raw = os.path.join(base_dir, "data", "raw")
        self.dir_clean = os.path.join(base_dir, "data", "clean")
        self.dir_output = os.path.join(base_dir, "data", "output")
        self.dir_reports = os.path.join(base_dir, "reports")


# ----------------------------------------------------------------------
# Stages
# ----------------------------------------------------------------------
def stage_recover(
    ctx: PipelineContext,
    discovery: Optional[SourceDiscovery] = None,
) -> tuple[int, dict[str, Any]]:
    """Recovery stage. Returns (exit_code, recovery_report)."""
    _log("[recovery] Searching exact ABCC sources")
    try:
        sources = load_sources_config(ctx.config_path)
    except Exception as exc:  # noqa: BLE001
        _log(f"[recovery] Configuration error: {exc}")
        return EXIT_PIPELINE_FAILED, {
            "status": "CONFIG_ERROR",
            "recovery_errors": [str(exc)],
        }

    if discovery is None:
        wayback = WaybackClient()
        downloader = Downloader()
        discovery = SourceDiscovery(wayback, downloader)

    result = discovery.recover(sources, ctx.dir_source)
    report = result.build_report()
    _json_dump(os.path.join(ctx.dir_reports, RECOVERY_REPORT), report)

    if result.status != STATUS_RECOVERED or not result.selected:
        _log("[recovery] No authoritative source could be recovered")
        return EXIT_RECOVERY_FAILED, report

    _log(f"[file] Detected {result.selected.detected_type}")
    _log("[file] SHA-256 calculated")
    return EXIT_OK, report


def _find_source_file(ctx: PipelineContext) -> Optional[str]:
    report_path = os.path.join(ctx.dir_reports, RECOVERY_REPORT)
    if os.path.exists(report_path):
        try:
            report = _json_load(report_path)
            selected = report.get("selected_source") or {}
            if selected.get("saved_path") and os.path.exists(selected["saved_path"]):
                return selected["saved_path"]
        except Exception:  # noqa: BLE001
            pass
    candidates = sorted(
        p
        for p in glob.glob(os.path.join(ctx.dir_source, "*"))
        if os.path.isfile(p) and not p.endswith(".gitkeep")
    )
    return candidates[0] if candidates else None


def stage_extract(ctx: PipelineContext) -> tuple[int, Optional[dict[str, Any]]]:
    """Extraction stage: recovered source -> raw records (EXL/RAW/PDF)."""
    source_path = _find_source_file(ctx)
    if not source_path:
        _log("[extraction] No recovered source file found in data/source/")
        return EXIT_PIPELINE_FAILED, None

    with open(source_path, "rb") as fh:
        head = fh.read(8192)
    detected = file_detector.detect_file_type(head)
    if detected in (file_detector.TYPE_HTML, file_detector.TYPE_UNKNOWN):
        _log(f"[file] Rejected invalid file content ({detected}); not extracting")
        return EXIT_PIPELINE_FAILED, None
    _log(f"[file] Detected {detected.upper()}")

    source_id = "SRC-0001"  # LIN-001 stable internal source identifier
    try:
        if detected == file_detector.TYPE_PDF:
            extraction = pdf_extraction.extract_pdf(source_path)
            raw_records = pdf_extraction.records_from_pdf(extraction, source_id)
            source_count = None  # PDF text has no determinable record count
        else:
            extraction = excel_extraction.extract_spreadsheet(source_path)
            raw_records = excel_extraction.records_from_extraction(
                extraction, source_id
            )
            # REC-001: determinable count = non-empty data rows after headings
            source_count = len(raw_records)
    except ExtractionError as exc:
        _log(f"[extraction] FAILED: {exc}")
        return EXIT_PIPELINE_FAILED, None

    meta = {
        "source_id": source_id,
        "source_file": source_path,
        "file_type": extraction["file_type"],
        "extraction_method": extraction["extraction_method"],
        "source_record_count": source_count,
        "extracted_record_count": len(raw_records),
        "formula_cells": extraction.get("formula_cells", []),
        "partial": source_count is not None and len(raw_records) != source_count,
    }
    if meta["partial"]:
        # ERR-004: partial extraction is never silently presented as complete
        _log("[extraction] WARNING: partial extraction (counts differ)")
    _json_dump(os.path.join(ctx.dir_raw, RAW_RECORDS), raw_records)
    _json_dump(os.path.join(ctx.dir_raw, EXTRACTION_META), meta)
    _log(f"[extraction] {len(raw_records)} raw records extracted")
    return EXIT_OK, meta


def stage_validate(ctx: PipelineContext) -> tuple[int, Optional[dict[str, Any]]]:
    """Normalisation + QA + reconciliation stage."""
    raw_path = os.path.join(ctx.dir_raw, RAW_RECORDS)
    meta_path = os.path.join(ctx.dir_raw, EXTRACTION_META)
    if not os.path.exists(raw_path):
        _log("[qa] No raw dataset found; run extract first")
        return EXIT_PIPELINE_FAILED, None
    raw_records = _json_load(raw_path)
    meta = _json_load(meta_path) if os.path.exists(meta_path) else {}

    _log("[normalise] Building clean dataset")
    clean_records = normalize.normalize_records(raw_records)
    findings = validate_mod.validate_records(clean_records, raw_records)
    _log("[qa] Running reconciliation")
    reconciliation = reconcile_mod.reconcile(
        raw_records,
        clean_records,
        source_record_count=meta.get("source_record_count"),
        exact_duplicate_groups=findings.get("exact_duplicate_groups"),
    )

    _json_dump(os.path.join(ctx.dir_clean, CLEAN_RECORDS), clean_records)
    qa_report = {
        "source_record_count": meta.get("source_record_count"),
        "extracted_record_count": len(raw_records),
        "clean_record_count": len(clean_records),
        "duplicate_count": findings.get("exact_duplicate_count", 0),
        "missing_value_stats": findings.get("missing_value_stats", {}),
        "source_verified_count": reconciliation.get("source_verified", 0),
        "manual_review_count": reconciliation.get("manual_review_required", 0),
        "reconciliation": reconciliation,
        "findings": findings,
    }
    _json_dump(os.path.join(ctx.dir_reports, QA_REPORT), qa_report)
    _log(
        f"[qa] {len(clean_records)} clean records; "
        f"{reconciliation['manual_review_required']} flagged for manual review"
    )
    return EXIT_OK, qa_report


def stage_export(ctx: PipelineContext) -> int:
    """Export stage: workbook + CSV. Export failure => non-zero exit (ERR-005)."""
    raw_path = os.path.join(ctx.dir_raw, RAW_RECORDS)
    clean_path = os.path.join(ctx.dir_clean, CLEAN_RECORDS)
    if not (os.path.exists(raw_path) and os.path.exists(clean_path)):
        _log("[export] Missing raw/clean dataset; run extract + validate first")
        return EXIT_EXPORT_FAILED
    raw_records = _json_load(raw_path)
    clean_records = _json_load(clean_path)
    meta = (
        _json_load(os.path.join(ctx.dir_raw, EXTRACTION_META))
        if os.path.exists(os.path.join(ctx.dir_raw, EXTRACTION_META))
        else {}
    )
    qa_report = (
        _json_load(os.path.join(ctx.dir_reports, QA_REPORT))
        if os.path.exists(os.path.join(ctx.dir_reports, QA_REPORT))
        else {}
    )
    recovery_report = (
        _json_load(os.path.join(ctx.dir_reports, RECOVERY_REPORT))
        if os.path.exists(os.path.join(ctx.dir_reports, RECOVERY_REPORT))
        else {}
    )

    selected = recovery_report.get("selected_source") or {}
    provenance = lineage.build_provenance(
        source_id=meta.get("source_id", "SRC-0001"),
        selected=selected
        or {"original_url": "unknown", "saved_path": meta.get("source_file")},
        retrieval_date=recovery_report.get("retrieval_date"),
        extraction_method=meta.get("extraction_method"),
    )

    readme_info = {
        "purpose": (
            "Historical ABCC Agreement Clauses dataset recovered from "
            "discontinued public URLs, delivered in a clean, traceable, "
            "validated form."
        ),
        "source": provenance.original_url,
        "recovery_method": "Wayback Machine archive recovery (CDX index + snapshot download)",
        "recovery_date": recovery_report.get("retrieval_date", "unknown"),
        "extraction_method": meta.get("extraction_method", "unknown"),
        "limitations": (
            "Recovered from archived copies; internal REC-/RAW-/SRC- identifiers "
            "are generated by this tool and are NOT original ABCC identifiers. "
            "Records flagged MANUAL_REVIEW_REQUIRED in 04_QA_REPORT need human "
            "review before reliance."
        ),
    }

    os.makedirs(ctx.dir_output, exist_ok=True)
    xlsx_path = os.path.join(ctx.dir_output, excel_export.WORKBOOK_NAME)
    csv_path = os.path.join(ctx.dir_output, csv_export.CSV_NAME)
    try:
        excel_export.create_workbook(
            raw_records=raw_records,
            clean_records=clean_records,
            qa_findings=qa_report.get("findings", {}),
            reconciliation=qa_report.get("reconciliation", {}),
            provenance_rows=[provenance.export_row()],
            readme_info=readme_info,
            out_path=xlsx_path,
        )
        csv_export.write_csv(clean_records, csv_path)
    except excel_export.ExportError as exc:
        _log(f"[export] FAILED: {exc}")
        return EXIT_EXPORT_FAILED
    _log("[export] Workbook created")
    _log("[export] CSV created")
    return EXIT_OK


# ----------------------------------------------------------------------
# Full pipeline
# ----------------------------------------------------------------------
def stage_run(ctx: PipelineContext, discovery: Optional[SourceDiscovery] = None) -> int:
    code, _report = stage_recover(ctx, discovery=discovery)
    if code != EXIT_OK:
        # SPEC section 26 failure block; no dataset is generated
        _log("")
        _log("Recovery: SOURCE_NOT_RECOVERED")
        _log("Dataset Generated: NO")
        return EXIT_RECOVERY_FAILED

    code, _meta = stage_extract(ctx)
    if code != EXIT_OK:
        _log("")
        _log("Recovery: SUCCESS")
        _log("Extraction: FAILED")
        _log("Dataset Generated: NO")
        return code

    code, qa_report = stage_validate(ctx)
    if code != EXIT_OK:
        _log("")
        _log("Recovery: SUCCESS")
        _log("Extraction: SUCCESS")
        _log("Validation: FAILED")
        _log("Dataset Generated: NO")
        return code

    code = stage_export(ctx)
    if code != EXIT_OK:
        _log("")
        _log("Recovery: SUCCESS")
        _log("Extraction: SUCCESS")
        _log("Validation: COMPLETE")
        _log("Output: FAILED")
        return code

    # SPEC section 26 success block
    manual_review = (qa_report or {}).get("manual_review_count", 0)
    _log("")
    _log("Recovery: SUCCESS")
    _log("Extraction: SUCCESS")
    _log("Validation: COMPLETE")
    _log("Reconciliation: COMPLETE")
    _log(f"Manual Review: {manual_review}")
    _log("Output: CREATED")
    return EXIT_OK


# ----------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="abcc-recovery",
        description="Recover the historical ABCC Agreement Clauses dataset.",
    )
    parser.add_argument(
        "command", choices=["run", "recover", "extract", "validate", "export"]
    )
    parser.add_argument(
        "--base-dir",
        default=os.getcwd(),
        help="project base directory containing config/ and data/ (default: cwd)",
    )
    parser.add_argument("--config", default=None, help="path to sources.yaml")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    args = build_parser().parse_args(argv)
    ctx = PipelineContext(args.base_dir, args.config)
    if args.command == "run":
        return stage_run(ctx)
    if args.command == "recover":
        code, _ = stage_recover(ctx)
        return code
    if args.command == "extract":
        code, _ = stage_extract(ctx)
        return code
    if args.command == "validate":
        code, _ = stage_validate(ctx)
        return code
    return stage_export(ctx)


if __name__ == "__main__":
    sys.exit(main())
