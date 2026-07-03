# CyberIntel — Workspace Rules

> This file defines the core architecture, database schema, and coding
> conventions for the Cybersecurity Knowledge Repository.

---

## Project Overview

**CyberIntel** is a full-stack cybersecurity intelligence aggregator that:
- Ingests vulnerabilities (NVD, CISA KEV), news (9 sources), and research (3 sources)
- Enriches every item with AI-generated summaries via Gemini 2.0 Flash
- Stores content + vector embeddings in Supabase (PostgreSQL + pgvector)
- Serves a React dashboard with streaming RAG chat (SSE)

### Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌──────────────────┐
│  React (Vite)   │────▶│ FastAPI on   │────▶│ Supabase         │
│  Vercel Static  │ SSE │ Vercel       │ SQL │ PostgreSQL +     │
│                 │◀────│ Serverless   │◀────│ pgvector         │
└─────────────────┘     └──────┬───────┘     └────────▲─────────┘
                               │                      │
                        Gemini 2.0 Flash         Ingestion
                        (RAG queries)            Pipeline
                                                      │
                                              ┌───────┴────────┐
                                              │ GitHub Actions  │
                                              │ Cron (6h)       │
                                              │ NVD + KEV + RSS │
                                              │ + Gemini Enrich │
                                              └────────────────┘
```

### Tech Stack
| Layer       | Technology                    | Deployed On     |
|-------------|-------------------------------|-----------------|
| Frontend    | React + Vite                  | Vercel (static) |
| API         | FastAPI + Pydantic V2         | Vercel (Python) |
| Database    | PostgreSQL + pgvector         | Supabase        |
| AI          | Gemini 2.0 Flash              | Google AI API   |
| Ingestion   | Python scripts                | GitHub Actions  |
| Auth        | OAuth2 + JWT + bcrypt         | —               |

---

## Database Schema (Supabase)

### Enable Extensions
```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

### `articles` — News & Research content
```sql
CREATE TABLE articles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source          VARCHAR(100) NOT NULL,
    stream          VARCHAR(20)  NOT NULL,       -- 'news' | 'research'
    title           TEXT         NOT NULL,
    url             TEXT         UNIQUE NOT NULL,
    author          VARCHAR(255),
    published_at    TIMESTAMPTZ,
    raw_content     TEXT,
    summary_bullets TEXT[],                       -- 3-bullet AI summary
    business_angle  TEXT,                         -- AI business insight
    interview_nugget TEXT,                        -- AI interview talking point
    tags            TEXT[],
    embedding       VECTOR(768),                 -- Gemini text-embedding-004
    enriched        BOOLEAN      DEFAULT FALSE,
    created_at      TIMESTAMPTZ  DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  DEFAULT NOW()
);
```

### `vulnerabilities` — NVD CVEs + CISA KEV
```sql
CREATE TABLE vulnerabilities (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cve_id               VARCHAR(20)  UNIQUE NOT NULL,
    source               VARCHAR(20)  NOT NULL,    -- 'nvd' | 'kev'
    description          TEXT,
    cvss_v3_score        DECIMAL(3,1),
    cvss_v3_vector       VARCHAR(100),
    severity             VARCHAR(20),              -- CRITICAL|HIGH|MEDIUM|LOW
    cwe_ids              TEXT[],
    affected_products    JSONB,
    reference_urls       JSONB,
    kev_known_ransomware BOOLEAN,
    kev_due_date         DATE,
    summary_bullets      TEXT[],
    business_angle       TEXT,
    interview_nugget     TEXT,
    embedding            VECTOR(768),
    enriched             BOOLEAN      DEFAULT FALSE,
    published_at         TIMESTAMPTZ,
    last_modified        TIMESTAMPTZ,
    created_at           TIMESTAMPTZ  DEFAULT NOW()
);
```

### `users` — Authentication
```sql
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    hashed_password TEXT         NOT NULL,
    full_name       VARCHAR(255),
    is_active       BOOLEAN      DEFAULT TRUE,
    created_at      TIMESTAMPTZ  DEFAULT NOW()
);
```

### `ingestion_logs` — Pipeline run tracking
```sql
CREATE TABLE ingestion_logs (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stream         VARCHAR(20)  NOT NULL,
    source         VARCHAR(100),
    started_at     TIMESTAMPTZ  DEFAULT NOW(),
    completed_at   TIMESTAMPTZ,
    items_fetched  INTEGER      DEFAULT 0,
    items_enriched INTEGER      DEFAULT 0,
    items_embedded INTEGER      DEFAULT 0,
    errors         JSONB,
    status         VARCHAR(20)  DEFAULT 'running'  -- running|completed|failed
);
```

### Indexes
```sql
-- Query indexes
CREATE INDEX idx_articles_source    ON articles(source);
CREATE INDEX idx_articles_stream    ON articles(stream);
CREATE INDEX idx_articles_published ON articles(published_at DESC);
CREATE INDEX idx_articles_enriched  ON articles(enriched) WHERE NOT enriched;
CREATE INDEX idx_vulns_severity     ON vulnerabilities(severity);
CREATE INDEX idx_vulns_cvss         ON vulnerabilities(cvss_v3_score DESC);
CREATE INDEX idx_vulns_published    ON vulnerabilities(published_at DESC);

-- Vector similarity (IVFFlat — lower storage than HNSW, fine for <100K rows)
CREATE INDEX idx_articles_embedding ON articles
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_vulns_embedding ON vulnerabilities
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);
```

### Storage Budget (500 MB free tier)
| Table           | ~Records/Year | ~Size   |
|-----------------|---------------|---------|
| articles        | 15,000        | 60 MB   |
| vulnerabilities | 25,000        | 100 MB  |
| IVFFlat indexes | —             | 30 MB   |
| Other tables    | —             | 5 MB    |
| **Year 1 total**| —             | **~195 MB** |

---

## Coding Conventions

- **Python**: 3.11+, type hints everywhere, `async def` for I/O
- **Models**: Pydantic V2 (`BaseModel` with `model_config = ConfigDict(...)`)
- **Imports**: stdlib → third-party → local, separated by blank lines
- **API routes**: Defined directly in endpoint files — **no APIRouter layer**
- **Env vars**: Always read via `os.getenv()` with safe defaults
- **Error handling**: Return proper HTTP status codes, never expose stack traces
- **Comments**: Preserve all existing comments when editing files

## Environment Variables

| Variable                     | Required | Description                          |
|------------------------------|----------|--------------------------------------|
| `SUPABASE_URL`               | Yes      | Supabase project URL                 |
| `SUPABASE_PUBLISHABLE_KEY`   | Yes      | Supabase publishable key (frontend)  |
| `SUPABASE_SECRET_KEY`        | Yes      | Supabase secret key (backend)        |
| `DATABASE_URL`               | Yes      | Supabase pooled connection string    |
| `GEMINI_API_KEY`             | Yes      | Google AI API key                    |
| `NVD_API_KEY`                | No       | NVD API key (50 vs 5 req/30s)        |
| `JWT_SECRET_KEY`             | Yes      | Secret for signing JWTs              |
| `FRONTEND_URL`               | Yes      | Vercel frontend URL (for CORS)       |
| `ACCESS_TOKEN_EXPIRE_MINUTES`| No       | JWT expiry (default: 60)             |
