# Case study: recovering a discontinued government dataset

**Project:** [ABCC Data Recovery](../projects/abcc-data-recovery/)
**Pattern:** records recovery from archived public sources

## Problem

The Australian Building and Construction Commission's *Agreement Clauses* dataset was
published as a spreadsheet and a PDF on abcc.gov.au. When the commission was wound
down, those URLs stopped working. The client needed the original data back in a clean,
usable form, with confidence that nothing had been invented or silently altered.

## Approach

- **Recover the original, not a copy of a copy.** The pipeline searches Wayback Machine
  snapshots of the known URLs and historical filenames, and prefers the original
  spreadsheet (XLSX, then XLS, then CSV). It only falls back to extracting the PDF when
  no structured file can be recovered.
- **Check every file is what it claims to be.** Downloads are identified by file
  signature, not extension; archive replay pages and error pages are rejected; every
  recovered file is hashed.
- **Never fabricate.** If no authoritative source can be recovered, the run reports
  `SOURCE_NOT_RECOVERED` and produces no dataset.
- **Keep raw and clean apart.** Extraction writes an immutable raw layer first. The
  clean layer applies only character-level normalisation (Unicode NFKC, smart quotes
  and dashes), and the workbook states how many cells were affected, so the original
  wording stays recoverable.
- **Prove it.** Recovery and QA reports record sources, snapshots, hashes and
  validation results.

## Result

- Excel workbook and CSV of the agreement clauses; the workbook carries five sheets
  (README, raw data, clean data, QA report, source provenance) so every value is traceable
- `recovery_report.json` and `qa_report.json` for every run
- One-command CLI (`abcc-recovery run`) with separate recover, extract, validate and
  export stages
- 42 tests that run fully offline; all network access is injectable

## Skills shown

Web archive recovery · file-type detection · spreadsheet and PDF extraction (with OCR
as a last resort) · data lineage · validation and reconciliation · Python packaging and
testing
