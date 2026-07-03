"""
Supabase connection factory.

Provides two connection modes:
  1. supabase-py client — for PostgREST CRUD operations (insert, select, update)
  2. asyncpg connection — for direct SQL queries (pgvector similarity search)

All credentials are read from environment variables.
"""

import os
from typing import Optional

from supabase import create_client, Client


# ---------------------------------------------------------------------------
# Credentials — set these in your environment or .env file
# ---------------------------------------------------------------------------

# TODO: Replace these placeholder values with your real Supabase credentials.
#       For local dev, use a .env file loaded by python-dotenv.
#       For Vercel, set them in the dashboard under Settings → Environment Variables.
#       For GitHub Actions, set them as repository secrets.

SUPABASE_URL: str = os.getenv(
    "SUPABASE_URL",
    "https://your-project-ref.supabase.co",  # TODO: your Supabase project URL
)
SUPABASE_PUBLISHABLE_KEY: str = os.getenv(
    "SUPABASE_PUBLISHABLE_KEY",
    "eyJ-your-publishable-key-here",  # TODO: your Supabase publishable (public) key
)
SUPABASE_SECRET_KEY: str = os.getenv(
    "SUPABASE_SECRET_KEY",
    "eyJ-your-secret-key-here",  # TODO: your Supabase secret (service-role) key
)

# Pooled connection string (Supavisor, port 6543) — needed for asyncpg / pgvector
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres.your-project-ref:your-password@aws-0-region.pooler.supabase.com:6543/postgres",
    # TODO: your Supabase pooled connection string (Settings → Database → Connection string → URI → "Mode: Transaction")
)


# ---------------------------------------------------------------------------
# Supabase PostgREST Client (singleton)
# ---------------------------------------------------------------------------

_client_cache: dict[str, Client] = {}


def get_supabase_client(use_service_key: bool = False) -> Client:
    """
    Get or create a Supabase client instance.

    Args:
        use_service_key: If True, use the service-role key (bypasses RLS).
                         Use this for backend/ingestion operations only.
                         If False, use the anon key (respects RLS).
    """
    cache_key = "service" if use_service_key else "anon"

    if cache_key not in _client_cache:
        key = SUPABASE_SECRET_KEY if use_service_key else SUPABASE_PUBLISHABLE_KEY
        _client_cache[cache_key] = create_client(SUPABASE_URL, key)

    return _client_cache[cache_key]


# ---------------------------------------------------------------------------
# Direct SQL Connection (asyncpg) — for pgvector queries
# ---------------------------------------------------------------------------

async def get_db_connection():
    """
    Create a single asyncpg connection for direct SQL queries.

    Use this for:
      - pgvector similarity searches (SELECT ... ORDER BY embedding <=> $1)
      - Batch inserts with ON CONFLICT
      - Any query that the PostgREST client can't express

    Remember to close the connection when done:
        conn = await get_db_connection()
        try:
            result = await conn.fetch("SELECT ...")
        finally:
            await conn.close()
    """
    import asyncpg
    return await asyncpg.connect(DATABASE_URL)


async def get_db_pool(min_size: int = 2, max_size: int = 5):
    """
    Create an asyncpg connection pool (for ingestion scripts that
    need multiple concurrent connections).

    Usage:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            await conn.fetch("SELECT ...")
        await pool.close()
    """
    import asyncpg
    return await asyncpg.create_pool(
        DATABASE_URL,
        min_size=min_size,
        max_size=max_size,
        command_timeout=30,
    )
