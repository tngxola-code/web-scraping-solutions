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
