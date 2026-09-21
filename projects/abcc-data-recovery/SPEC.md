# ABCC Data Recovery Requirements Specification

## 1. Purpose

The purpose of the ABCC Data Recovery solution is to recover the historical Australian Building and Construction Commission Agreement Clauses dataset from discontinued public URLs and deliver the recovered information in a clean, traceable, validated Excel and CSV format.

The solution must prioritise recovery of the original spreadsheet or structured dataset.

If the original spreadsheet cannot be recovered, the solution must attempt to recover the original PDF and extract its contents into structured data.

The solution must never fabricate, infer, or substitute source records when authoritative source material cannot be recovered.

---

# 2. Primary Client Requirement

The client supplied the following historical resources:

### Original PDF

`https://www.abcc.gov.au/sites/default/files/abcc_agreement_clauses_spreadsheet.pdf`

### Original resource page

`https://www.abcc.gov.au/resources/agreement-clauses`

Both URLs are currently unavailable.

The required outcome is:

1. Recover the original spreadsheet where possible.
2. Otherwise recover the original PDF.
3. Convert the recovered source into a structured Excel workbook.
4. Validate the extracted dataset against the recovered source.
5. Preserve evidence showing where the recovered information came from.

---

# 3. Project Objectives

The solution must:

* locate archived copies of the historical ABCC Agreement Clauses resource;
* prioritise XLS, XLSX and CSV recovery before PDF reconstruction;
* preserve the original source file where recovered;
* detect the actual recovered file format rather than relying only on file extensions;
* extract structured data from recovered files;
* preserve original source data separately from transformed data;
* provide traceability from every delivered record back to the source where technically possible;
* identify extraction and data-quality anomalies;
* produce an Excel workbook suitable for client use;
* optionally produce CSV where the recovered structure supports CSV representation;
* produce recovery and QA reports;
* fail safely when authoritative source data cannot be recovered.

---

# 4. Scope

## 4.1 In Scope

The project includes:

* historical source discovery;
* Wayback Machine research;
* archived webpage analysis;
* archived asset discovery;
* spreadsheet recovery;
* PDF recovery;
* file integrity validation;
* Excel extraction;
* PDF extraction;
* data normalisation;
* duplicate detection;
* missing-field detection;
* source reconciliation;
* evidence lineage;
* Excel export;
* CSV export;
* QA reporting;
* recovery reporting;
* automated tests for critical pipeline behaviour.

## 4.2 Out of Scope

The project does not include:

* ongoing website scraping;
* recurring data monitoring;
* legal interpretation of ABCC clauses;
* legal compliance advice;
* assessment of whether historical ABCC guidance remains legally applicable;
* extraction of unrelated ABCC resources;
* a hosted web application;
* APIs;
* dashboards;
* databases;
* user authentication;
* cloud deployment;
* bulk historical-document processing beyond the requested Agreement Clauses dataset.

---

# 5. Source Recovery Requirements

## SR-001 Exact URL Recovery

The recovery engine must first attempt to locate archived copies of the exact client-supplied URLs.

The exact URLs must remain preserved in configuration.

## SR-002 Original Spreadsheet Priority

The recovery process must prioritise structured formats in this order:

1. XLSX
2. XLS
3. CSV
4. PDF

A PDF must not be converted if the original spreadsheet can be reliably recovered.

## SR-003 Historical Filename Discovery

The system should search archive records for likely filename variants, including variations around:

* `abcc_agreement_clauses_spreadsheet`
* `agreement_clauses`
* `agreement-clauses`
* `abcc_agreement_clauses`

The actual list may be expanded during investigation.

## SR-004 Archived Resource Page Discovery

The solution must attempt to recover historical versions of the Agreement Clauses webpage.

Where recovered, links contained in the historical webpage should be inspected for:

* XLS;
* XLSX;
* CSV;
* PDF;
* downloadable attachments;
* related historical assets.

## SR-005 Multiple Snapshot Evaluation

The system must not assume that the newest archive snapshot contains the best source.

Relevant snapshots should be evaluated where necessary.

## SR-006 Recovery Logging

Every recovery attempt must record:

* requested URL;
* archive URL;
* archive timestamp;
* HTTP result;
* detected content type;
* detected file type;
* file size;
* SHA-256 checksum;
* recovery outcome;
* error details where applicable.

## SR-007 No Fabricated Recovery

If no authoritative source can be recovered, the production pipeline must report:

