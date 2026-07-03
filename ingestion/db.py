"""
Database helpers for the ingestion pipeline.

Wraps the shared Supabase PostgREST client with ingestion-specific
operations: article/vulnerability upserts, enrichment updates,
embedding storage, and ingestion-run logging.

All functions use the service-role key (bypasses RLS) and include
error handling so that pipeline scripts never crash on a single
DB failure.
"""

from datetime import datetime
import logging
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

from shared.supabase_client import get_supabase_client

logger = logging.getLogger("ingestion.db")

# ---------------------------------------------------------------------------
# Supabase client (service-role key — bypasses RLS)
# ---------------------------------------------------------------------------

_client = get_supabase_client(use_service_key=True)


# ---------------------------------------------------------------------------
# Article & Vulnerability Upserts
# ---------------------------------------------------------------------------


def upsert_articles(articles: list[dict]) -> int:
    """
    Upsert articles into the ``articles`` table.

    Uses ``url`` as the conflict key so duplicate URLs are updated
    rather than inserted twice.

    Args:
        articles: List of article dicts matching the ``articles`` schema.

    Returns:
        Number of rows upserted, or ``0`` on error.
    """
    if not articles:
        return 0

    try:
        response = (
            _client.table("articles")
            .upsert(articles, on_conflict="url")
            .execute()
        )
        count = len(response.data) if response.data else 0
        logger.info("Upserted %d articles", count)
        return count
    except Exception:
        logger.exception("Failed to upsert %d articles", len(articles))
        return 0


def upsert_vulnerabilities(vulns: list[dict]) -> int:
    """
    Upsert vulnerabilities into the ``vulnerabilities`` table.

    Uses ``cve_id`` as the conflict key so duplicate CVE IDs are
    updated rather than inserted twice.

    Args:
        vulns: List of vulnerability dicts matching the ``vulnerabilities``
               schema.

    Returns:
        Number of rows upserted, or ``0`` on error.
    """
    if not vulns:
        return 0

    try:
        response = (
            _client.table("vulnerabilities")
            .upsert(vulns, on_conflict="cve_id")
            .execute()
        )
        count = len(response.data) if response.data else 0
        logger.info("Upserted %d vulnerabilities", count)
        return count
    except Exception:
        logger.exception("Failed to upsert %d vulnerabilities", len(vulns))
        return 0


# ---------------------------------------------------------------------------
# Enrichment Helpers
# ---------------------------------------------------------------------------


