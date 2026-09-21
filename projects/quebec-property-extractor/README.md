# Québec Property Assessment Extractor

Pipeline for Québec municipal property assessment rolls (*rôles d'évaluation foncière*),
published by the Ministère des Affaires municipales as open-data XML. It finds a
municipality in the provincial index, downloads its roll, records a SHA-256 fingerprint
of the source, parses the XML as a stream, maps it to a validated record model, and
exports Excel, CSV and a run manifest.

> **Status: work in progress.** Acquisition, fingerprinting, the export layer and the
> quality-gate CI are in place. Mapping of the roll's evaluation-unit records (`RLUEx`
> elements with fields such as `RL0101Ax`) to the
> canonical model is still being wired, so the pipeline does not yet produce a full
> dataset. The longer-term platform vision is in [docs/VISION.md](docs/VISION.md).

## What it shows

| Capability | Where |
|---|---|
| Source discovery from a government index (CSV) and municipality resolution | `src/qc_property/acquisition/` |
| Streamed, atomic download with retries and a SHA-256 source fingerprint | `acquisition/downloader.py`, `provenance.py` |
| Streaming XML parsing for very large files (the Québec City roll is ~270 MB) | `parsing/xml_stream.py` |
| Configuration-driven field mapping to a typed Pydantic model | `parsing/mapper.py`, `models.py` |
| Reconciliation counts and a run manifest for every run | `validation/reconciliation.py`, `export/manifest.py` |
| Excel and CSV export | `export/` |
| Quality gates in CI: lint (ruff, mypy), unit tests, security scan (pip-audit, bandit, detect-secrets) | `gates/`, `.github/workflows/`, [docs/QUALITY_GATES.md](docs/QUALITY_GATES.md) |

## Run

Requires Python 3.12+.

```bash
pip install -e ".[dev]"
qc-property --help            # pipeline CLI
python -m gates.cli --help    # quality gates
pytest                        # tests run offline
```

Source data: [Données Québec – rôles d'évaluation foncière](https://www.donneesquebec.ca/).
Downloaded files go to `data/` (git-ignored).

## Roadmap

1. Wire the `RLUEx` record tag and a versioned field mapping for roll schema 2.6.
2. Produce a sample dataset (first 1,000 units) with a data-quality report.
3. Signed run manifest and a `verify` command that re-hashes the source.
