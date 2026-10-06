"""HTTP fetch helper for DSE Quant loaders.
One function: fetch_json(url, *, cache_dir=None, cache_slug=None) -> FetchResult.
Design:
  - requests, no urllib3.Retry
  - timeout=(5, 30) connect/read
  - one retry on ConnectionError or Timeout, 2s sleep, logged at WARNING
  - explicit raise_for_status()
  - optional raw payload caching to audit/raw/ with a deterministic filename
Returns metadata (final URL, status, byte size, cache path) so callers can
record provenance in load_log.raw_file_ref and source_endpoint.
"""
from __future__ import annotations
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse
import requests
from src import paths
logger = logging.getLogger(__name__)
_DEFAULT_CONNECT_TIMEOUT = 5.0
_DEFAULT_READ_TIMEOUT = 30.0
_RETRY_SLEEP_SECONDS = 2.0
_USER_AGENT = "dse-quant-v2/1.0"
@dataclass(frozen=True)
class FetchResult:
    """Result of a fetch_json call. Immutable."""
    data: Any
    url: str
    status_code: int
    byte_size: int
    elapsed_seconds: float
    cache_path: Optional[Path]
def _url_slug(url: str) -> str:
    """Deterministic short slug from a URL.
    Uses the host + last path segment, sanitized to [A-Za-z0-9_.-].
    Falls back to 'root' if the path is empty.
    """
    parsed = urlparse(url)
    host = parsed.netloc or "unknown"
    path = parsed.path.strip("/") or "root"
    seg = path.split("/")[-1] or "root"
    raw = f"{host}__{seg}"
    safe = "".join(c if (c.isalnum() or c in "._-") else "_" for c in raw)
    return safe[:80]
def _cache_filename(url: str, payload_bytes: bytes) -> str:
    """Build the standardized cache filename.
    Format: {YYYYMMDD-HHMMSS}__{url_slug}__{sha256_prefix8}.json
    Uses UTC for the timestamp to match the audit probes.
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    digest = hashlib.sha256(payload_bytes).hexdigest()[:8]
    return f"{ts}__{_url_slug(url)}__{digest}.json"
def _write_cache(url: str, payload_bytes: bytes, cache_dir: Path) -> Path:
    """Write raw payload to cache_dir and return the path."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    filename = _cache_filename(url, payload_bytes)
    path = cache_dir / filename
    # Binary write, no encoding games.
    path.write_bytes(payload_bytes)
    return path
def fetch_json(
    url: str,
    *,
    cache_dir: Optional[Path] = None,
    connect_timeout: float = _DEFAULT_CONNECT_TIMEOUT,
    read_timeout: float = _DEFAULT_READ_TIMEOUT,
    extra_headers: Optional[dict[str, str]] = None,
) -> FetchResult:
    """Fetch a URL, parse JSON, optionally cache the raw payload.
    Retries once on connection errors or timeouts. HTTP error status codes
    raise via raise_for_status(); the caller should let those propagate.
    """
    headers = {"User-Agent": _USER_AGENT, "Accept": "application/json"}
    if extra_headers:
        headers.update(extra_headers)
    started = time.monotonic()
    last_exc: Optional[Exception] = None
    response: Optional[requests.Response] = None
    for attempt in (1, 2):
        try:
            logger.info("GET %s (attempt %d)", url, attempt)
            response = requests.get(
                url,
                headers=headers,
                timeout=(connect_timeout, read_timeout),
            )
            response.raise_for_status()
            break
        except (requests.ConnectionError, requests.Timeout) as exc:
            last_exc = exc
            if attempt == 1:
                logger.warning(
                    "Fetch attempt %d failed (%s); retrying in %.1fs",
                    attempt, type(exc).__name__, _RETRY_SLEEP_SECONDS,
                )
                time.sleep(_RETRY_SLEEP_SECONDS)
                continue
            logger.error("Fetch attempt %d failed (%s); giving up",
                         attempt, type(exc).__name__)
            raise
    assert response is not None  # for type checkers; loop guarantees this
    elapsed = time.monotonic() - started
    payload_bytes = response.content
    cache_path: Optional[Path] = None
    if cache_dir is not None:
        cache_path = _write_cache(url, payload_bytes, cache_dir)
        logger.info("cached raw payload -> %s", cache_path)
    try:
        data = json.loads(payload_bytes)
    except json.JSONDecodeError as exc:
        logger.error("Response body is not valid JSON: %s", exc)
        raise
    logger.info(
        "GET %s -> %d, %d bytes, %.3fs",
        url, response.status_code, len(payload_bytes), elapsed,
    )
    return FetchResult(
        data=data,
        url=response.url,
        status_code=response.status_code,
        byte_size=len(payload_bytes),
        elapsed_seconds=elapsed,
        cache_path=cache_path,
    )
__all__ = ["FetchResult", "fetch_json"]