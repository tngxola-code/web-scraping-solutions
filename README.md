# Web Scraping Solutions

**Data for teams that can't afford to be wrong.**
Every dataset is delivered with a data-quality report, proof of where each record came
from, and a codebase you own.

## What you get

- **Clean data in the format you use:** Excel, CSV, Google Sheets, a database or an API
- **A data-quality report:** row counts, completeness per field, validation rules passed
  or failed, and a sample audit
- **Proof of source:** every record traces back to the page or file it came from, with
  timestamps and file hashes
- **A codebase you own:** tests, Docker, an optional schedule and a runbook; it runs
  without me
- **Optional monitoring:** scheduled runs, alerts on new or changed data, and fixes when
  a site changes

## The standard behind it

15+ years delivering systems for banks and financial institutions, including Vision Bank
(Saudi Arabia), FNB, ABSA, Standard Bank and Sanlam Glacier (South Africa), where data
has to be correct, traceable and audit-ready. The same standard applies to every
dataset in this repository.

## Projects

| Project | What it does | Pattern | Status |
|---|---|---|---|
| [ABCC Data Recovery](projects/abcc-data-recovery/) · [case study](case-studies/abcc-data-recovery.md) | Recovers a discontinued Australian government dataset from the Wayback Machine, extracts it (spreadsheet first, PDF as fallback), validates it and delivers a traceable Excel workbook and CSV | Records recovery | Complete, 42 offline tests |
| [Québec Property Assessment Extractor](projects/quebec-property-extractor/) · [case study](case-studies/quebec-property-assessment.md) | Finds and downloads Québec municipal assessment rolls from provincial open data, fingerprints the source and streams ~270 MB XML files into a typed model, with CI quality gates | Records portal / bulk open data | In progress |

## How clients receive their solution

1. **Pre-check** of the target site: rendering, access, structure, volume, legal flags.
2. **Sample** of the client's own data before any commitment.
3. **Fixed quote** based on the pre-check.
4. **Delivery:** clean data, a data-quality report and a run manifest.
5. **Handover:** a private repository the client owns, with tests, Docker, a schedule
   and a runbook. It runs without me.
6. **Optional monitoring:** scheduled runs, change alerts and fixes when a site changes.

More in [docs/how-i-work.md](docs/how-i-work.md) and
[docs/responsible-data-collection.md](docs/responsible-data-collection.md).

## What I can build for you

- Catalogue and listing extraction with pagination, detail pages and images
- Lead and directory data from search results or lists of websites
- Site crawls for contacts, opening hours, addresses
- Monitors that alert on new or changed items (listings, prices, notices, tenders)
- Extraction from hidden JSON APIs and JavaScript-heavy sites (Playwright)
- Government and public-records data: portals, open-data files, PDFs, archives

## Repository layout

```
projects/        full source of each portfolio project, with its own README and tests
case-studies/    problem, approach, result and skills for each project
docs/            how I work, and my approach to responsible data collection
```

## Running the projects

Each project is self-contained. From its folder:

```bash
pip install -e ".[test]"   # or ".[dev]" for the Québec project
pytest
```

CI runs both test suites on every push (`.github/workflows/ci.yml`).

## Contact

Themba Ngxola · [GitHub](https://github.com/tngxola-code)
<!-- TODO: add Upwork profile link here -->

## Rights

The code here is shown so prospective clients can evaluate my work. All rights
reserved unless a project states otherwise.
