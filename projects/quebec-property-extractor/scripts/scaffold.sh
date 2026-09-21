#!/bin/bash

# ==============================================================================
# setup.sh - Scaffolds the Quebec City Real Estate Extraction Project
# ==============================================================================

echo "🚀 Creating project directory structure..."
mkdir -p quebec-property-extractor/{config,src/qc_property/{sources,extraction,transformation,validation,export,observability},tests/{unit,integration,fixtures},output,logs}
cd quebec-property-extractor

echo "📝 Generating configuration and environment files..."
cat << 'EOF' > pyproject.toml
[project]
name = "qc-property-extractor"
version = "1.0.0"
description = "Quebec City Real Estate Assessment Roll Data Extraction"
requires-python = ">=3.12"
dependencies = [
    "httpx>=0.27.0",
    "beautifulsoup4>=4.12.0",
    "lxml>=5.0.0",
    "playwright>=1.40.0",
    "pandas>=2.2.0",
    "openpyxl>=3.1.0",
    "pydantic>=2.5.0",
    "tenacity>=8.2.0",
    "pyyaml>=6.0.0",
    "click>=8.1.0",
]

[project.scripts]
qc-extract = "qc_property.cli:main"

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"
EOF

cat << 'EOF' > .env.example
SOURCE_TYPE="html"
SOURCE_URL="https://example.com/quebec-roll"
MAX_RETRIES=3
REQUEST_TIMEOUT=30
EOF

