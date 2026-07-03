"""
Gemini API REST client with built-in rate limiting.

Uses standard HTTP requests via httpx instead of heavy SDKs (grpcio/protobuf)
to ensure the Vercel serverless function bundle stays under ~95 MB (well below
Vercel's 225 MB Lambda limit).

Enforces free-tier limits:
  - 15 requests per minute  (RPM)
  - 1,500 requests per day  (RPD)

Provides:
  - generate_text()          — full response
  - generate_text_stream()   — async generator (for RAG SSE)
  - generate_embedding()     — single text → 768-dim vector
  - generate_query_embedding() — retrieval query vector
  - generate_embeddings_batch() — batch embeddings with rate limiting
"""

import asyncio
import json
import logging
import os
import time
from typing import Any, AsyncGenerator, Optional

import httpx

logger = logging.getLogger("shared.gemini_client")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GEMINI_API_KEY: str = os.getenv(
    "GEMINI_API_KEY",
    "your-gemini-api-key-here",  # TODO: replace with your real API key
)

GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "models/text-embedding-004")
EMBEDDING_DIMENSIONS: int = 768

BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """
    Token-bucket rate limiter for Gemini's free tier.
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


_rate_limiter = RateLimiter()


# ---------------------------------------------------------------------------
# Text Generation
# ---------------------------------------------------------------------------

async def generate_text(
    prompt: str,
    system_instruction: Optional[str] = None,
) -> str:
    """
    Generate a full text response (blocking until complete) via REST API.
    """
    await _rate_limiter.acquire()

    url = f"{BASE_URL}/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    payload: dict[str, Any] = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    if system_instruction:
        payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        return parts[0].get("text", "") if parts else ""


async def generate_text_stream(
    prompt: str,
    system_instruction: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    Stream text generation — yields chunks as Server-Sent Events arrive.
    """
    await _rate_limiter.acquire()

    url = f"{BASE_URL}/models/{GEMINI_MODEL}:streamGenerateContent?alt=sse&key={GEMINI_API_KEY}"
    payload: dict[str, Any] = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    if system_instruction:
        payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

    async with httpx.AsyncClient() as client:
        async with client.stream("POST", url, json=payload, timeout=60.0) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:].strip()
                    if not data_str or data_str == "[DONE]":
                        continue
                    try:
                        chunk = json.loads(data_str)
                        candidates = chunk.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts and "text" in parts[0]:
                                yield parts[0]["text"]
                    except Exception:
                        pass


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------

async def _embed_content(text: str, task_type: Optional[str] = None) -> list[float]:
    await _rate_limiter.acquire()

    model_name = EMBEDDING_MODEL if EMBEDDING_MODEL.startswith("models/") else f"models/{EMBEDDING_MODEL}"
    url = f"{BASE_URL}/{model_name}:embedContent?key={GEMINI_API_KEY}"
    
    payload: dict[str, Any] = {
        "model": model_name,
        "content": {"parts": [{"text": text}]},
        "outputDimensionality": EMBEDDING_DIMENSIONS,
    }
    if task_type:
        payload["taskType"] = task_type

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
        return data.get("embedding", {}).get("values", [])


async def generate_embedding(text: str) -> list[float]:
    """Generate a single vector embedding (768 dimensions)."""
    return await _embed_content(text, task_type="RETRIEVAL_DOCUMENT")


async def generate_query_embedding(text: str) -> list[float]:
    """Generate an embedding optimized for search queries."""
    return await _embed_content(text, task_type="RETRIEVAL_QUERY")


async def generate_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a batch of texts sequentially."""
    embeddings = []
    for text in texts:
        emb = await generate_embedding(text)
        embeddings.append(emb)
    return embeddings
