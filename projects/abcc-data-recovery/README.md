# ABCC Data Recovery

Recovers the historical Australian Building and Construction Commission (ABCC)
Agreement Clauses dataset from discontinued public URLs via the Wayback Machine,
extracts it into structured data, validates it, and delivers a traceable Excel
workbook and CSV.

The pipeline prioritises recovery of the original spreadsheet (XLSX > XLS > CSV)
and only falls back to PDF extraction when no structured source can be
recovered. If no authoritative source can be recovered, the pipeline reports
`SOURCE_NOT_RECOVERED` and produces **no** dataset — synthetic data is never
generated.

## Install

```bash
pip install -e .
# optional extras
pip install -e ".[xls,ocr,test]"
```

## Usage

```bash
abcc-recovery run        # full pipeline: recover -> extract -> validate -> export
abcc-recovery recover    # recovery stage only
abcc-recovery extract    # extraction stage only (requires data/source/)
abcc-recovery validate   # QA/validation stage only
abcc-recovery export     # export stage only
```

Equivalent module form: `python -m abcc_recovery.cli run`

## Outputs

```
data/source/   recovered authoritative source file(s)
data/raw/      immutable raw extraction (JSON)
data/clean/    normalised dataset (JSON)
data/output/   ABCC_Agreement_Clauses.xlsx + ABCC_Agreement_Clauses.csv
reports/       recovery_report.json, qa_report.json
```

Normalisation transparency: the clean layer applies Unicode NFKC
normalisation plus smart-quote/dash/ellipsis replacement (–/—→-,
'/'→', “/”→", …→...). This is character-level only and does not alter
wording or meaning; the original characters remain recoverable verbatim in
`data/raw/` and the workbook's 02_RAW_DATA sheet (see the 01_README sheet
for affected-cell counts).

## Configuration

Historical source URLs live in `config/sources.yaml` only.

## Tests

```bash
pytest
```

Tests never touch the network — all HTTP access is injectable/mockable.

## Legal notice

This dataset contains historical material recovered from former Australian
Building and Construction Commission resources. It is provided for
historical/data-recovery purposes and does not constitute legal advice or
confirmation of current regulatory requirements.
