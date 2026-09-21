# Case study: Québec property assessment rolls

**Project:** [Québec Property Assessment Extractor](../projects/quebec-property-extractor/)
**Pattern:** records portal / bulk government open data
**Status:** in progress

## Problem

Québec publishes the property assessment roll of every municipality as open data, but
as one large XML file per municipality in a coded schema (the Québec City file alone is
about 270 MB). Property investors, analysts and proptech teams need it as clean,
queryable records with evidence of exactly which source file each value came from.

## Approach

- **Discover, don't hard-code.** The pipeline reads the provincial index of rolls and
  resolves the municipality and year requested.
- **Fingerprint the source.** Each roll is downloaded atomically with retries and
  recorded with its SHA-256 hash and size in a run manifest.
- **Stream, don't load.** XML is parsed incrementally so very large rolls run in
  constant memory.
- **Map by configuration.** Coded fields are mapped to a typed Pydantic model through a
  versioned mapping file, so a schema change is a config change.
- **Gate every change.** CI runs lint (ruff, mypy), unit tests and a security scan
  (pip-audit, bandit, detect-secrets) before anything merges.

## Where it stands

Source discovery, download, fingerprinting, the export layer (Excel, CSV, manifest)
and the quality gates work. Wiring the roll's evaluation-unit records to the model is
the next step, followed by a sample dataset with a data-quality report and a signed,
verifiable manifest.

## Skills shown

Government open-data acquisition · large-file streaming XML · configuration-driven
mapping · provenance and run manifests · CI quality gates · Python 3.12 packaging
