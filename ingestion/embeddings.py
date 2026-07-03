"""Generate vector embeddings for enriched items using Gemini text-embedding-004.

This script fetches articles and vulnerabilities that have been AI-enriched
but lack an embedding vector, generates embeddings via Google's Generative AI
SDK, and persists them back to the database.

Usage:
    python -m ingestion.embeddings
"""

from __future__ import annotations

import logging
import time
from typing import Any

from dotenv import load_dotenv

load_dotenv()

import google.generativeai as genai  # noqa: E402

from ingestion.config import (  # noqa: E402
    GEMINI_API_KEY,
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSIONS,
    GEMINI_ENRICHMENT_DELAY,
)
from ingestion.db import (  # noqa: E402
    get_unembedded_items,
    update_embedding,
    create_ingestion_log,
    complete_ingestion_log,
)

logger = logging.getLogger(__name__)

# Expected dimensionality for pgvector column (VECTOR(768))
_EXPECTED_DIM = 768

# Maximum character length for the text sent to the embedding model
_MAX_EMBED_CHARS = 2000

# Progress logging interval
_LOG_EVERY = 10


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_embedding_text(item: dict[str, Any], table: str) -> str:
    """Combine relevant fields into a single text string for embedding.

    For *articles* the embedding text is built from ``title``,
    ``summary_bullets``, and ``business_angle`` — this gives a
    semantically rich input that captures the gist of the piece plus its
    business relevance.

    For *vulnerabilities* the text includes ``cve_id``, ``description``,
    ``summary_bullets``, and ``severity`` so that similarity search can
    surface CVEs by impact narrative as well as technical detail.

    The result is truncated to 2 000 characters to stay within model
    limits and keep embedding costs predictable.

    Args:
        item: Row dict returned by ``get_unembedded_items``.
        table: Either ``"articles"`` or ``"vulnerabilities"``.

    Returns:
        A single string ready to be sent to the embedding model.
    """
    parts: list[str] = []

    if table == "vulnerabilities":
        # CVE identifier gives strong signal for exact-match retrieval
        if item.get("cve_id"):
            parts.append(item["cve_id"])
        if item.get("description"):
            parts.append(item["description"])
    else:
        # Articles — lead with title
        if item.get("title"):
            parts.append(item["title"])

    # Summary bullets are stored as a Postgres TEXT[] → Python list[str]
    bullets = item.get("summary_bullets")
    if bullets:
        if isinstance(bullets, list):
            parts.append(" ".join(bullets))
        else:
            parts.append(str(bullets))

    if table == "vulnerabilities":
        if item.get("severity"):
            parts.append(f"Severity: {item['severity']}")
    else:
        if item.get("business_angle"):
            parts.append(item["business_angle"])

    text = " ".join(parts).strip()
    if not text:
        text = item.get("title") or item.get("cve_id") or ""

    return text[:_MAX_EMBED_CHARS]


def _generate_embedding(text: str) -> list[float] | None:
    """Call the Gemini embedding API and return the vector, or ``None`` on failure.

    A warning is logged when the returned dimensionality does not match the
    expected 768-dim column so the caller can investigate without crashing.
    """
    try:
        result = genai.embed_content(
            model=EMBEDDING_MODEL,
            content=text,
            task_type="retrieval_document",
            output_dimensionality=EMBEDDING_DIMENSIONS,
        )
        embedding: list[float] = result["embedding"]

        if len(embedding) != _EXPECTED_DIM:
            logger.warning(
                "Embedding dimension mismatch: expected %d, got %d",
                _EXPECTED_DIM,
                len(embedding),
            )

        return embedding
    except Exception:
        logger.exception("Embedding generation failed")
        return None


# ---------------------------------------------------------------------------
# Per-table processing
# ---------------------------------------------------------------------------

def _process_table(table: str) -> tuple[int, int]:
    """Embed all un-embedded rows in *table* and return (processed, errors).

    Items are fetched in a single batch (limit 100). For each item the
    pipeline:

    1. Builds the embedding text from the item's fields.
    2. Calls the Gemini embedding API.
    3. Persists the vector back to the database.
    4. Sleeps ``GEMINI_ENRICHMENT_DELAY`` seconds to stay under rate limits.

    Progress is logged every ``_LOG_EVERY`` items.
    """
    logger.info("Fetching un-embedded %s (limit 100)…", table)
    items: list[dict[str, Any]] = get_unembedded_items(table, limit=100)

    if not items:
        logger.info("No un-embedded %s found — skipping.", table)
        return 0, 0

    logger.info("Processing %d %s for embedding generation.", len(items), table)

    processed = 0
    errors = 0

    for idx, item in enumerate(items, start=1):
        item_id: str = str(item.get("id", "unknown"))
        label = item.get("cve_id") or item.get("title", item_id)

        try:
            text = build_embedding_text(item, table)
            if not text:
                logger.warning("[%s] Empty embedding text — skipping %s", table, label)
                errors += 1
                continue

            embedding = _generate_embedding(text)
            if embedding is None:
                logger.error("[%s] Failed to generate embedding for %s", table, label)
                errors += 1
                continue

            update_embedding(table, item_id, embedding)
            processed += 1

            if idx % _LOG_EVERY == 0:
                logger.info(
                    "[%s] Progress: %d / %d embedded (%d errors so far)",
                    table,
                    processed,
                    len(items),
                    errors,
                )

            # Rate-limit: ~13 RPM → sleep between calls
            time.sleep(GEMINI_ENRICHMENT_DELAY)

        except Exception:
            logger.exception(
                "[%s] Unexpected error processing %s — skipping", table, label
            )
            errors += 1

    logger.info(
        "[%s] Finished: %d embedded, %d errors out of %d total.",
        table,
        processed,
        errors,
        len(items),
    )
    return processed, errors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry-point: embed enriched articles, then vulnerabilities."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    )

    logger.info("=== Embedding pipeline starting ===")

    # Configure the Google Generative AI SDK
    genai.configure(api_key=GEMINI_API_KEY)

    total_embedded = 0
    total_errors = 0

    for table in ("articles", "vulnerabilities"):
        log_id = create_ingestion_log(stream=table, source="embeddings")

        embedded, errs = _process_table(table)
        total_embedded += embedded
        total_errors += errs

        complete_ingestion_log(
            log_id,
            items_fetched=embedded + errs,
            items_enriched=0,
            items_embedded=embedded,
            errors={"count": errs} if errs else None,
            status="completed" if errs == 0 else "completed",
        )

    logger.info(
        "=== Embedding pipeline finished: %d embedded, %d errors ===",
        total_embedded,
        total_errors,
    )


if __name__ == "__main__":
    main()
