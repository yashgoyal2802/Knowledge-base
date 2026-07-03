"""
Central configuration for the CyberIntel ingestion pipeline.

All RSS feed URLs, API endpoints, rate-limit constants, and
processing parameters are defined here. Used by the GitHub Actions
workflow scripts (nvd_ingest, kev_ingest, rss_ingest, enrichment, embeddings).
"""

import os


# ---------------------------------------------------------------------------
# API Keys & Credentials
# ---------------------------------------------------------------------------

# TODO: These are read from GitHub Actions secrets at runtime.
#       For local development, create a .env file and use python-dotenv.

SUPABASE_URL: str = os.getenv(
    "SUPABASE_URL",
    "https://your-project-ref.supabase.co",  # TODO: your Supabase project URL
)
SUPABASE_SECRET_KEY: str = os.getenv(
    "SUPABASE_SECRET_KEY",
    "eyJ-your-secret-key-here",  # TODO: your Supabase secret key
)
DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres.ref:pass@pooler.supabase.com:6543/postgres",  # TODO: your pooled connection string
)
GEMINI_API_KEY: str = os.getenv(
    "GEMINI_API_KEY",
    "your-gemini-api-key-here",  # TODO: your Gemini API key
)
NVD_API_KEY: str = os.getenv(
    "NVD_API_KEY",
    "",  # Optional but recommended — 50 vs 5 req/30s
)


# ---------------------------------------------------------------------------
# Stream 1: Vulnerabilities & Threats
# ---------------------------------------------------------------------------

NVD_API_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"
NVD_RESULTS_PER_PAGE = 200
NVD_REQUEST_DELAY_KEYED = 0.7       # seconds between requests (with API key)
NVD_REQUEST_DELAY_UNKEYED = 6.5     # seconds between requests (without key)
NVD_MAX_DATE_RANGE_DAYS = 120       # NVD enforces max 120-day query windows

CISA_KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
CISA_KEV_GITHUB_URL = (
    "https://raw.githubusercontent.com/cisagov/kev-data/main/"
    "known_exploited_vulnerabilities.json"
)
# Use the GitHub mirror as primary (more reliable, no WAF issues)
CISA_KEV_PRIMARY = CISA_KEV_GITHUB_URL


# ---------------------------------------------------------------------------
# Stream 2: News & Analysis — RSS Feeds
# ---------------------------------------------------------------------------

NEWS_FEEDS: dict[str, dict] = {
    "the_hacker_news": {
        "url": "https://feeds.feedburner.com/TheHackersNews",
        "stream": "news",
        "full_content": True,
        "frequency": "daily",
    },
    "dark_reading": {
        "url": "https://www.darkreading.com/rss/all.xml",
        "stream": "news",
        "full_content": False,
        "frequency": "daily",
    },
    "krebs_on_security": {
        "url": "https://krebsonsecurity.com/feed/",
        "stream": "news",
        "full_content": True,
        "frequency": "2-4/week",
    },
    "infosecurity_magazine": {
        "url": "https://www.infosecurity-magazine.com/rss/news/",
        "stream": "news",
        "full_content": False,
        "frequency": "daily",
        "note": "No official RSS confirmed — may need fallback HTML scraping",
    },
    "cso_online": {
        "url": "https://www.csoonline.com/feed/",
        "stream": "news",
        "full_content": False,
        "frequency": "daily",
    },
    "sc_media": {
        "url": "https://www.scworld.com/feed",
        "stream": "news",
        "full_content": False,
        "frequency": "daily",
        "note": "No official RSS confirmed — may need fallback HTML scraping",
    },
    "cyberscoop": {
        "url": "https://cyberscoop.com/feed/",
        "stream": "news",
        "full_content": False,
        "frequency": "daily",
    },
    "zdnet_security": {
        "url": "https://www.zdnet.com/topic/security/rss.xml",
        "stream": "news",
        "full_content": False,
        "frequency": "daily",
        "note": "Feed can be unreliable — implement retry with fallback",
    },
    "tldr_sec": {
        "url": "https://rss.beehiiv.com/feeds/xgT92yW05G.xml",
        "stream": "news",
        "full_content": True,
        "frequency": "weekly",
    },
}


# ---------------------------------------------------------------------------
# Stream 3: Research
# ---------------------------------------------------------------------------

RESEARCH_FEEDS: dict[str, dict] = {
    "sans_isc": {
        "url": "https://isc.sans.edu/rssfeed_full.xml",
        "stream": "research",
        "full_content": True,
        "frequency": "daily",
    },
    "daniel_miessler": {
        "url": "https://danielmiessler.com/feed/",
        "stream": "research",
        "full_content": True,
        "frequency": "weekly",
    },
    "schneier_on_security": {
        "url": "https://www.schneier.com/blog/atom.xml",
        "stream": "research",
        "full_content": True,
        "frequency": "near-daily",
    },
}


# ---------------------------------------------------------------------------
# Combined feed registry (convenience)
# ---------------------------------------------------------------------------

ALL_FEEDS: dict[str, dict] = {**NEWS_FEEDS, **RESEARCH_FEEDS}


# ---------------------------------------------------------------------------
# AI Enrichment (Gemini 2.0 Flash)
# ---------------------------------------------------------------------------

GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
EMBEDDING_MODEL: str = "models/text-embedding-004"
EMBEDDING_DIMENSIONS: int = 768

# Free-tier rate limits
GEMINI_RPM: int = 15
GEMINI_RPD: int = 1500
# Delay between enrichment calls to stay safely under 15 RPM (~13 RPM effective)
GEMINI_ENRICHMENT_DELAY: float = 4.5  # seconds

ENRICHMENT_SYSTEM_PROMPT: str = (
    "You are a cybersecurity intelligence analyst. For the given article or "
    "vulnerability, generate:\n"
    "1. **summary_bullets**: Exactly 3 concise bullet points summarizing the key facts.\n"
    "2. **business_angle**: A 1-2 sentence explanation of why a business leader "
    "or CISO should care about this.\n"
    "3. **interview_nugget**: A single memorable talking point someone could use "
    "in a cybersecurity job interview to demonstrate awareness.\n\n"
    "Respond ONLY with valid JSON. Keys: summary_bullets (array of 3 strings), "
    "business_angle (string), interview_nugget (string). No markdown fences."
)


# ---------------------------------------------------------------------------
# HTTP Client Settings
# ---------------------------------------------------------------------------

REQUEST_TIMEOUT: int = 30  # seconds
USER_AGENT: str = (
    "CyberIntel-Bot/1.0 "
    "(Cybersecurity Knowledge Repository; "
    "+https://github.com/yashgoyal2802/Knowledge-base)"
)
MAX_RETRIES: int = 3
RETRY_BACKOFF_FACTOR: float = 2.0


# ---------------------------------------------------------------------------
# Processing Limits
# ---------------------------------------------------------------------------

# Max articles to process per source per ingestion run.
# With 12 sources × 25 = 300 max articles → well within 1,500 RPD.
MAX_ARTICLES_PER_SOURCE: int = 25

# Max CVEs to process per ingestion run (NVD can return thousands).
MAX_CVES_PER_RUN: int = 200
