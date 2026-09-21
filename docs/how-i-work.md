# How I work

## 1. Pre-check (before quoting)

I check the target site before giving a price: whether pages need a real browser,
signs of anti-bot protection, robots.txt and terms, how pages are linked and paginated,
whether structured data or an API is available, expected volume, and whether personal
data is involved. You get a one-page summary of what I found and any risks.

## 2. Sample

You see a sample of your own data (usually 10–20 rows) before committing.

## 3. Fixed quote and scope

The quote lists the sites, fields, row volume, output formats and schedule. Changes
after that are quoted separately, so there are no surprises on either side.

## 4. Delivery

- The data, in the format you need: Excel, CSV, Google Sheets, a database, or an API
- A **data-quality report**: row counts, completeness per field, validation rules
  passed or failed, and a sample audit
- A **run manifest**: sources, timestamps and file hashes, so every record can be traced

## 5. Handover

You receive a private repository that you own:

- your job configuration and the code to run it, with pinned dependencies
- tests against saved pages from your target site
- Docker, and an optional scheduled GitHub Action
- a README and runbook

It runs without me, my servers or any licence.

## 6. Monitoring (optional)

Scheduled runs, alerts on new or changed items, a monthly health report, and fixes when
a site changes its layout.