`SOURCE_NOT_RECOVERED`

It must not generate substitute data.

---

# 6. File Detection Requirements

## FD-001 Signature-Based File Detection

Recovered files must be validated using file signatures or equivalent content inspection.

The system must not rely solely on:

* filename extensions;
* archive URLs;
* HTTP `Content-Type`.

## FD-002 PDF Validation

A PDF must be validated as a genuine PDF before extraction.

## FD-003 Spreadsheet Validation

XLS and XLSX files must be validated before parsing.

## FD-004 HTML Detection

If an archive request returns an HTML replay page, error page or redirect page rather than the expected document, it must not be processed as a PDF or spreadsheet.

## FD-005 File Hashing

Each accepted source file must have a SHA-256 checksum calculated and recorded.

---

# 7. Extraction Requirements

# 7.1 Spreadsheet Extraction

## EXL-001 Preserve Source Structure

Where a spreadsheet is recovered, the extraction layer must preserve the original:

* worksheets;
* columns;
* row order;
* values;
* headings.

## EXL-002 Raw Copy

The extracted spreadsheet data must first be retained as raw source data before any transformations occur.

## EXL-003 Multiple Sheets

If the original spreadsheet contains multiple worksheets, all relevant sheets must be inspected.

## EXL-004 Formula Handling

If formulas are present, the solution must determine whether the delivered values or formulas are appropriate to preserve.

No formulas should be silently removed without documentation.

---

# 7.2 PDF Extraction

## PDF-001 Inspect Before Parsing

The extraction strategy must be selected after inspecting the actual recovered PDF.

## PDF-002 Native Text First

Native PDF text extraction should be preferred where usable.

## PDF-003 Table Extraction

If the PDF contains structured tables, table-aware extraction should be attempted.

## PDF-004 Positional Extraction

Where the PDF uses visually structured columns that are not recognised as tables, coordinate-based extraction may be used.

## PDF-005 OCR Last Resort

OCR should only be used where the source PDF is scanned or lacks usable embedded text.

## PDF-006 Page Traceability

Extracted records should retain the originating PDF page number where possible.

## PDF-007 Header/Footer Exclusion

Repeated page:

* headers;
* footers;
* page numbers;
* navigation text

must not be incorrectly appended to clause content.

## PDF-008 Multiline Clause Preservation

Clauses spanning multiple lines must remain logically connected.

## PDF-009 Cross-Page Records

Records spanning page boundaries must be detected and handled where technically possible.

---

# 8. Raw Data Requirements

## RAW-001 Immutable Raw Layer

Raw extracted data must not be modified after extraction.

## RAW-002 Original Meaning

The raw dataset must represent the recovered source as closely as practical.

## RAW-003 No Assumed Schema

The solution must not force the source into a predetermined business schema before the actual source structure has been identified.

## RAW-004 Source Metadata

Raw records should include technical metadata separately where required, such as:

* source file;
* page number;
* extraction sequence.

---

# 9. Data Normalisation Requirements

## NR-001 Separate Clean Dataset

Normalisation must produce a separate cleaned dataset.

The raw dataset must remain unchanged.

## NR-002 Non-Destructive Cleaning

Cleaning may address:

* leading whitespace;
* trailing whitespace;
* repeated whitespace;
* encoding issues;
* obvious PDF line-break artefacts;
* column-name consistency.

Cleaning must not alter the legal meaning of clause text.

## NR-003 Preserve Original Values

Where transformations materially change formatting, original values must remain recoverable through the raw dataset.

## NR-004 Missing Values

Missing information must remain null or blank.

The system must not guess missing values.

## NR-005 Stable Record Identifier

Clean records should receive an internal stable identifier for lineage and QA.

This identifier must not be presented as an original ABCC identifier unless it actually came from the source.

---

# 10. Data Lineage Requirements

## LIN-001 Source File Identifier

Every source file must receive a stable internal source identifier.

## LIN-002 Record-Level Traceability

Where possible, each cleaned record must be traceable to:

* source file;
* source worksheet or PDF page;
* source row or extraction sequence;
* raw record identifier.

## LIN-003 Transformation Traceability

Relevant transformations should be documented where they materially change the representation of data.

## LIN-004 Source Provenance

The final deliverable must identify:

* original ABCC URL;
* recovered URL;
* archive timestamp;
* recovery date;
* filename;
* SHA-256 hash;
* extraction method.

---

