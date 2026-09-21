def split_address(full_address: str | None) -> dict:
    """Simplistic address split – replace with real parser."""
    if not full_address:
        return {}
    # Dummy implementation
    return {"civic": "", "street": full_address, "locality": ""}