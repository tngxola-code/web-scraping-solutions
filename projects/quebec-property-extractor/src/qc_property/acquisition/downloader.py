import logging
import shutil
import tempfile
from pathlib import Path
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from ..provenance import compute_sha256

logger = logging.getLogger(__name__)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10),
       retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)))
def download_source(url: str, output_path: Path, timeout: int = 60) -> tuple[str, int]:
    """Download XML source, compute SHA256, return (checksum, size)."""
    logger.info(f"Downloading source from {url}")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Use a temporary file to avoid partial writes
    with tempfile.NamedTemporaryFile(delete=False, suffix=".part") as tmp:
        tmp_path = Path(tmp.name)
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            with client.stream("GET", url) as resp:
                resp.raise_for_status()
                total = 0
                for chunk in resp.iter_bytes(chunk_size=8192):
                    tmp.write(chunk)
                    total += len(chunk)
        tmp.flush()

    # Atomically rename
    shutil.move(str(tmp_path), str(output_path))
    logger.info(f"Downloaded {total} bytes to {output_path}")

    sha256 = compute_sha256(output_path)
    logger.info(f"SHA256: {sha256}")
    return sha256, total