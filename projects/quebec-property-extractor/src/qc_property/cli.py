import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime          # <-- added

from .config import load_settings
from .observability.logging import setup_logging
from .acquisition.index import fetch_index
from .acquisition.resolver import resolve_municipality
from .acquisition.downloader import download_source
from .parsing.xml_stream import parse_xml
from .parsing.mapper import Mapper
from .validation.reconciliation import reconcile
from .export.excel import export_excel
from .export.csv import export_csv
from .export.manifest import write_manifest


def run_pipeline(year: int, municipality: str, settings_path: Path = Path("config/settings.yaml")):
    settings = load_settings(settings_path)
    setup_logging(level=settings.logging.level, log_file=settings.logging.file)

    logger = logging.getLogger(__name__)
    run_id = f"QC-ROLL-{year}{datetime.now():%Y%m%d}-001"

    logger.info(f"Starting run {run_id} for {municipality}, year {year}")

    # 1. Fetch index
    index_path = Path("data/raw/index.csv")
    fetch_index(settings.source.municipality_index_url, index_path)

    # 2. Resolve municipality
    resource_url, metadata = resolve_municipality(index_path, municipality)
    if not resource_url:
        logger.error("Failed to resolve municipality")
        sys.exit(1)

    # 3. Download XML
    xml_path = Path(f"data/raw/{municipality}_{year}.xml")
    sha256, size = download_source(resource_url, xml_path, timeout=settings.source.timeout_seconds)

    # 4. Parse and map
    mapping = Mapper.load_mapping(settings.parser.mapping_file)
    mapper = Mapper(mapping)
    records = []
    exceptions = []
    for record, exc in parse_xml(xml_path, mapper):
        if record:
            records.append(record)
        if exc:
            exceptions.append(exc)

    # 5. Reconcile
    summary = reconcile(records, exceptions)

    # 6. Export
    output_dir = settings.output.directory
    output_dir.mkdir(parents=True, exist_ok=True)
    if settings.output.excel:
        export_excel(records, exceptions, summary, output_dir / f"{municipality}_{year}.xlsx")
    if settings.output.csv:
        export_csv(records, output_dir / f"{municipality}_{year}.csv")
    if settings.output.manifest:
        manifest = write_manifest(run_id, summary, sha256, size, resource_url, status="SUCCESS")
        (output_dir / "manifest.json").write_text(manifest.to_json())

    logger.info("Run completed successfully")


def main():
    parser = argparse.ArgumentParser(description="Québec Property Extractor")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run full extraction")
    run_parser.add_argument("--year", type=int, default=2026)
    run_parser.add_argument("--municipality", default="Québec")

    args = parser.parse_args()
    if args.command == "run":
        run_pipeline(args.year, args.municipality)
    else:
        parser.print_help()