# 11. Validation Requirements

## QA-001 Structural Validation

The system must validate the resulting data structure.

Examples include:

* empty datasets;
* missing headings;
* empty mandatory-looking records;
* malformed rows.

## QA-002 Duplicate Detection

The system must detect exact duplicates.

Where useful, it should also identify possible near-duplicates.

## QA-003 Missing Data

The system must identify missing values in significant source fields.

## QA-004 Suspicious Extraction

The system should flag suspicious extraction such as:

* unusually short text;
* abruptly truncated text;
* malformed example numbers;
* orphaned continuation lines;
* page header content in records.

## QA-005 Status Terminology

The solution must distinguish between:

* `EXTRACTED`
* `STRUCTURALLY_VALID`
* `SOURCE_VERIFIED`
* `MANUAL_REVIEW_REQUIRED`

A record must not be classified as `SOURCE_VERIFIED` solely because required fields are populated.

## QA-006 Verification Evidence

A source-verification status must be based on evidence that the extracted value agrees with the recovered source.

## QA-007 Review Notes

Any flagged record must contain a human-readable reason for review.

---

# 12. Reconciliation Requirements

## REC-001 Record Count Reconciliation

Where the source exposes a determinable record count, the extraction must reconcile source records against extracted records.

## REC-002 Missing Record Detection

The system must identify cases where source records appear to be absent from the extracted dataset.

## REC-003 Duplicate Reconciliation

Duplicates created by extraction must be distinguishable from duplicates actually present in the source.

## REC-004 Reconciliation Summary

The QA report should provide a summary similar to:

`Source records: 214`

`Extracted records: 214`

`Clean records: 214`

`Source verified: 211`

`Manual review required: 3`

The actual figures must come from the recovered source.

---

# 13. Excel Output Requirements

The primary output must be:

`ABCC_Agreement_Clauses.xlsx`

The workbook should contain:

## 01_README

Must describe:

* dataset purpose;
* source;
* recovery method;
* recovery date;
* extraction method;
* important limitations;
* legal disclaimer.

## 02_RAW_DATA

Must contain the raw extracted representation of the recovered source.

## 03_CLEAN_DATA

Must contain the cleaned, structured client-ready representation.

## 04_QA_REPORT

Must contain:

* total records;
* duplicate findings;
* missing fields;
* suspicious records;
* validation statuses;
* records requiring manual review;
* reconciliation summary.

## 05_SOURCE_PROVENANCE

Must contain:

* source ID;
* original URL;
* recovered URL;
* archive timestamp;
* filename;
* file type;
* file size;
* SHA-256;
* retrieval date;
* extraction method.

---

# 14. Excel Usability Requirements

## XLS-001 Filtering

Client data worksheets must support Excel filters.

## XLS-002 Frozen Header

Relevant sheets must have the header row frozen.

## XLS-003 Text Wrapping

Long clause text must be readable using wrapped cells.

## XLS-004 Column Widths

Column widths should be set to reasonable values.

## XLS-005 Consistent Headers

Headers must use clear and consistent naming.

## XLS-006 No Hidden Data

Data required to understand the dataset must not be hidden in hidden worksheets or hidden columns.

---

# 15. CSV Requirements

A CSV export should be provided where the final cleaned dataset can be represented without losing important workbook structure.

The CSV should be named:

`ABCC_Agreement_Clauses.csv`

CSV must not replace the Excel deliverable.

---

# 16. Recovery Report Requirements

The system must produce:

`reports/recovery_report.json`

The report should contain:

* URLs searched;
* archive queries executed;
* snapshots discovered;
* files considered;
* files rejected;
* files accepted;
* checksum information;
* recovery errors;
* final authoritative source selected;
* recovery status.

---

# 17. QA Report Requirements

The system must produce:

`reports/qa_report.json`

The report should contain:

* source record count where known;
* extracted record count;
* clean record count;
* duplicate count;
* missing-value statistics;
* source verification count;
* manual-review count;
* reconciliation result;
* QA findings.

---

# 18. Error Handling Requirements

## ERR-001 Recovery Failure

Failure to recover a source must terminate production dataset generation safely.

## ERR-002 Invalid File

Invalid file content must not progress to extraction.

## ERR-003 Extraction Failure

Extraction errors must include sufficient information to identify the failing source/page/sheet.

## ERR-004 Partial Extraction

Partial extraction must not be silently presented as complete.

## ERR-005 Export Failure

