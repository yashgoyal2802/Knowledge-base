# CyberIntel — Cybersecurity Knowledge Repository

A full-stack intelligence aggregator that collects cybersecurity news, vulnerabilities, and research from 15+ sources, enriches each item with AI-generated insights, and serves it through a React dashboard with streaming RAG chat.

---

## Architecture

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
                                              │ Cron (every 6h) │
                                              │ NVD + KEV + RSS │
                                              │ + AI Enrichment │
                                              └────────────────┘
```

## Tech Stack

| Layer       | Technology                          | Hosting         |
|-------------|-------------------------------------|-----------------|
| Frontend    | React + Vite                        | Vercel (static) |
| API         | FastAPI + Pydantic V2               | Vercel (Python serverless) |
| Database    | PostgreSQL + pgvector               | Supabase (free tier) |
| AI          | Gemini 2.0 Flash                    | Google AI API (free tier) |
| Ingestion   | Python scripts                      | GitHub Actions (cron) |
| Auth        | OAuth2 + JWT + bcrypt               | — |

## Data Sources

### Stream 1: Vulnerabilities & Threats
- **NVD API v2** — NIST National Vulnerability Database (CVEs)
- **CISA KEV** — Known Exploited Vulnerabilities catalog

### Stream 2: News & Analysis (9 sources)
The Hacker News · Dark Reading · Krebs on Security · Infosecurity Magazine · CSO Online · SC Media · CyberScoop · ZDNet Security · TLDR Sec

### Stream 3: Research (3 sources)
SANS Internet Storm Center · Unsupervised Learning (Daniel Miessler) · Schneier on Security

### AI Enrichment
Every ingested item is automatically enriched by Gemini 2.0 Flash with:
- **3-bullet summary** — key facts at a glance
- **Business Angle** — why a CISO or business leader should care
- **Interview Nugget** — a memorable talking point for cybersecurity interviews

---

## Project Structure

```
├── .agents/                    # Workspace rules + skills
│   ├── AGENTS.md               # DB schema, conventions, env vars
│   └── skills/rate-limiting/   # Rate-limiting strategy docs
├── .github/workflows/
│   └── ingestion.yml           # Cron pipeline (every 6 hours)
├── api/
│   └── index.py                # FastAPI serverless entry point
├── shared/                     # Shared between API + ingestion
│   ├── supabase_client.py      # Database connection factory
│   ├── gemini_client.py        # Gemini wrapper + rate limiter
│   ├── models.py               # Pydantic V2 data models
│   └── auth_utils.py           # JWT + bcrypt utilities
├── ingestion/                  # GitHub Actions scripts
│   └── config.py               # Feed URLs + constants
├── frontend/                   # React app (coming soon)
├── vercel.json                 # Vercel deployment config
└── requirements.txt            # Python dependencies
```

---

## Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+ (for frontend)
- A [Supabase](https://supabase.com) account (free tier)
- A [Google AI Studio](https://aistudio.google.com) API key (free tier)
- (Optional) An [NVD API key](https://nvd.nist.gov/developers/request-an-api-key)

### 1. Clone & Install

```bash
git clone https://github.com/yashgoyal2802/Knowledge-base.git
cd Knowledge-base
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file in the project root:

```env
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key
DATABASE_URL=postgresql://postgres.ref:pass@pooler.supabase.com:6543/postgres
GEMINI_API_KEY=your-gemini-api-key
JWT_SECRET_KEY=your-jwt-secret
FRONTEND_URL=http://localhost:5173
NVD_API_KEY=your-nvd-key          # optional
```

### 3. Set Up Supabase

Run the SQL from [`.agents/AGENTS.md`](.agents/AGENTS.md) in the Supabase SQL editor to create the tables, indexes, and pgvector extension.

### 4. Run Locally

```bash
# API (FastAPI dev server)
uvicorn api.index:app --reload --port 8000

# Frontend (coming soon)
cd frontend && npm run dev
```

### 5. Deploy

- Push to GitHub → Vercel auto-deploys
- Set environment variables in Vercel dashboard
- Add repository secrets in GitHub for the Actions workflow

---

## Free-Tier Budget

| Service | Limit | Our Usage |
|---------|-------|-----------|
| Vercel Hobby | 100 GB bandwidth, 60s function timeout | Well within limits |
| Supabase Free | 500 MB database | ~195 MB/year estimated |
| Gemini Free | 1,500 req/day, 15 req/min | ~200 req/day (ingestion + RAG) |
| GitHub Actions | Unlimited minutes (public repo) | ~5 min/run × 4 runs/day |

---

## License

See [LICENSE](LICENSE) for details.