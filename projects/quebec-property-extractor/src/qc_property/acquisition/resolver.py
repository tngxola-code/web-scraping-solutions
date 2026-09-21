import logging
from pathlib import Path
from .index import read_index

logger = logging.getLogger(__name__)

def resolve_municipality(index_path: Path, municipality_name: str) -> tuple[str | None, dict]:
    """
    Resolve the municipality's XML resource URL.
    Returns (url, metadata) or (None, {}) if ambiguous or not found.
    """
    rows = read_index(index_path)
    if not rows:
        logger.error("Index is empty")
        return None, {}

    # Determine column names by checking first row keys
    sample = rows[0]
    # Expect columns: code géographique, nom du territoire, lien
    mun_col = None
    for col in sample.keys():
        if "territoire" in col.lower() or "nom" in col.lower():
            mun_col = col
            break
    if not mun_col:
        # fallback to first column
        mun_col = list(sample.keys())[0]
        logger.warning(f"Could not detect municipality column, using '{mun_col}'")

    url_col = None
    for col in sample.keys():
        if "lien" in col.lower() or "url" in col.lower():
            url_col = col
            break
    if not url_col:
        logger.error("Could not find a URL/lien column in index")
        return None, {}

    # Try multiple variations of the municipality name
    variations = [
        municipality_name,
        f"Ville de {municipality_name}",
        municipality_name.replace("é", "e"),
        f"Ville de {municipality_name}".replace("é", "e"),
    ]
    # Also try without accents for comparison
    normalized_variations = []
    for v in variations:
        normalized_variations.append(v)
        # Remove accents (simple approach)
        import unicodedata
        nf = unicodedata.normalize('NFKD', v).encode('ASCII', 'ignore').decode('ASCII')
        if nf not in normalized_variations:
            normalized_variations.append(nf)

    candidates = []
    for row in rows:
        mun_val = row.get(mun_col, "").strip()
        if mun_val in variations or mun_val in normalized_variations:
            candidates.append(row)
        # Case-insensitive match
        if mun_val.lower() in [v.lower() for v in variations + normalized_variations]:
            if row not in candidates:
                candidates.append(row)

    if len(candidates) == 0:
        # Log some sample values for debugging
        sample_values = [row.get(mun_col, "") for row in rows[:20]]
        logger.error(f"Municipality '{municipality_name}' not found in index column '{mun_col}'")
        logger.debug(f"Sample values: {sample_values}")
        return None, {}

    if len(candidates) > 1:
        logger.error(f"Multiple entries found for '{municipality_name}': {len(candidates)}")
        return None, {}

    row = candidates[0]
    url = row.get(url_col, "").strip()
    if not url:
        logger.error(f"No resource URL found for {municipality_name} in column '{url_col}'")
        return None, {}

    logger.info(f"Resolved {municipality_name} → {url}")
    return url, row