"""
RAG Pipeline for CyberIntel.

Combines pgvector similarity search in Supabase with Gemini 2.0 Flash
streaming text generation to answer cybersecurity queries with citations.

Provides:
  - search_similar_items(query, limit) -> retrieves relevant articles & CVEs
  - stream_rag_chat(query) -> SSE async generator yielding token, source, and done events
"""

from __future__ import annotations

import json
import logging
from typing import AsyncGenerator

from shared.gemini_client import generate_query_embedding, generate_text_stream
from shared.supabase_client import get_db_connection, get_supabase_client

logger = logging.getLogger("shared.rag")


async def search_similar_items(query: str, limit: int = 5) -> list[dict]:
    """
    Search for articles and vulnerabilities semantically similar to the query.

    Uses Gemini text-embedding-004 to vectorize the query, then queries
    Supabase via asyncpg (pgvector cosine distance `<=>`). Falls back to
    standard PostgREST queries if the direct SQL connection fails.
    """
    try:
        embedding = await generate_query_embedding(query)
    except Exception as exc:
        logger.warning("Failed to generate query embedding (%s), using fallback search", exc)
        return _fallback_search(limit)

    try:
        conn = await get_db_connection()
        try:
            # Format embedding list to Postgres vector string representation
            emb_str = f"[{','.join(str(f) for f in embedding)}]"
            sql = """
            WITH combined AS (
                SELECT id, title, url, summary_bullets, business_angle, 'article' as item_type,
                       1 - (embedding <=> $1::vector) as similarity
                FROM articles
                WHERE embedding IS NOT NULL
                UNION ALL
                SELECT id, COALESCE(cve_id || ': ' || description, cve_id) as title, 
                       'https://nvd.nist.gov/vuln/detail/' || cve_id as url, 
                       summary_bullets, business_angle, 'vulnerability' as item_type,
                       1 - (embedding <=> $1::vector) as similarity
                FROM vulnerabilities
                WHERE embedding IS NOT NULL
            )
            SELECT * FROM combined
            ORDER BY similarity DESC
            LIMIT $2;
            """
            rows = await conn.fetch(sql, emb_str, limit)
            results = []
            for r in rows:
                results.append({
                    "id": str(r["id"]),
                    "title": r["title"],
                    "url": r["url"],
                    "summary_bullets": r["summary_bullets"] or [],
                    "business_angle": r["business_angle"],
                    "item_type": r["item_type"],
                    "similarity": round(float(r["similarity"]), 4) if r["similarity"] is not None else 0.0,
                })
            return results
        finally:
            await conn.close()
    except Exception as exc:
        logger.warning("Direct pgvector search failed (%s), falling back to REST query", exc)
        return _fallback_search(limit)


def _fallback_search(limit: int = 5) -> list[dict]:
    """Fallback search using standard PostgREST when direct pgvector is unavailable."""
    try:
        client = get_supabase_client(use_service_key=False)
        articles_res = (
            client.table("articles")
            .select("id, title, url, summary_bullets, business_angle")
            .order("created_at", desc=True)
            .limit(max(1, limit // 2))
            .execute()
        )
        vulns_res = (
            client.table("vulnerabilities")
            .select("id, cve_id, description, summary_bullets, business_angle")
            .order("published_at", desc=True)
            .limit(max(1, limit - (limit // 2)))
            .execute()
        )

        results = []
        for a in (articles_res.data or []):
            results.append({
                "id": str(a["id"]),
                "title": a.get("title", ""),
                "url": a.get("url", ""),
                "summary_bullets": a.get("summary_bullets") or [],
                "business_angle": a.get("business_angle"),
                "item_type": "article",
                "similarity": 0.5000,
            })
        for v in (vulns_res.data or []):
            cve_id = v.get("cve_id", "")
            desc = v.get("description", "")
            results.append({
                "id": str(v["id"]),
                "title": f"{cve_id}: {desc}" if desc else cve_id,
                "url": f"https://nvd.nist.gov/vuln/detail/{cve_id}",
                "summary_bullets": v.get("summary_bullets") or [],
                "business_angle": v.get("business_angle"),
                "item_type": "vulnerability",
                "similarity": 0.5000,
            })
        return results[:limit]
    except Exception as exc:
        logger.error("Fallback search also failed: %s", exc)
        return []


async def stream_rag_chat(query: str) -> AsyncGenerator[str, None]:
    """
    Stream RAG response via Server-Sent Events (SSE).

    Yields JSON strings formatted as SSE events (`data: <json>\\n\\n`):
      1. 'token' chunks as Gemini generates the answer
      2. 'source' event with the retrieved intelligence items
      3. 'done' event signaling completion
    """
    sources = await search_similar_items(query, limit=5)

    system_instruction = (
        "You are CyberIntel AI, an expert cybersecurity intelligence analyst. "
        "Answer the user's query clearly, professionally, and accurately using the provided "
        "threat intelligence context (recent news articles and vulnerability records). "
        "If the context contains relevant CVEs or articles, cite them in your response. "
        "If the provided context does not fully answer the question, supplement with your expert "
        "knowledge but clarify what is from the recent intelligence feeds vs general knowledge."
    )

    context_str = ""
    for i, src in enumerate(sources, 1):
        context_str += f"\n[{i}] {src['item_type'].upper()}: {src['title']} ({src['url']})\n"
        if src.get("summary_bullets"):
            context_str += f"    Summary: {' '.join(src['summary_bullets'])}\n"
        if src.get("business_angle"):
            context_str += f"    Business Impact: {src['business_angle']}\n"

    prompt = f"Threat Intelligence Context:\n{context_str}\n\nUser Query: {query}\n\nAnalyst Assessment:"

    try:
        async for chunk in generate_text_stream(prompt, system_instruction=system_instruction):
            yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"

        yield f"data: {json.dumps({'type': 'source', 'sources': sources})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
    except Exception as exc:
        logger.exception("Error during RAG text generation stream")
        yield f"data: {json.dumps({'type': 'error', 'content': 'Failed to generate AI response.'})}\n\n"