A failed export must produce a non-zero process exit code.

---

# 19. Logging Requirements

The command-line application should provide concise execution logs.

Example:

```text
[recovery] Searching exact ABCC PDF
[recovery] Found 6 archive snapshots
[recovery] Candidate downloaded
[file] Detected PDF
[file] SHA-256 calculated
[extraction] Extracting 42 pages
[qa] Running reconciliation
[export] Workbook created
```

Logs must not contain fabricated success messages.

---

# 20. Command-Line Requirements

The solution should expose a simple command-line interface.

Preferred usage:

```bash
abcc-recovery run
```

or:

```bash
python -m abcc_recovery.cli run
```

Useful optional commands may include:

```bash
abcc-recovery recover
abcc-recovery extract
abcc-recovery validate
abcc-recovery export
```

The full pipeline should remain executable with one primary command.

---

# 21. Configuration Requirements

Historical source locations should be externalised into:

`config/sources.yaml`

Example:

```yaml
sources:
  - name: agreement_clauses_pdf
    type: pdf
    url: https://www.abcc.gov.au/sites/default/files/abcc_agreement_clauses_spreadsheet.pdf

  - name: agreement_clauses_page
    type: webpage
    url: https://www.abcc.gov.au/resources/agreement-clauses
```

Source URLs must not be duplicated unnecessarily across the codebase.

---

# 22. Test Requirements

Automated tests must cover the critical behaviours of the application.

## test_recovery.py

Must test:

* source configuration loading;
* archive result parsing;
* failed recovery;
* successful candidate selection;
* production pipeline does not create synthetic data when recovery fails.

## test_extraction.py

Must test:

* Excel reading;
* CSV reading where applicable;
* PDF extraction fixtures;
* multiline handling;
* empty input handling.

## test_validation.py

Must test:

* duplicate detection;
* missing values;
* suspicious records;
* status assignment;
* source-verification rules.

## test_export.py

Must test:

* workbook creation;
* expected workbook sheets;
* CSV generation;
* provenance export;
* QA export.

---

# 23. Security Requirements

Although the solution is a small local extraction utility:

* no credentials should be stored in source code;
* downloaded files must be treated as untrusted input;
* filenames from remote sources must not control arbitrary filesystem paths;
* URLs must use HTTPS where available;
* archive response content must be validated before processing;
* spreadsheet formulas should be treated cautiously when generating client-facing output.

---

# 24. Legal and Data Use Requirement

The final workbook must state that the recovered dataset represents historical ABCC material.

It must not claim that the data represents current Australian legal requirements.

Suggested wording:

“This dataset contains historical material recovered from former Australian Building and Construction Commission resources. It is provided for historical/data-recovery purposes and does not constitute legal advice or confirmation of current regulatory requirements.”

---

# 25. Acceptance Criteria

The solution will be considered complete when:

1. The exact historical ABCC resources have been searched.
2. The best publicly recoverable authoritative source has been identified.
3. The original structured spreadsheet has been recovered where available, or the recovered PDF has been extracted where required.
4. The recovered source has been preserved.
5. Source integrity information has been recorded.
6. Raw extracted data has been preserved separately.
7. A cleaned dataset has been produced without changing source meaning.
8. QA checks have been executed.
9. Reconciliation has been performed where possible.
10. Uncertain records have been flagged.
11. No fabricated ABCC records have been introduced.
12. The final Excel workbook contains the required five worksheets.
13. CSV has been produced where appropriate.
14. Recovery and QA JSON reports have been generated.
15. Automated tests for critical functionality pass.
16. The project can be executed using a documented command.
17. The client can trace delivered information back to its recovered source.

---

# 26. Definition of Done

The project is Done when the final delivery package contains:

```text
data/output/
├── ABCC_Agreement_Clauses.xlsx
└── ABCC_Agreement_Clauses.csv

data/source/
└── recovered authoritative source file(s)

reports/
├── recovery_report.json
└── qa_report.json
```

and the final pipeline reports a clear outcome:

```text
Recovery: SUCCESS
Extraction: SUCCESS
Validation: COMPLETE
Reconciliation: COMPLETE
Manual Review: <count>
Output: CREATED
```

If recovery is unsuccessful, the correct outcome is:

```text
Recovery: SOURCE_NOT_RECOVERED
Dataset Generated: NO
```

A synthetic or guessed dataset must never be presented as the recovered ABCC dataset.
