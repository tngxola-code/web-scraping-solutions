from decimal import Decimal

def parse_decimal(v: str | None) -> Decimal | None:
    if v is None:
        return None
    v = str(v).replace(",", "").replace(" ", "").strip()
    if not v:
        return None
    try:
        return Decimal(v)
    except:
        return None