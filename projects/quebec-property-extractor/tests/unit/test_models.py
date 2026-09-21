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
