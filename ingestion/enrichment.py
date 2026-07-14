"""
AI enrichment pipeline for CyberIntel.

Fetches unenriched articles and vulnerabilities from Supabase,
sends each to Gemini 2.0 Flash for structured summaries, then
writes the enrichment data back.  Designed to run synchronously
inside a GitHub Actions cron job.

Usage:
    python -m ingestion.enrichment
"""

import json
import logging
import re
import time
from typing import Any

from dotenv import load_dotenv

load_dotenv()

import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted

from ingestion.config import (
    GEMINI_API_KEY,
    GEMINI_ENRICHMENT_DELAY,
    GEMINI_MODEL,
    ENRICHMENT_SYSTEM_PROMPT,
)
from ingestion.db import (
    complete_ingestion_log,
    create_ingestion_log,
    get_unenriched_items,
    update_enrichment,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_CONTENT_CHARS: int = 3_000
"""Max characters of body text sent to Gemini (saves tokens)."""

ITEMS_PER_TABLE: int = 50
"""Maximum items to process per table per run."""

PROGRESS_LOG_INTERVAL: int = 10
"""Print a progress message every N items."""

# Regex to extract a JSON object wrapped in markdown fences.
_JSON_FENCE_RE = re.compile(
    r"```(?:json)?\s*\n?(\{.*?\})\s*\n?```",
    re.DOTALL,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def parse_enrichment_response(text: str) -> dict[str, Any] | None:
    """Parse the Gemini response text as JSON.

    Handles the common case where the model wraps JSON in markdown
    code fences (````json … ````) even though the system prompt asks
    it not to.

    Returns
    -------
    dict | None
        Parsed enrichment payload with ``summary_bullets``,
        ``business_angle``, and ``interview_nugget`` keys,
        or ``None`` if parsing fails.
    """
    # First attempt: direct parse (ideal case).
    try:
        return json.loads(text)  # type: ignore[return-value]
    except json.JSONDecodeError:
        pass

    # Second attempt: strip markdown fences and re-parse.
    match = _JSON_FENCE_RE.search(text)
    if match:
        try:
            return json.loads(match.group(1))  # type: ignore[return-value]
        except json.JSONDecodeError:
            pass

    # Give up.
    logger.warning("Failed to parse enrichment JSON from response")
    logger.debug("Raw response text:\n%s", text)
    return None


def build_prompt(item: dict[str, Any], table: str) -> str:
    """Build the enrichment prompt for a single item.

    Parameters
    ----------
    item:
        Row dict from Supabase (articles or vulnerabilities).
    table:
        ``"articles"`` or ``"vulnerabilities"``.

    Returns
    -------
    str
        The user-message prompt sent to Gemini.
    """
    if table == "vulnerabilities":
        cve_id: str = item.get("cve_id", "UNKNOWN")
        description: str = (item.get("description") or "")[:MAX_CONTENT_CHARS]
        return (
            f"CVE ID: {cve_id}\n\n"
            f"Description:\n{description}"
        )

    # Default: articles / research
    title: str = item.get("title", "Untitled")
    raw_content: str = (item.get("raw_content") or "")[:MAX_CONTENT_CHARS]
    return (
        f"Title: {title}\n\n"
        f"Content:\n{raw_content}"
    )


# ---------------------------------------------------------------------------
# Core enrichment loop
# ---------------------------------------------------------------------------


def enrich_table(
    model: genai.GenerativeModel,
    table: str,
    stream: str,
) -> tuple[int, int, list[dict[str, str]]]:
    """Enrich all unenriched rows in *table*.

    Parameters
    ----------
    model:
        Configured ``GenerativeModel`` instance.
    table:
        ``"articles"`` or ``"vulnerabilities"``.
    stream:
        Ingestion stream label (``"news"``, ``"research"``, ``"vuln"``).

    Returns
    -------
    tuple[int, int, list]
        ``(items_processed, items_enriched, errors)``
    """
    items: list[dict[str, Any]] = get_unenriched_items(
        table=table,
        limit=ITEMS_PER_TABLE,
    )

    if not items:
        logger.info("No unenriched items in %s — skipping", table)
        return 0, 0, []

    logger.info(
        "Starting enrichment for %d items from %s",
        len(items),
        table,
    )

    processed: int = 0
    enriched: int = 0
    errors: list[dict[str, str]] = []

    for idx, item in enumerate(items, start=1):
        item_id: str = str(item.get("id", "?"))
        label: str = item.get("cve_id") or item.get("title", item_id)

        try:
            prompt = build_prompt(item, table)
            response = model.generate_content(prompt)

            # Gemini may return no text if the content was blocked.
            if not response.text:
                msg = f"Empty response for {label}"
                logger.warning(msg)
                errors.append({"item_id": item_id, "error": msg})
                processed += 1
                continue

            parsed = parse_enrichment_response(response.text)
            if parsed is None:
                msg = f"JSON parse failure for {label}"
                logger.warning(msg)
                errors.append({"item_id": item_id, "error": msg})
                processed += 1
                continue

            # Write enrichment back to Supabase.
            update_enrichment(
                table=table,
                item_id=item_id,
                enrichment={
                    "summary_bullets": parsed.get("summary_bullets", []),
                    "business_angle": parsed.get("business_angle", ""),
                    "interview_nugget": parsed.get("interview_nugget", ""),
                },
            )

            enriched += 1

        except ResourceExhausted:
            msg = f"Rate-limited by Gemini API on {label}"
            logger.error(msg)
            errors.append({"item_id": item_id, "error": msg})
            # Back off longer when rate-limited, then continue.
            time.sleep(GEMINI_ENRICHMENT_DELAY * 3)

        except Exception as exc:  # noqa: BLE001
            msg = f"Unexpected error enriching {label}: {exc}"
            logger.error(msg, exc_info=False)
            errors.append({"item_id": item_id, "error": str(exc)})

        finally:
            processed += 1

            # Progress logging every N items.
            if idx % PROGRESS_LOG_INTERVAL == 0:
                logger.info(
                    "[%s] %d / %d processed  (%d enriched, %d errors)",
                    table,
                    idx,
                    len(items),
                    enriched,
                    len(errors),
                )

            # Rate-limit delay between Gemini calls.
            time.sleep(GEMINI_ENRICHMENT_DELAY)

    logger.info(
        "Finished %s: %d processed, %d enriched, %d errors",
        table,
        processed,
        enriched,
        len(errors),
    )
    return processed, enriched, errors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the full enrichment pipeline."""

    logger.info("=== CyberIntel enrichment pipeline starting ===")

    # Configure Gemini SDK.
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        GEMINI_MODEL,
        system_instruction=ENRICHMENT_SYSTEM_PROMPT,
    )
    logger.info("Gemini model configured: %s", GEMINI_MODEL)

    # ------------------------------------------------------------------
    # 1. Enrich articles (news + research share the same table)
    # ------------------------------------------------------------------
    article_log_id = create_ingestion_log(stream="enrichment", source="articles")

    art_processed, art_enriched, art_errors = enrich_table(
        model=model,
        table="articles",
        stream="enrichment",
    )

    complete_ingestion_log(
        log_id=article_log_id,
        items_fetched=art_processed,
        items_enriched=art_enriched,
        errors=art_errors,
    )

    # ------------------------------------------------------------------
    # 2. Enrich vulnerabilities
    # ------------------------------------------------------------------
    vuln_log_id = create_ingestion_log(stream="enrichment", source="vulnerabilities")

    vuln_processed, vuln_enriched, vuln_errors = enrich_table(
        model=model,
        table="vulnerabilities",
        stream="enrichment",
    )

    complete_ingestion_log(
        log_id=vuln_log_id,
        items_fetched=vuln_processed,
        items_enriched=vuln_enriched,
        errors=vuln_errors,
    )

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    total_enriched = art_enriched + vuln_enriched
    total_errors = len(art_errors) + len(vuln_errors)
    logger.info(
        "=== Enrichment complete — %d enriched, %d errors ===",
        total_enriched,
        total_errors,
    )


if __name__ == "__main__":
    main()
