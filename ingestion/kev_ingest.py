"""
CISA Known Exploited Vulnerabilities (KEV) ingestion script.

Fetches the full KEV catalog, maps each entry to the ``vulnerabilities``
table schema, and upserts into Supabase.  On conflict with ``cve_id`` the
KEV-specific columns (``kev_due_date``, ``kev_known_ransomware``) are
updated so NVD-sourced records are *enriched* rather than overwritten.

Run as::

    python -m ingestion.kev_ingest
"""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv

# Load .env before any config imports
load_dotenv()

import httpx  # noqa: E402

from ingestion.config import (  # noqa: E402
    CISA_KEV_PRIMARY,
    CISA_KEV_URL,
    USER_AGENT,
    REQUEST_TIMEOUT,
)
from ingestion.db import (  # noqa: E402
    upsert_vulnerabilities,
    create_ingestion_log,
    complete_ingestion_log,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("ingestion.kev")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_RETRIES: int = 3
_RETRY_BACKOFF_BASE: float = 2.0  # seconds — doubles each attempt


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _fetch_kev_json(client: httpx.Client) -> dict[str, Any]:
    """Download the KEV JSON catalog, trying primary URL then fallback.

    Retries each URL up to ``_MAX_RETRIES`` times with exponential back-off
    before moving on to the fallback.

    Returns:
        Parsed JSON payload (dict).

    Raises:
        RuntimeError: If both URLs are exhausted without a successful fetch.
    """
    urls: list[tuple[str, str]] = [
        (CISA_KEV_PRIMARY, "GitHub mirror (primary)"),
        (CISA_KEV_URL, "CISA official (fallback)"),
    ]

    last_error: Exception | None = None

    for url, label in urls:
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                logger.info(
                    "Fetching KEV from %s — attempt %d/%d",
                    label,
                    attempt,
                    _MAX_RETRIES,
                )
                response = client.get(url, timeout=REQUEST_TIMEOUT)
                response.raise_for_status()
                data: dict[str, Any] = response.json()
                logger.info(
                    "KEV fetched (catalog v%s, %d entries)",
                    data.get("catalogVersion", "?"),
                    len(data.get("vulnerabilities", [])),
                )
                return data
            except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                last_error = exc
                wait = _RETRY_BACKOFF_BASE ** attempt
                logger.warning(
                    "HTTP error from %s (attempt %d): %s — retrying in %.1fs",
                    label,
                    attempt,
                    exc,
                    wait,
                )
                time.sleep(wait)
            except json.JSONDecodeError as exc:
                # Bad JSON is unlikely to self-heal on retry — skip to fallback
                last_error = exc
                logger.error("Invalid JSON from %s: %s", label, exc)
                break

        logger.warning("All retries exhausted for %s", label)

    raise RuntimeError(
        f"Failed to fetch KEV catalog from all sources: {last_error}"
    )


# ---------------------------------------------------------------------------
# Record mapping
# ---------------------------------------------------------------------------


def _parse_kev_entry(entry: dict[str, Any]) -> dict[str, Any] | None:
    """Map a single KEV JSON entry to the ``vulnerabilities`` table schema.

    Returns ``None`` if the entry is missing a CVE ID or fails to parse.
    """
    try:
        cve_id = entry.get("cveID")
        if not cve_id:
            logger.warning("KEV entry missing cveID — skipping: %s", entry)
            return None

        # Build a rich description from available fields
        parts = []
        vuln_name = entry.get("vulnerabilityName", "")
        short_desc = entry.get("shortDescription", "")
        required_action = entry.get("requiredAction", "")

        if vuln_name:
            parts.append(vuln_name)
        if short_desc:
            parts.append(short_desc)
        if required_action:
            parts.append(f"Required Action: {required_action}")

        description = " | ".join(parts) if parts else None

        # Affected products
        vendor = entry.get("vendorProject", "")
        product = entry.get("product", "")
        affected_products = {
            "vendors": [{"vendor": vendor, "product": product}]
        } if vendor or product else None

        # Known ransomware usage
        ransomware_value = entry.get("knownRansomwareCampaignUse", "")
        kev_known_ransomware = ransomware_value == "Known"

        # Due date
        kev_due_date = entry.get("dueDate")

        # Published date (dateAdded)
        date_added = entry.get("dateAdded")
        published_at = None
        if date_added:
            try:
                published_at = datetime.strptime(
                    date_added, "%Y-%m-%d"
                ).replace(tzinfo=timezone.utc).isoformat()
            except ValueError:
                logger.warning(
                    "Could not parse dateAdded '%s' for %s", date_added, cve_id
                )

        return {
            "cve_id": cve_id,
            "source": "kev",
            "description": description,
            "affected_products": affected_products,
            "kev_known_ransomware": kev_known_ransomware,
            "kev_due_date": kev_due_date,
            "published_at": published_at,
        }

    except Exception:
        logger.exception("Failed to parse KEV entry: %s", entry.get("cveID", "<unknown>"))
        return None


# ---------------------------------------------------------------------------
# Main ingestion flow
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry-point: fetch KEV catalog → parse → upsert → log."""
    logger.info("=== CISA KEV Ingestion — starting ===")

    log_id = create_ingestion_log(stream="vulnerabilities", source="kev")
    logger.info("Ingestion run started (log_id=%s)", log_id)

    items_fetched: int = 0
    errors: list[dict[str, str]] = []

    try:
        # Fetch the full catalog
        with httpx.Client(
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        ) as client:
            catalog = _fetch_kev_json(client)

        raw_entries: list[dict[str, Any]] = catalog.get("vulnerabilities", [])
        items_fetched = len(raw_entries)

        # Parse all entries
        parsed_records: list[dict[str, Any]] = []
        for entry in raw_entries:
            record = _parse_kev_entry(entry)
            if record is not None:
                parsed_records.append(record)

        skipped = items_fetched - len(parsed_records)
        if skipped:
            logger.warning(
                "%d/%d KEV entries skipped due to parse errors",
                skipped,
                items_fetched,
            )

        # Upsert into the database
        upserted = upsert_vulnerabilities(parsed_records)
        logger.info(
            "Upserted %d vulnerability records (%d fetched, %d parsed)",
            upserted,
            items_fetched,
            len(parsed_records),
        )

        complete_ingestion_log(
            log_id,
            status="completed",
            items_fetched=items_fetched,
            items_enriched=0,   # enrichment runs separately
            items_embedded=0,   # embedding runs separately
            errors=errors or None,
        )

    except Exception as exc:
        logger.exception("KEV ingestion failed")
        errors.append({"error": f"{type(exc).__name__}: {exc}"})
        complete_ingestion_log(
            log_id,
            status="failed",
            items_fetched=items_fetched,
            items_enriched=0,
            items_embedded=0,
            errors=errors,
        )

    logger.info("=== CISA KEV Ingestion — done ===")


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)
    except Exception:
        logger.exception("Unhandled error in KEV ingestion")
        sys.exit(1)
