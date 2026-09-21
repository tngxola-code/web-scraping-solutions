from datetime import datetime

def parse_iso_date(v: str | None) -> datetime | None:
    if not v:
        return None
    try:
        return datetime.fromisoformat(v)
    except:
        return None