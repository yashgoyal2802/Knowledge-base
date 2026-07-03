"""
Gemini API wrapper with built-in rate limiting.

Wraps the google-generativeai SDK and enforces free-tier limits:
  - 15 requests per minute  (RPM)
  - 1,500 requests per day  (RPD)
  - 1,000,000 tokens per minute (TPM) — not enforced here (hard to predict)

Provides:
  - generate_text()          — full response (for enrichment)
  - generate_text_stream()   — async generator (for RAG SSE)
  - generate_embedding()     — single text → 768-dim vector
  - generate_embeddings_batch() — batch embeddings with rate limiting
"""

import asyncio
import os
import time
from typing import AsyncGenerator

import google.generativeai as genai


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# TODO: Set your Gemini API key in the environment.
#       Get one free at https://aistudio.google.com/apikey
GEMINI_API_KEY: str = os.getenv(
    "GEMINI_API_KEY",
    "your-gemini-api-key-here",  # TODO: replace with your real API key
)

GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "models/text-embedding-004")
EMBEDDING_DIMENSIONS: int = 768

# Initialize the SDK
genai.configure(api_key=GEMINI_API_KEY)


# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """
    Token-bucket rate limiter for Gemini's free tier.

    - Tracks a sliding 60-second window for RPM enforcement.
    - Tracks a rolling 24-hour counter for RPD enforcement.
    - Blocks (async sleep) when the minute bucket is full.
    - Raises RuntimeError when the daily cap is hit.
    """

    def __init__(self, rpm: int = 15, rpd: int = 1500):
        self.rpm = rpm
        self.rpd = rpd
        self._minute_timestamps: list[float] = []
        self._day_count: int = 0
        self._day_start: float = time.time()

    async def acquire(self):
        """Wait until a request slot is available, then consume one."""
        now = time.time()

        # Reset daily counter every 24 hours
        if now - self._day_start > 86_400:
            self._day_count = 0
            self._day_start = now

        # Hard-stop on daily limit
        if self._day_count >= self.rpd:
            raise RuntimeError(
                f"Gemini daily request limit ({self.rpd} RPD) reached. "
                "Resets at midnight Pacific Time."
            )

        # Sliding-window minute check
        self._minute_timestamps = [
            t for t in self._minute_timestamps if now - t < 60
        ]

        if len(self._minute_timestamps) >= self.rpm:
            wait_time = 60 - (now - self._minute_timestamps[0]) + 0.1
            if wait_time > 0:
                await asyncio.sleep(wait_time)

        self._minute_timestamps.append(time.time())
        self._day_count += 1


# Module-level singleton
_rate_limiter = RateLimiter()


# ---------------------------------------------------------------------------
# Text Generation
# ---------------------------------------------------------------------------

async def generate_text(
    prompt: str,
    system_instruction: str | None = None,
) -> str:
    """
    Generate a full text response (blocking until complete).

    Use for enrichment tasks where you need the entire response at once.
    """
    await _rate_limiter.acquire()

    model = genai.GenerativeModel(
        GEMINI_MODEL,
        system_instruction=system_instruction,
    )
    response = model.generate_content(prompt)
    return response.text


async def generate_text_stream(
    prompt: str,
    system_instruction: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    Stream text generation — yields chunks as they arrive.

    Use for the RAG chat endpoint (SSE streaming to the frontend).
    """
    await _rate_limiter.acquire()

    model = genai.GenerativeModel(
        GEMINI_MODEL,
        system_instruction=system_instruction,
    )
    response = model.generate_content(prompt, stream=True)

    for chunk in response:
        if chunk.text:
            yield chunk.text


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------

async def generate_embedding(text: str) -> list[float]:
    """Generate a single vector embedding (768 dimensions)."""
    await _rate_limiter.acquire()

    result = genai.embed_content(
        model=EMBEDDING_MODEL,
        content=text,
        task_type="retrieval_document",
        output_dimensionality=EMBEDDING_DIMENSIONS,
    )
    return result["embedding"]


async def generate_query_embedding(text: str) -> list[float]:
    """
    Generate an embedding optimized for search queries.

    Uses task_type="retrieval_query" which produces embeddings
    better suited for matching against document embeddings.
    """
    await _rate_limiter.acquire()

    result = genai.embed_content(
        model=EMBEDDING_MODEL,
        content=text,
        task_type="retrieval_query",
        output_dimensionality=EMBEDDING_DIMENSIONS,
    )
    return result["embedding"]


async def generate_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """
    Generate embeddings for a batch of texts.

    Processes sequentially with rate limiting between each call.
    """
    embeddings = []
    for text in texts:
        emb = await generate_embedding(text)
        embeddings.append(emb)
    return embeddings
