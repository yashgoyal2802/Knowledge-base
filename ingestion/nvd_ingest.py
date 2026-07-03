"""
NVD CVE Ingestion Script.

Fetches recently modified CVEs from the NIST NVD API v2.0 and upserts
them into the ``vulnerabilities`` table in Supabase.  Designed to run as
a standalone module inside a GitHub Actions cron job::

    python -m ingestion.nvd_ingest

Rate-limiting, pagination, and exponential-backoff retries are handled
internally so the script stays within NVD's published limits.
"""

from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from dotenv import load_dotenv

# Load .env before any config reads (local development)
load_dotenv()

import httpx  # noqa: E402 — must come after load_dotenv()

from ingestion.config import (  # noqa: E402
    MAX_CVES_PER_RUN,
    NVD_API_BASE,
    NVD_API_KEY,
    NVD_REQUEST_DELAY_KEYED,
    NVD_REQUEST_DELAY_UNKEYED,
    NVD_RESULTS_PER_PAGE,
    REQUEST_TIMEOUT,
    USER_AGENT,
)
from ingestion.db import (  # noqa: E402
    complete_ingestion_log,
    create_ingestion_log,
    get_last_ingestion_time,
    upsert_vulnerabilities,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ingestion.nvd")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_RETRIES: int = 3
RETRY_BACKOFF_BASE: float = 2.0  # seconds; doubles each attempt
_RETRYABLE_STATUS_CODES: frozenset[int] = frozenset({403, 429, 500, 502, 503, 504})

# Select the appropriate inter-request delay based on whether an API key
# has been configured.  With a key NVD allows ~50 req / 30 s; without one
# only ~5 req / 30 s.
_REQUEST_DELAY: float = (
    NVD_REQUEST_DELAY_KEYED if NVD_API_KEY else NVD_REQUEST_DELAY_UNKEYED
)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _build_headers() -> dict[str, str]:
    """Return common HTTP headers, optionally including the NVD API key."""
    headers: dict[str, str] = {"User-Agent": USER_AGENT}
    if NVD_API_KEY:
        headers["apiKey"] = NVD_API_KEY
    return headers


def _fetch_page(
    client: httpx.Client,
    params: dict[str, Any],
    *,
    attempt: int = 1,
) -> dict[str, Any]:
    """Fetch a single page from the NVD API with retry / back-off.

    Parameters
    ----------
    client:
        A reusable ``httpx.Client`` instance.
    params:
        Query-string parameters for the NVD ``/cves/2.0`` endpoint.
    attempt:
        Current attempt number (1-indexed).  Callers should not set this;
        the function recurses internally.

    Returns
    -------
    dict
        The parsed JSON response from NVD.

    Raises
    ------
    RuntimeError
        If all retry attempts are exhausted.
    """
    try:
        response = client.get(NVD_API_BASE, params=params)

        # Retry on transient server / rate-limit errors
        if response.status_code in _RETRYABLE_STATUS_CODES:
            if attempt > MAX_RETRIES:
                raise RuntimeError(
                    f"NVD API returned {response.status_code} after "
                    f"{MAX_RETRIES} retries"
                )
            wait = RETRY_BACKOFF_BASE ** attempt
            logger.warning(
                "NVD returned %s — retrying in %.1fs (attempt %d/%d)",
                response.status_code,
                wait,
                attempt,
                MAX_RETRIES,
            )
            time.sleep(wait)
            return _fetch_page(client, params, attempt=attempt + 1)

        # Any other non-2xx status is a hard failure
        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError:
        # Already raised from raise_for_status(); let it propagate.
        raise
    except httpx.TimeoutException as exc:
        if attempt > MAX_RETRIES:
            raise RuntimeError(
                f"NVD API request timed out after {MAX_RETRIES} retries"
            ) from exc
        wait = RETRY_BACKOFF_BASE ** attempt
        logger.warning(
            "Request timed out — retrying in %.1fs (attempt %d/%d)",
            wait,
            attempt,
            MAX_RETRIES,
        )
        time.sleep(wait)
        return _fetch_page(client, params, attempt=attempt + 1)
    except Exception as exc:
        # Catch-all for unexpected transport / JSON errors
        if attempt > MAX_RETRIES:
            raise RuntimeError(
                "NVD API request failed unexpectedly after "
                f"{MAX_RETRIES} retries: {exc}"
            ) from exc
        wait = RETRY_BACKOFF_BASE ** attempt
        logger.warning(
            "Unexpected error (%s) — retrying in %.1fs (attempt %d/%d)",
            exc,
            wait,
            attempt,
            MAX_RETRIES,
        )
        time.sleep(wait)
        return _fetch_page(client, params, attempt=attempt + 1)


# ---------------------------------------------------------------------------
# CVE Parsing
# ---------------------------------------------------------------------------

def _extract_english_description(descriptions: list[dict[str, str]]) -> str | None:
    """Return the English-language description, if present."""
    for desc in descriptions:
        if desc.get("lang") == "en":
            return desc.get("value")
    # Fallback: return whatever is first
    return descriptions[0].get("value") if descriptions else None


def _extract_cvss_v3(
    metrics: dict[str, Any],
) -> tuple[float | None, str | None, str | None]:
    """Extract CVSSv3.1 (preferred) or CVSSv3.0 score, vector, and severity.

    Returns
    -------
    tuple[float | None, str | None, str | None]
        ``(base_score, vector_string, base_severity)``
    """
    # Try v3.1 first, fall back to v3.0
    for key in ("cvssMetricV31", "cvssMetricV30"):
        metric_list = metrics.get(key)
        if metric_list:
            cvss_data = metric_list[0].get("cvssData", {})
            return (
                cvss_data.get("baseScore"),
                cvss_data.get("vectorString"),
                cvss_data.get("baseSeverity"),
            )
    return None, None, None


def _extract_cwe_ids(weaknesses: list[dict[str, Any]]) -> list[str]:
    """Return a deduplicated list of CWE IDs from the weaknesses array."""
    cwe_ids: list[str] = []
    for weakness in weaknesses:
        for desc in weakness.get("description", []):
            value = desc.get("value", "")
            # Filter out the placeholder "NVD-CWE-noinfo" / "NVD-CWE-Other"
            if value.startswith("CWE-"):
                cwe_ids.append(value)
    # Preserve order, remove duplicates
    return list(dict.fromkeys(cwe_ids))


def _parse_cve(cve_item: dict[str, Any]) -> dict[str, Any]:
    """Transform a single NVD API ``cve`` object into a flat dict matching
    the ``vulnerabilities`` table schema.

    Parameters
    ----------
    cve_item:
        A single element from the NVD response ``vulnerabilities`` array.
        Expected shape: ``{"cve": { ... }}``.

    Returns
    -------
    dict
        Column-ready data for ``upsert_vulnerabilities``.
    """
    cve: dict[str, Any] = cve_item.get("cve", {})

    # CVSS v3 metrics
    metrics: dict[str, Any] = cve.get("metrics", {})
    cvss_score, cvss_vector, severity = _extract_cvss_v3(metrics)

    # Reference URLs — store the full list as JSON
    references: list[dict[str, Any]] = cve.get("references", [])
    reference_urls = (
        [{"url": ref.get("url"), "tags": ref.get("tags", [])} for ref in references]
        if references
        else None
    )

    # Affected products / configurations — store raw JSON
    configurations: list[dict[str, Any]] | None = cve.get("configurations")

    return {
        "cve_id": cve.get("id"),
        "source": "nvd",
        "description": _extract_english_description(cve.get("descriptions", [])),
        "cvss_v3_score": cvss_score,
        "cvss_v3_vector": cvss_vector,
        "severity": severity.upper() if severity else None,
        "cwe_ids": _extract_cwe_ids(cve.get("weaknesses", [])),
        "affected_products": configurations,
        "reference_urls": reference_urls,
        "published_at": cve.get("published"),
        "last_modified": cve.get("lastModified"),
    }


# ---------------------------------------------------------------------------
# Main ingestion flow
# ---------------------------------------------------------------------------

def _fetch_all_cves(
    start_date: datetime,
    end_date: datetime,
) -> list[dict[str, Any]]:
    """Page through the NVD API and collect parsed CVE dicts.

    Parameters
    ----------
    start_date:
        Inclusive lower bound for ``lastModStartDate``.
    end_date:
        Inclusive upper bound for ``lastModEndDate``.

    Returns
    -------
    list[dict]
        Parsed CVE rows ready for upserting.  Capped at
        ``MAX_CVES_PER_RUN``.
    """
    all_cves: list[dict[str, Any]] = []
    start_index = 0

    # NVD expects ISO 8601 with explicit offset — always use UTC.
    fmt_start = start_date.strftime("%Y-%m-%dT%H:%M:%S.000+00:00")
    fmt_end = end_date.strftime("%Y-%m-%dT%H:%M:%S.000+00:00")

    headers = _build_headers()

    with httpx.Client(timeout=REQUEST_TIMEOUT, headers=headers) as client:
        while True:
            params: dict[str, Any] = {
                "lastModStartDate": fmt_start,
                "lastModEndDate": fmt_end,
                "startIndex": start_index,
                "resultsPerPage": NVD_RESULTS_PER_PAGE,
            }

            logger.info(
                "Fetching CVEs — startIndex=%d, window=%s → %s",
                start_index,
                fmt_start,
                fmt_end,
            )

            data = _fetch_page(client, params)

            total_results: int = data.get("totalResults", 0)
            vulnerabilities: list[dict[str, Any]] = data.get("vulnerabilities", [])

            if not vulnerabilities:
                logger.info("No more CVEs returned by NVD at startIndex=%d", start_index)
                break

            for item in vulnerabilities:
                try:
                    parsed = _parse_cve(item)
                    all_cves.append(parsed)
                except Exception:
                    # Log and skip malformed entries rather than aborting
                    cve_id = item.get("cve", {}).get("id", "<unknown>")
                    logger.exception("Failed to parse CVE %s — skipping", cve_id)

            logger.info(
                "Fetched %d CVEs so far (total available: %d)",
                len(all_cves),
                total_results,
            )

            # Stop if we've reached the processing cap
            if len(all_cves) >= MAX_CVES_PER_RUN:
                logger.warning(
                    "Reached MAX_CVES_PER_RUN (%d) — stopping pagination early",
                    MAX_CVES_PER_RUN,
                )
                all_cves = all_cves[:MAX_CVES_PER_RUN]
                break

            # Advance the page cursor
            start_index += NVD_RESULTS_PER_PAGE
            if start_index >= total_results:
                break

            # Respect NVD rate limits between page requests
            time.sleep(_REQUEST_DELAY)

    return all_cves


def main() -> None:
    """Entry point for the NVD ingestion pipeline.

    1. Creates an ingestion log entry.
    2. Determines the time window (last successful run → now).
    3. Fetches and parses CVEs from NVD.
    4. Upserts parsed CVEs into ``vulnerabilities``.
    5. Completes the ingestion log.
    """
    logger.info("=== NVD Ingestion — starting ===")

    # Step 1 — create ingestion log
    log_id: str = create_ingestion_log(stream="vulnerabilities", source="nvd")
    logger.info("Ingestion log created: %s", log_id)

    status = "completed"
    errors: list[dict[str, str]] = []
    items_fetched = 0
    items_upserted = 0

    try:
        # Step 2 — determine date window
        last_run = get_last_ingestion_time(stream="vulnerabilities", source="nvd")
        now = datetime.now(tz=timezone.utc)

        if last_run is None:
            start_date = now - timedelta(days=7)
            logger.info("No previous run found — querying last 7 days")
        else:
            start_date = last_run
            logger.info("Last successful run: %s", start_date.isoformat())

        # Step 3 — fetch CVEs from NVD
        cves = _fetch_all_cves(start_date=start_date, end_date=now)
        items_fetched = len(cves)
        logger.info("Fetched %d CVEs from NVD", items_fetched)

        if not cves:
            logger.info("Nothing new to ingest — done")
        else:
            # Step 4 — upsert into the database
            items_upserted = upsert_vulnerabilities(cves)
            logger.info("Upserted %d vulnerabilities into the database", items_upserted)

    except Exception as exc:
        status = "failed"
        error_msg = f"{type(exc).__name__}: {exc}"
        errors.append({"error": error_msg})
        logger.exception("NVD ingestion failed")

    finally:
        # Step 5 — finalize ingestion log
        complete_ingestion_log(
            log_id=log_id,
            status=status,
            items_fetched=items_fetched,
            items_enriched=0,  # enrichment is a separate pipeline step
            items_embedded=0,  # embedding is a separate pipeline step
            errors=errors if errors else None,
        )
        logger.info(
            "=== NVD Ingestion — %s (fetched=%d, upserted=%d) ===",
            status,
            items_fetched,
            items_upserted,
        )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)
    except Exception:
        logger.exception("Unhandled error in NVD ingestion")
        sys.exit(1)
