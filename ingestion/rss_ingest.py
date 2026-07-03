"""
RSS / Atom feed ingestion for CyberIntel.

Fetches articles from NEWS_FEEDS or RESEARCH_FEEDS (configurable via
``--stream``), normalises each entry into the ``articles`` table schema,
and batch-upserts them through :func:`ingestion.db.upsert_articles`.

Usage::

    python -m ingestion.rss_ingest --stream news
    python -m ingestion.rss_ingest --stream research
"""

from __future__ import annotations

import argparse
import logging
import time
from calendar import timegm
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv

# Load .env before any config imports (local development)
load_dotenv()

import feedparser  # noqa: E402
import httpx  # noqa: E402
from bs4 import BeautifulSoup  # noqa: E402

from ingestion.config import (  # noqa: E402
    MAX_ARTICLES_PER_SOURCE,
    NEWS_FEEDS,
    REQUEST_TIMEOUT,
    RESEARCH_FEEDS,
    USER_AGENT,
)
from ingestion.db import (  # noqa: E402
    complete_ingestion_log,
    create_ingestion_log,
    upsert_articles,
)

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def clean_html(html: str | None) -> str:
    """Strip HTML tags and collapse whitespace, returning plain text.

    Args:
        html: Raw HTML string (may be ``None``).

    Returns:
        Cleaned plain-text string, or an empty string when *html* is falsy.
    """
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text(separator=" ", strip=True)


def parse_date(entry: dict[str, Any]) -> datetime | None:
    """Extract a timezone-aware UTC datetime from a feedparser entry.

    Tries ``published_parsed`` first, then falls back to
    ``updated_parsed``.  Both are :class:`time.struct_time` objects
    produced by :mod:`feedparser`.

    Args:
        entry: A single feedparser entry dict.

    Returns:
        A :class:`~datetime.datetime` in UTC, or ``None`` if neither
        field is available.
    """
    for field in ("published_parsed", "updated_parsed"):
        struct: time.struct_time | None = entry.get(field)
        if struct is not None:
            try:
                # timegm interprets struct_time as UTC and returns a POSIX ts
                ts = timegm(struct)
                return datetime.fromtimestamp(ts, tz=timezone.utc)
            except (ValueError, OverflowError, OSError):
                continue
    return None


def _extract_raw_content(entry: dict[str, Any]) -> str:
    """Pull the richest content field available from a feed entry.

    Preference order:
        1. ``entry.content[0].value`` (Atom full-content)
        2. ``entry.summary``           (RSS description / summary)
        3. ``entry.description``       (legacy RSS)

    The result is run through :func:`clean_html` to strip markup.
    """
    raw: str | None = None

    # 1. Atom <content> element — list of dicts with 'value' key
    content_list: list[dict[str, Any]] | None = getattr(entry, "content", None) or entry.get("content")
    if content_list and isinstance(content_list, list) and len(content_list) > 0:
        raw = content_list[0].get("value")

    # 2. RSS <description> exposed as .summary by feedparser
    if not raw:
        raw = entry.get("summary")

    # 3. Explicit .description (rare, but some feeds expose it)
    if not raw:
        raw = entry.get("description")

    return clean_html(raw)


def _extract_tags(entry: dict[str, Any]) -> list[str]:
    """Return a list of tag terms attached to the feed entry."""
    tags_raw: list[dict[str, Any]] = entry.get("tags", [])
    return [
        tag["term"]
        for tag in tags_raw
        if isinstance(tag, dict) and tag.get("term")
    ]


def _parse_entry(
    entry: dict[str, Any],
    source_key: str,
    stream: str,
) -> dict[str, Any] | None:
    """Convert a single feedparser entry into an ``articles``-table row dict.

    Returns ``None`` when a required field (title, url) is missing so the
    caller can skip the entry gracefully.
    """
    title: str | None = entry.get("title")
    url: str | None = entry.get("link")

    if not title or not url:
        logger.debug("Skipping entry without title/url in source '%s'", source_key)
        return None

    return {
        "source": source_key,
        "stream": stream,
        "title": title.strip(),
        "url": url.strip(),
        "author": entry.get("author") or None,
        "published_at": parse_date(entry),
        "raw_content": _extract_raw_content(entry),
        "tags": _extract_tags(entry),
    }


