import csv
import logging
from pathlib import Path
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10),
       retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)))
def fetch_index(url: str, output_path: Path, timeout: int = 60) -> Path:
    """Download the municipality index CSV."""
    logger.info(f"Downloading index from {url}")
    with httpx.Client(timeout=timeout) as client:
        resp = client.get(url)
        resp.raise_for_status()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(resp.content)
    logger.info(f"Index saved to {output_path}")
    return output_path


def read_index(index_path: Path) -> list[dict]:
    """Read the index CSV and return list of rows."""
    with open(index_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)
