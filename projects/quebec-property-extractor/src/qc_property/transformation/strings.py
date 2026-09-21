def normalize_whitespace(s: str | None) -> str | None:
    """Trim and normalize inner whitespace."""
    if s is None:
        return None
    return " ".join(s.split())