cat << 'EOF' > .gitignore
__pycache__/
*.py[cod]
*$py.class
.env
.venv/
venv/
output/*.xlsx
output/*.csv
logs/*.log
.pytest_cache/
EOF

cat << 'EOF' > config/settings.yaml
source:
  type: "html"
  url: "https://example.com/quebec-roll"
extraction:
  max_retries: 3
  request_timeout_seconds: 30
  checkpoint_enabled: true
  rate_limit_delay_ms: 500
output:
  excel: true
  csv: true
  include_exceptions: true
  include_data_dictionary: true
  directory: "./output"
logging:
  level: "INFO"
  file: "./logs/extraction.log"
EOF

cat << 'EOF' > config/schema.yaml
fields:
  - name: roll_number
    type: string
    required: true
  - name: matricule
    type: string
    required: false
  - name: address
    type: string
    required: true
  - name: municipality
    type: string
    required: true
  - name: postal_code
    type: string
    required: false
  - name: property_category
    type: string
    required: false
  - name: land_value
    type: decimal
    required: false
  - name: building_value
    type: decimal
    required: false
  - name: total_assessment
    type: decimal
    required: false
  - name: assessment_year
    type: integer
    required: false
  - name: land_area
    type: decimal
    required: false
EOF

echo "🐍 Generating Python source modules..."
cat << 'EOF' > src/qc_property/__init__.py
"""Quebec City Real Estate Assessment Roll Data Extraction."""
__version__ = "1.0.0"
EOF

cat << 'EOF' > src/qc_property/config.py
import yaml
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional

class SourceConfig(BaseModel):
    type: str = "html"
    url: Optional[str] = None

class ExtractionConfig(BaseModel):
    max_retries: int = 3
    request_timeout_seconds: int = 30
    checkpoint_enabled: bool = True
    rate_limit_delay_ms: int = 500

class OutputConfig(BaseModel):
    excel: bool = True
    csv: bool = True
    include_exceptions: bool = True
    include_data_dictionary: bool = True
    directory: str = "./output"

class LoggingConfig(BaseModel):
    level: str = "INFO"
    file: str = "./logs/extraction.log"

class Settings(BaseModel):
    source: SourceConfig = Field(default_factory=SourceConfig)
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

def load_settings(config_path: str = "config/settings.yaml") -> Settings:
    path = Path(config_path)
    if not path.exists():
        return Settings()
    with open(path, 'r') as f:
        data = yaml.safe_load(f)
    return Settings(**data)
EOF

cat << 'EOF' > src/qc_property/sources/base.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Iterator

class AssessmentSource(ABC):
    @abstractmethod
    def discover_records(self, scope: Dict[str, Any]) -> Iterator[Dict[str, Any]]: pass

    @abstractmethod
    def fetch_record(self, record_ref: Any) -> Dict[str, Any]: pass

    @abstractmethod
    def parse_record(self, raw_data: Dict[str, Any]) -> Dict[str, Any]: pass
EOF

cat << 'EOF' > src/qc_property/sources/mock.py
from qc_property.sources.base import AssessmentSource
from typing import Dict, Any, Iterator
import random

class MockSource(AssessmentSource):
    def __init__(self, record_count=50):
        self.record_count = record_count

    def discover_records(self, scope: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
        streets = ['de la Paix', 'Saint-Jean', 'Cartier', 'Saint-Louis']
        for i in range(self.record_count):
            yield {
                'id': f"REC-{i:04d}",
                'roll_number': f"RN-{100000 + i}" if random.random() > 0.1 else None,
                'matricule': f"MAT-{200000 + i}" if random.random() > 0.2 else None,
                'address': f"  {random.randint(1, 9999)}   Rue {random.choice(streets)}  ",
                'municipality': "Québec",
                'land_value': f"${random.randint(50, 500)} 000",
                'building_value': f"${random.randint(100, 800)} 000",
                'total_assessment': f"${random.randint(150, 1200)} 000",
                'source_ref': f"SRC-{i}"
            }
    def fetch_record(self, record_ref: Any) -> Dict[str, Any]: pass
    def parse_record(self, raw_data: Dict[str, Any]) -> Dict[str, Any]: pass
EOF

cat << 'EOF' > src/qc_property/validation/models.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum

class ValidationStatus(str, Enum):
    VALID = "VALID"
    WARNING = "WARNING"
    INVALID = "INVALID"
    DUPLICATE = "DUPLICATE"
    EXCEPTION = "EXCEPTION"

class PropertyRecord(BaseModel):
    record_id: str
    roll_number: Optional[str] = None
    matricule: Optional[str] = None
    lot_number: Optional[str] = None
    address: Optional[str] = None
    unit: Optional[str] = None
    municipality: Optional[str] = None
    postal_code: Optional[str] = None
    property_category: Optional[str] = None
    land_area: Optional[float] = None
    land_value: Optional[float] = None
    building_value: Optional[float] = None
    total_assessment: Optional[float] = None
    assessment_year: Optional[int] = None
    roll_period: Optional[str] = None
    source_reference: Optional[str] = None
    source_url: Optional[str] = None
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    run_id: str
    validation_status: ValidationStatus = ValidationStatus.VALID
    validation_notes: Optional[str] = None
EOF

cat << 'EOF' > src/qc_property/validation/rules.py
from qc_property.validation.models import PropertyRecord, ValidationStatus
from typing import List, Tuple

def validate_record(record: PropertyRecord) -> Tuple[ValidationStatus, List[str]]:
    notes = []
    status = ValidationStatus.VALID

    if not record.address:
        notes.append("Missing address")
        status = ValidationStatus.INVALID
    if not record.municipality:
        notes.append("Missing municipality")
        status = ValidationStatus.INVALID

    for field in ['land_value', 'building_value', 'total_assessment', 'land_area']:
        val = getattr(record, field)
        if val is not None and val < 0:
            notes.append(f"Negative value in {field}")
            status = ValidationStatus.INVALID

    if record.land_value is not None and record.building_value is not None and record.total_assessment is not None:
        calc_total = record.land_value + record.building_value
        if abs(calc_total - record.total_assessment) > max(100, record.total_assessment * 0.01):
            notes.append(f"Total assessment mismatch: {calc_total} != {record.total_assessment}")
            status = ValidationStatus.WARNING

    if not record.roll_number and not record.matricule and not record.lot_number:
        notes.append("Missing authoritative identifier")
        status = ValidationStatus.WARNING

    return status, notes
EOF

cat << 'EOF' > src/qc_property/validation/reconciliation.py
from dataclasses import dataclass

@dataclass
class ReconciliationStats:
    discovered: int = 0
    attempted: int = 0
    successful: int = 0
    warnings: int = 0
    invalid: int = 0
    duplicates: int = 0
    exceptions: int = 0
    exported: int = 0

    def to_dict(self):
        return self.__dict__
EOF

cat << 'EOF' > src/qc_property/transformation/currency.py
import re
from typing import Optional

def parse_currency(value: Optional[str]) -> Optional[float]:
    if value is None: return None
    if isinstance(value, (int, float)): return float(value)
    cleaned = re.sub(r'[^\d.,-]', '', str(value))
    cleaned = cleaned.replace(' ', '').replace(',', '')
    try:
        return float(cleaned) if cleaned else None
    except ValueError:
        return None
EOF

cat << 'EOF' > src/qc_property/transformation/dates.py
from datetime import datetime
from typing import Optional

def parse_date(value: Optional[str]) -> Optional[str]:
    if not value: return None
    formats = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"]
    for fmt in formats:
        try:
            return datetime.strptime(str(value).strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None
EOF

cat << 'EOF' > src/qc_property/transformation/normalization.py
import re
from typing import Optional

def normalize_whitespace(value: Optional[str]) -> Optional[str]:
    if not value: return None
    return re.sub(r'\s+', ' ', str(value).strip())

def normalize_null(value: Optional[str]) -> Optional[str]:
    if not value: return None
    if str(value).strip().lower() in ('null', 'none', 'n/a', '-', ''):
        return None
    return str(value).strip()
EOF

cat << 'EOF' > src/qc_property/export/excel.py
import pandas as pd
from pathlib import Path
from qc_property.validation.models import PropertyRecord
from qc_property.validation.reconciliation import ReconciliationStats
from datetime import datetime

def export_to_excel(records: list, exceptions: list, stats: ReconciliationStats, output_path: str, run_id: str):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    df_props = pd.DataFrame([r.model_dump() for r in records])
    if df_props.empty:
        df_props = pd.DataFrame(columns=PropertyRecord.model_fields.keys())

    df_exc = pd.DataFrame(exceptions)
    if df_exc.empty:
        df_exc = pd.DataFrame(columns=['record_id', 'source_reference', 'exception_type', 'reason', 'raw_value', 'timestamp'])

    qa_data = {
        'Metric': ['Run ID', 'Extraction Date', 'Records Discovered', 'Records Attempted',
                   'Successful', 'Warnings', 'Invalid', 'Duplicates', 'Exceptions', 'Exported', 'Success %'],
        'Value': [
            run_id, datetime.utcnow().isoformat(), stats.discovered, stats.attempted,
            stats.successful, stats.warnings, stats.invalid, stats.duplicates,
            stats.exceptions, stats.exported,
            f"{(stats.successful / stats.attempted * 100):.2f}%" if stats.attempted > 0 else "0%"
        ]
    }
    df_qa = pd.DataFrame(qa_data)

    dict_data = [
        {'Column': 'roll_number', 'Description': 'Assessment-roll identifier', 'Type': 'string'},
        {'Column': 'address', 'Description': 'Physical property address', 'Type': 'string'},
        {'Column': 'total_assessment', 'Description': 'Total assessed value', 'Type': 'decimal'},
        {'Column': 'validation_status', 'Description': 'QA result (VALID, WARNING, INVALID)', 'Type': 'enum'}
    ]
    df_dict = pd.DataFrame(dict_data)

    with pd.ExcelWriter(path, engine='openpyxl') as writer:
        df_props.to_excel(writer, sheet_name='Properties', index=False)
        df_exc.to_excel(writer, sheet_name='Exceptions', index=False)
        df_qa.to_excel(writer, sheet_name='QA Summary', index=False)
        df_dict.to_excel(writer, sheet_name='Data Dictionary', index=False)

        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            worksheet.freeze_panes = 'A2'
            worksheet.auto_filter.ref = worksheet.dimensions
EOF

cat << 'EOF' > src/qc_property/export/csv.py
import pandas as pd
from pathlib import Path
from qc_property.validation.models import PropertyRecord

def export_to_csv(records: list, output_path: str):
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([r.model_dump() for r in records])
    if df.empty:
        df = pd.DataFrame(columns=PropertyRecord.model_fields.keys())
    df.to_csv(path, index=False, encoding='utf-8')
EOF

cat << 'EOF' > src/qc_property/observability/logging.py
import logging
import sys
from pathlib import Path
from qc_property.config import LoggingConfig

def setup_logging(config: LoggingConfig) -> logging.Logger:
    logger = logging.getLogger("qc_property")
    logger.setLevel(getattr(logging, config.level.upper(), logging.INFO))

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    log_path = Path(config.file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(log_path)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    return logger
EOF

cat << 'EOF' > src/qc_property/pipeline.py
import uuid
from datetime import datetime
from qc_property.config import Settings
from qc_property.sources.mock import MockSource
from qc_property.validation.models import PropertyRecord, ValidationStatus
from qc_property.validation.rules import validate_record
from qc_property.validation.reconciliation import ReconciliationStats
from qc_property.transformation.currency import parse_currency
from qc_property.transformation.normalization import normalize_whitespace, normalize_null
from qc_property.export.excel import export_to_excel
from qc_property.export.csv import export_to_csv
from qc_property.observability.logging import setup_logging

def run_pipeline(settings: Settings, run_id: str = None):
    logger = setup_logging(settings.logging)

    if not run_id:
        run_id = f"QC-ROLL-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"

    logger.info(f"Starting pipeline run: {run_id}")
    stats = ReconciliationStats()

    source = MockSource(record_count=50)
    raw_records = list(source.discover_records(scope={}))
    stats.discovered = len(raw_records)
    logger.info(f"Discovered {stats.discovered} records")

    valid_records = []
    exceptions = []
    seen_ids = set()

    logger.info("Processing records...")
    for raw in raw_records:
        stats.attempted += 1
        try:
            normalized_addr = normalize_whitespace(raw.get('address'))
            land_val = parse_currency(raw.get('land_value'))
            build_val = parse_currency(raw.get('building_value'))
            total_val = parse_currency(raw.get('total_assessment'))

            record = PropertyRecord(
                record_id=raw.get('id', str(uuid.uuid4())),
                roll_number=normalize_null(raw.get('roll_number')),
                matricule=normalize_null(raw.get('matricule')),
                address=normalized_addr,
                municipality=normalize_null(raw.get('municipality', 'Québec')),
                land_value=land_val,
                building_value=build_val,
                total_assessment=total_val,
                source_reference=raw.get('source_ref'),
                run_id=run_id
            )

            dedup_key = record.roll_number or record.matricule or record.record_id
            if dedup_key in seen_ids:
                record.validation_status = ValidationStatus.DUPLICATE
                stats.duplicates += 1
                exceptions.append({'record_id': record.record_id, 'exception_type': 'DUPLICATE', 'reason': f'Key: {dedup_key}', 'timestamp': datetime.utcnow().isoformat()})
                continue
            seen_ids.add(dedup_key)

            status, notes = validate_record(record)
            record.validation_status = status
            record.validation_notes = "; ".join(notes) if notes else None

            if status == ValidationStatus.INVALID:
                stats.invalid += 1
                exceptions.append({'record_id': record.record_id, 'exception_type': 'INVALID', 'reason': record.validation_notes, 'timestamp': datetime.utcnow().isoformat()})
            else:
                if status == ValidationStatus.WARNING: stats.warnings += 1
                valid_records.append(record)
                stats.successful += 1

        except Exception as e:
            stats.exceptions += 1
            exceptions.append({'record_id': raw.get('id'), 'exception_type': 'EXCEPTION', 'reason': str(e), 'timestamp': datetime.utcnow().isoformat()})
            logger.error(f"Error processing record {raw.get('id')}: {e}")

    stats.exported = len(valid_records)
    logger.info(f"Exporting {stats.exported} records to {settings.output.directory}")

    output_dir = settings.output.directory
    if settings.output.excel:
        export_to_excel(valid_records, exceptions, stats, f"{output_dir}/quebec_properties.xlsx", run_id)
    if settings.output.csv:
        export_to_csv(valid_records, f"{output_dir}/quebec_properties.csv")

    logger.info(f"Pipeline completed successfully. Run ID: {run_id}")
    return stats
EOF

cat << 'EOF' > src/qc_property/cli.py
import click
from qc_property.config import load_settings
from qc_property.pipeline import run_pipeline

@click.group()
def main():
    """Quebec City Real Estate Assessment Roll Data Extraction CLI."""
    pass

@main.command()
@click.option('--config', default='config/settings.yaml', help='Path to settings.yaml')
@click.option('--run-id', default=None, help='Custom run ID (auto-generated if omitted)')
def extract(config: str, run_id: str):
    """Run the extraction pipeline."""
    settings = load_settings(config)
    run_pipeline(settings, run_id)

if __name__ == '__main__':
    main()
EOF

echo "📂 Creating empty submodule init files and test structure..."
for dir in sources extraction transformation validation export; do
    touch src/qc_property/$dir/__init__.py
done

touch tests/__init__.py tests/unit/__init__.py tests/integration/__init__.py
cat << 'EOF' > tests/unit/test_models.py
from qc_property.validation.models import PropertyRecord, ValidationStatus

def test_property_record_creation():
    record = PropertyRecord(
        record_id="TEST-001",
        roll_number="1234567",
        address="123 Rue Example",
        municipality="Québec",
        run_id="QC-ROLL-20260903-001"
    )
    assert record.validation_status == ValidationStatus.VALID
    assert record.roll_number == "1234567"
EOF

echo "✅ Project structure and boilerplate created successfully in ./quebec-property-extractor"