
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator


class PropertyRecord(BaseModel):
    # Identity
    record_id: str
    municipality_code: Optional[str] = None
    municipality_name: Optional[str] = None
    roll_identifier: Optional[str] = None

    # Address
    civic_number: Optional[str] = None
    street_name: Optional[str] = None
    locality: Optional[str] = None
    postal_code: Optional[str] = None
    full_address: Optional[str] = None

    # Property use
    property_use_code: Optional[str] = None
    property_use_description: Optional[str] = None

    # Land & building
    land_area: Optional[Decimal] = None
    building_area: Optional[Decimal] = None
    building_count: Optional[int] = None

    # Assessment
    land_assessment: Optional[Decimal] = None
    building_assessment: Optional[Decimal] = None
    total_assessment: Optional[Decimal] = None

    # Provenance
    source_year: int
    source_file: str
    source_reference: Optional[str] = None
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    run_id: str

    # Validation
    validation_status: str = "VALID"  # VALID, WARNING, INVALID, DUPLICATE, EXCEPTION
    validation_notes: List[str] = Field(default_factory=list)

    # Raw values for provenance (optional)
    raw_values: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("total_assessment", mode="before")
    @classmethod
    def decimal_or_none(cls, v):
        if v is None or v == "":
            return None
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))

    class Config:
        extra = "ignore"  # ignore any extra fields not defined