def get_unenriched_items(table: str, limit: int = 50) -> list[dict]:
    """
    Fetch items that have not yet been enriched.

    Works for both ``articles`` and ``vulnerabilities`` tables.

    Args:
        table: Table name (``"articles"`` or ``"vulnerabilities"``).
        limit: Maximum number of rows to return.

    Returns:
        List of row dicts, or an empty list on error.
    """
    try:
        response = (
            _client.table(table)
            .select("*")
            .eq("enriched", False)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        items = response.data or []
        logger.info("Fetched %d unenriched items from %s", len(items), table)
        return items
    except Exception:
        logger.exception("Failed to fetch unenriched items from %s", table)
        return []


def update_enrichment(table: str, item_id: str, enrichment: dict) -> bool:
    """
    Apply AI-generated enrichment fields to an item and mark it enriched.

    Expected keys in *enrichment*:
      - ``summary_bullets`` (list[str])
      - ``business_angle`` (str)
      - ``interview_nugget`` (str)

    Args:
        table:      Table name (``"articles"`` or ``"vulnerabilities"``).
        item_id:    UUID primary key of the row to update.
        enrichment: Dict containing the enrichment fields.

    Returns:
        ``True`` if the update succeeded, ``False`` otherwise.
    """
    try:
        payload = {
            "summary_bullets": enrichment.get("summary_bullets"),
            "business_angle": enrichment.get("business_angle"),
            "interview_nugget": enrichment.get("interview_nugget"),
            "enriched": True,
            "updated_at": datetime.utcnow().isoformat(),
        }
        _client.table(table).update(payload).eq("id", item_id).execute()
        logger.info("Enriched %s item %s", table, item_id)
        return True
    except Exception:
        logger.exception("Failed to enrich %s item %s", table, item_id)
        return False


# ---------------------------------------------------------------------------
# Embedding Helpers
# ---------------------------------------------------------------------------


def get_unembedded_items(table: str, limit: int = 50) -> list[dict]:
    """
    Fetch items that are enriched but still lack an embedding vector.

    Args:
        table: Table name (``"articles"`` or ``"vulnerabilities"``).
        limit: Maximum number of rows to return.

    Returns:
        List of row dicts, or an empty list on error.
    """
    try:
        response = (
            _client.table(table)
            .select("*")
            .eq("enriched", True)
            .is_("embedding", "null")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        items = response.data or []
        logger.info(
            "Fetched %d unembedded items from %s", len(items), table
        )
        return items
    except Exception:
        logger.exception("Failed to fetch unembedded items from %s", table)
        return []


def update_embedding(
    table: str, item_id: str, embedding: list[float]
) -> bool:
    """
    Store an embedding vector for an item.

    The supabase-py client serialises the list to a JSON array which
    PostgREST casts to ``vector(768)`` on the server side.

    Args:
        table:     Table name (``"articles"`` or ``"vulnerabilities"``).
        item_id:   UUID primary key of the row to update.
        embedding: 768-dimensional float vector.

    Returns:
        ``True`` if the update succeeded, ``False`` otherwise.
    """
    try:
        _client.table(table).update(
            {"embedding": embedding}
        ).eq("id", item_id).execute()
        logger.info("Stored embedding for %s item %s", table, item_id)
        return True
    except Exception:
        logger.exception(
            "Failed to store embedding for %s item %s", table, item_id
        )
        return False


# ---------------------------------------------------------------------------
# Ingestion Log Tracking
# ---------------------------------------------------------------------------


def create_ingestion_log(
    stream: str, source: Optional[str] = None
) -> Optional[str]:
    """
    Create a new ``ingestion_logs`` entry with ``status='running'``.

    Args:
        stream: Ingestion stream (``"news"``, ``"research"``, or
                ``"vulnerabilities"``).
        source: Optional source identifier (e.g. ``"nvd"``, ``"kev"``,
                ``"the_hacker_news"``).

    Returns:
        The UUID of the new log row, or ``None`` on error.
    """
    try:
        payload: dict = {"stream": stream, "status": "running"}
        if source is not None:
            payload["source"] = source

        response = (
            _client.table("ingestion_logs").insert(payload).execute()
        )
        log_id: str = response.data[0]["id"]
        logger.info(
            "Created ingestion log %s (stream=%s, source=%s)",
            log_id,
            stream,
            source,
        )
        return log_id
    except Exception:
        logger.exception(
            "Failed to create ingestion log (stream=%s, source=%s)",
            stream,
            source,
        )
        return None


def complete_ingestion_log(
    log_id: str,
    items_fetched: int = 0,
    items_enriched: int = 0,
    items_embedded: int = 0,
    status: str = "completed",
    errors: Optional[list] = None,
) -> None:
    """
    Finalise an ingestion log entry with completion metrics.

    Args:
        log_id:         UUID of the log row to update.
        items_fetched:  Total items fetched during the run.
        items_enriched: Total items enriched during the run.
        items_embedded: Total items that received embeddings.
        status:         Final status (``"completed"`` or ``"failed"``).
        errors:         Optional list of error details (stored as JSONB).
    """
    try:
        payload: dict = {
            "items_fetched": items_fetched,
            "items_enriched": items_enriched,
            "items_embedded": items_embedded,
            "status": status,
            "completed_at": datetime.utcnow().isoformat(),
        }
        if errors is not None:
            payload["errors"] = errors

        _client.table("ingestion_logs").update(payload).eq(
            "id", log_id
        ).execute()
        logger.info(
            "Completed ingestion log %s — fetched=%d enriched=%d "
            "embedded=%d status=%s",
            log_id,
            items_fetched,
            items_enriched,
            items_embedded,
            status,
        )
    except Exception:
        logger.exception("Failed to complete ingestion log %s", log_id)


def get_last_ingestion_time(
    stream: str, source: Optional[str] = None
) -> Optional[datetime]:
    """
    Get the most recent *completed* ingestion timestamp for a stream.

    Used by incremental ingestors to determine the time window for
    fetching new data (e.g. NVD ``lastModStartDate``).

    Args:
        stream: Ingestion stream name.
        source: Optional source name to narrow the query.

    Returns:
        ``datetime`` of the last successful ``completed_at``, or
        ``None`` if no completed runs exist or on error.
    """
    try:
        query = (
            _client.table("ingestion_logs")
            .select("completed_at")
            .eq("stream", stream)
            .eq("status", "completed")
            .order("completed_at", desc=True)
            .limit(1)
        )
        if source is not None:
            query = query.eq("source", source)

        response = query.execute()

        if not response.data:
            logger.info(
                "No completed ingestion logs for stream=%s source=%s",
                stream,
                source,
            )
            return None

        raw_ts: str = response.data[0]["completed_at"]
        # Parse ISO-8601 timestamp returned by Supabase
        ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        logger.info(
            "Last ingestion for stream=%s source=%s was %s",
            stream,
            source,
            ts.isoformat(),
        )
        return ts
    except Exception:
        logger.exception(
            "Failed to get last ingestion time for stream=%s source=%s",
            stream,
            source,
        )
        return None