# ---------------------------------------------------------------------------
# Per-feed processing
# ---------------------------------------------------------------------------


def _fetch_feed(url: str) -> str:
    """Download a feed URL and return the response body as text.

    Uses :mod:`httpx` so we can set a custom ``User-Agent`` header;
    :mod:`feedparser` alone does not expose request-level headers
    reliably.

    Raises:
        httpx.HTTPStatusError: On 4xx / 5xx responses.
        httpx.TransportError: On network-level failures.
    """
    headers = {"User-Agent": USER_AGENT}
    with httpx.Client(timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
        response = client.get(url, headers=headers)
        response.raise_for_status()
    return response.text


def process_feed(source_key: str, feed_cfg: dict[str, Any], stream: str) -> int:
    """Fetch, parse, and upsert a single RSS/Atom feed.

    Args:
        source_key: Short identifier (e.g. ``"the_hacker_news"``).
        feed_cfg: Dict from :data:`ingestion.config.NEWS_FEEDS` /
            :data:`RESEARCH_FEEDS` containing at least ``url`` and
            ``stream``.
        stream: ``"news"`` or ``"research"``.

    Returns:
        Number of articles successfully upserted for this feed.
    """
    url: str = feed_cfg["url"]
    log_id = create_ingestion_log(stream=stream, source=source_key)
    items_fetched = 0
    errors: list[str] = []

    try:
        logger.info("Fetching feed: %s (%s)", source_key, url)
        raw_xml = _fetch_feed(url)

        parsed = feedparser.parse(raw_xml)
        if parsed.bozo and not parsed.entries:
            # Feed was completely unparseable
            raise ValueError(
                f"feedparser could not parse {url}: {parsed.bozo_exception}"
            )

        articles: list[dict[str, Any]] = []
        for idx, entry in enumerate(parsed.entries):
            if idx >= MAX_ARTICLES_PER_SOURCE:
                break

            try:
                row = _parse_entry(entry, source_key, stream)
                if row is not None:
                    articles.append(row)
            except Exception:
                logger.warning(
                    "Failed to parse entry #%d in '%s' — skipping",
                    idx,
                    source_key,
                    exc_info=True,
                )
                errors.append(f"entry#{idx}")

        if articles:
            upsert_articles(articles)

        items_fetched = len(articles)
        logger.info(
            "Source '%s': %d articles upserted (%d skipped/errored)",
            source_key,
            items_fetched,
            len(parsed.entries[:MAX_ARTICLES_PER_SOURCE]) - items_fetched,
        )

    except Exception as exc:
        logger.error(
            "Feed '%s' failed: %s",
            source_key,
            exc,
            exc_info=True,
        )
        errors.append(str(exc))
        complete_ingestion_log(
            log_id,
            items_fetched=items_fetched,
            items_enriched=0,
            items_embedded=0,
            errors=errors,
            status="failed",
        )
        return 0

    complete_ingestion_log(
        log_id,
        items_fetched=items_fetched,
        items_enriched=0,  # enrichment runs as a separate pipeline stage
        items_embedded=0,
        errors=errors or None,
        status="completed",
    )
    return items_fetched


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entrypoint — parse ``--stream`` and run the ingestion loop."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    )

    parser = argparse.ArgumentParser(
        description="Ingest cybersecurity articles from RSS / Atom feeds.",
    )
    parser.add_argument(
        "--stream",
        required=True,
        choices=("news", "research"),
        help="Which feed group to ingest: 'news' or 'research'.",
    )
    args = parser.parse_args()
    stream: str = args.stream

    # Select the right feed registry
    feeds: dict[str, dict[str, Any]] = (
        NEWS_FEEDS if stream == "news" else RESEARCH_FEEDS
    )

    logger.info(
        "Starting RSS ingestion — stream=%s, sources=%d",
        stream,
        len(feeds),
    )

    total_articles = 0

    for source_key, feed_cfg in feeds.items():
        count = process_feed(source_key, feed_cfg, stream)
        total_articles += count

    logger.info(
        "RSS ingestion complete — stream=%s, total_articles=%d",
        stream,
        total_articles,
    )


if __name__ == "__main__":
    main()
