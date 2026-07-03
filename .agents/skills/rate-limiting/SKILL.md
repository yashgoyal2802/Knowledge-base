---
name: rate-limiting
description: API rate-limiting strategies for Gemini, NVD, Supabase, and frontend requests. Covers token bucket, sliding window, connection pooling, and client-side caching patterns.
---

# API Rate-Limiting Strategies

This skill documents the rate-limiting approaches used across the CyberIntel
stack. Every external API we depend on has free-tier limits that will hard-block
us if exceeded.

---

## 1. Gemini API (google-generativeai)

**Limits (gemini-2.0-flash free tier):**
| Metric | Limit |
|--------|-------|
| RPM    | 15 requests/minute |
| RPD    | 1,500 requests/day |
| TPM    | 1,000,000 tokens/minute |

### Strategy: Token Bucket with Daily Cap

```python
import time, asyncio

class GeminiRateLimiter:
    """
    Token-bucket rate limiter.
    - Bucket refills at 1 token every 4 seconds (= 15/min).
    - Daily counter hard-stops at 1,500 requests.
    """
    def __init__(self, rpm=15, rpd=1500):
        self.rpm = rpm
        self.rpd = rpd
        self._timestamps: list[float] = []
        self._day_count = 0
        self._day_start = time.time()

    async def acquire(self):
        now = time.time()
        # Reset daily counter
        if now - self._day_start > 86400:
            self._day_count = 0
            self._day_start = now
        # Hard stop on daily limit
        if self._day_count >= self.rpd:
            raise RuntimeError("Daily Gemini limit reached (1,500 RPD)")
        # Sliding-window minute check
        self._timestamps = [t for t in self._timestamps if now - t < 60]
        if len(self._timestamps) >= self.rpm:
            wait = 60 - (now - self._timestamps[0]) + 0.1
            await asyncio.sleep(max(wait, 0))
        self._timestamps.append(time.time())
        self._day_count += 1
```

### Usage Budget

| Use Case | Calls/Day | Notes |
|----------|-----------|-------|
| Ingestion enrichment | ~60-100 | 1 call per article (structured JSON output) |
| Ingestion embeddings | ~60-100 | 1 call per article |
| User RAG queries | ~1,300 remaining | ~0.9 queries/minute sustained |

### Tips
- **Batch the enrichment prompt**: Send title + content in one call, ask for
  summary + business angle + interview nugget as a single JSON response.
- **Cache RAG responses**: Store query→response pairs in Supabase for repeat
  questions (exact match + semantic similarity dedup).
- **Use `gemini-2.0-flash-lite`** for embeddings if available (30 RPM, lighter).

---

## 2. NVD API v2

**Limits:**
| Config | Rate Limit |
|--------|-----------|
| No API key | 5 requests / 30 seconds |
| With API key | 50 requests / 30 seconds |

### Strategy: Sliding Window with Sleep

```python
import time

NVD_WINDOW = 30        # seconds
NVD_MAX_REQUESTS = 50  # with API key

class NVDRateLimiter:
    def __init__(self, max_requests=NVD_MAX_REQUESTS, window=NVD_WINDOW):
        self.max_requests = max_requests
        self.window = window
        self._timestamps: list[float] = []

    def wait_if_needed(self):
        now = time.time()
        self._timestamps = [t for t in self._timestamps if now - t < self.window]
        if len(self._timestamps) >= self.max_requests:
            sleep_time = self.window - (now - self._timestamps[0]) + 0.5
            time.sleep(max(sleep_time, 0))
        self._timestamps.append(time.time())
```

### Tips
- Always use `lastModStartDate` to fetch only changes since last run.
- Store last successful run timestamp in `ingestion_logs`.
- Max date range = 120 days; paginate with `startIndex`.

---

## 3. Supabase (PostgreSQL)

**Free-tier connection limits:**
| Type | Limit |
|------|-------|
| Direct connections | 60 |
| Pooled (Supavisor) | 200 |

### Strategy: Connection Pooling + Single Client

- **Always** use the pooled connection string (`port 6543`) for ingestion scripts.
- Use a **singleton** Supabase client instance — don't create new clients per request.
- For Vercel serverless: each function invocation gets its own client, but Supavisor
  handles the pooling server-side. No action needed.
- For GitHub Actions: create one `asyncpg` pool at script start, reuse across all operations.

```python
import asyncpg

# One pool per ingestion run
pool = await asyncpg.create_pool(
    DATABASE_URL,
    min_size=2,
    max_size=5,   # Keep low — we only need a few connections
    command_timeout=30,
)
```

---

## 4. RSS Feeds

**No formal rate limits**, but best practices:
- Respect `robots.txt` and set a proper `User-Agent` header.
- Don't poll more than once per hour (we poll every 6 hours).
- Use `If-Modified-Since` / `ETag` headers where supported.
- Timeout after 30 seconds per feed.
- If a feed fails, log the error and continue to the next feed.

---

## 5. Frontend — Client-Side Rate Limiting

### Debounce Search Input
```javascript
// Debounce user search queries to avoid spamming the API
const DEBOUNCE_MS = 400;
let timer;
function onSearchInput(query) {
    clearTimeout(timer);
    timer = setTimeout(() => fetchResults(query), DEBOUNCE_MS);
}
```

### Cache RAG Responses
- Store `{ query_hash → response }` in `sessionStorage`.
- Before hitting `/api/chat`, check if an identical query was asked in this session.
- TTL: session lifetime (cleared on tab close).

### Exponential Backoff on 429
```javascript
async function fetchWithRetry(url, options, maxRetries = 3) {
    for (let i = 0; i < maxRetries; i++) {
        const res = await fetch(url, options);
        if (res.status !== 429) return res;
        const wait = Math.pow(2, i) * 1000 + Math.random() * 500;
        await new Promise(r => setTimeout(r, wait));
    }
    throw new Error("Rate limited after retries");
}
```

---

## Summary

| Service | Limiter Type | Key Constant | Where Enforced |
|---------|-------------|--------------|----------------|
| Gemini | Token bucket + daily cap | 15 RPM / 1,500 RPD | `shared/gemini_client.py` |
| NVD | Sliding window | 50 req/30s | `ingestion/nvd_ingest.py` |
| Supabase | Connection pool | 5 connections | `shared/supabase_client.py` |
| RSS feeds | Cron interval | 6 hours | GitHub Actions |
| Frontend | Debounce + cache | 400ms / session | React hooks |
