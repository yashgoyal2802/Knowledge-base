"""
Cybersecurity Knowledge Repository — API Entry Point

Deployed as a Vercel serverless function. All routes are defined
directly in this file — no APIRouter layer or internal abstraction.

Vercel auto-detects the `app` variable for the serverless handler.
"""

import os
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field

from shared.auth_utils import create_access_token, decode_access_token, hash_password, verify_password
from shared.models import (
    Article,
    ArticleListResponse,
    ChatRequest,
    Token,
    User,
    UserCreate,
    Vulnerability,
    VulnerabilityListResponse,
)
from shared.rag import search_similar_items, stream_rag_chat
from shared.supabase_client import get_supabase_client


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
API_VERSION = "0.1.0"


# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="CyberIntel API",
    description=(
        "Cybersecurity Knowledge Repository — threat intelligence, "
        "vulnerability tracking, and AI-powered analysis."
    ),
    version=API_VERSION,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

# CORS — accept requests from the Vercel frontend and local dev servers
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        FRONTEND_URL,
        "http://localhost:5173",   # Vite dev server
        "http://localhost:3000",   # Fallback dev port
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Response Models (Pydantic V2)
# ---------------------------------------------------------------------------
class HealthResponse(BaseModel):
    """Response for the health-check endpoint."""
    status: str = Field(description="Service health status")
    version: str = Field(description="API version string")
    service: str = Field(description="Service identifier")
    timestamp: str = Field(description="ISO-8601 UTC timestamp")


class ErrorResponse(BaseModel):
    """Standard error envelope."""
    error: str
    detail: str | None = None


# ---------------------------------------------------------------------------
# Exception Handlers
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Catch-all handler — never expose stack traces to the client."""
    return JSONResponse(
        status_code=500,
        content={"error": "internal_server_error", "detail": "An unexpected error occurred."},
    )


# ---------------------------------------------------------------------------
# Routes (defined directly — no router abstraction)
# ---------------------------------------------------------------------------

@app.get("/api", response_model=HealthResponse, tags=["system"])
async def health_check():
    """Health-check endpoint. Returns service status and version."""
    return HealthResponse(
        status="operational",
        version=API_VERSION,
        service="cyberintel-api",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.get("/api/ping", tags=["system"])
async def ping():
    """Lightweight liveness probe (used by GitHub Actions keep-alive)."""
    return {"pong": True}


# ---------------------------------------------------------------------------
# Authentication Dependencies & Helpers
# ---------------------------------------------------------------------------

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


async def get_current_user(token: str | None = Depends(oauth2_scheme)) -> dict:
    """Validate JWT token and return the current active user dict."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Provide Bearer token in Authorization header.",
        )
    user_id = decode_access_token(token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
        )
    client = get_supabase_client(use_service_key=False)
    res = client.table("users").select("*").eq("id", user_id).limit(1).execute()
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found.",
        )
    user = res.data[0]
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is inactive.",
        )
    return user


class LoginRequest(BaseModel):
    """Payload for JSON-based email/password login."""
    email: str
    password: str


# ---------------------------------------------------------------------------
# Auth Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/auth/register", response_model=User, status_code=status.HTTP_201_CREATED, tags=["auth"])
async def register(user_in: UserCreate):
    """Register a new user account with bcrypt password hashing."""
    client = get_supabase_client(use_service_key=True)
    existing = client.table("users").select("id").eq("email", user_in.email).limit(1).execute()
    if existing.data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )

    hashed_pwd = hash_password(user_in.password)
    payload = {
        "email": user_in.email,
        "hashed_password": hashed_pwd,
        "full_name": user_in.full_name,
        "is_active": True,
    }
    res = client.table("users").insert(payload).execute()
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user account.",
        )
    return res.data[0]


@app.post("/api/auth/login", response_model=Token, tags=["auth"])
async def login(credentials: LoginRequest):
    """Authenticate with email and password, returning a signed JWT Bearer token."""
    client = get_supabase_client(use_service_key=True)
    res = client.table("users").select("*").eq("email", credentials.email).limit(1).execute()
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    user = res.data[0]
    if not verify_password(credentials.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is inactive.",
        )

    token = create_access_token(subject=str(user["id"]))
    return Token(access_token=token, token_type="bearer")


@app.get("/api/auth/me", response_model=User, tags=["auth"])
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get the currently authenticated user's profile."""
    return current_user


# ---------------------------------------------------------------------------
# Articles Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/articles", response_model=ArticleListResponse, tags=["articles"])
async def list_articles(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    stream: str | None = Query(None, description="Filter by stream: 'news' or 'research'"),
    source: str | None = Query(None, description="Filter by source identifier"),
):
    """Fetch paginated articles with optional stream/source filtering."""
    client = get_supabase_client(use_service_key=False)
    query = client.table("articles").select("*", count="exact")
    if stream:
        query = query.eq("stream", stream.lower())
    if source:
        query = query.eq("source", source.lower())

    offset = (page - 1) * page_size
    res = query.order("published_at", desc=True).range(offset, offset + page_size - 1).execute()

    total = res.count if res.count is not None else len(res.data or [])
    items = res.data or []
    has_more = offset + len(items) < total

    return ArticleListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=has_more,
    )


@app.get("/api/articles/search", tags=["articles"])
async def search_articles_endpoint(
    q: str = Query(..., min_length=1, description="Search query string"),
    limit: int = Query(10, ge=1, le=50, description="Max results to return"),
):
    """Semantic vector search across articles using pgvector and Gemini embeddings."""
    results = await search_similar_items(q, limit=limit)
    articles_only = [r for r in results if r.get("item_type") == "article"]
    return {"items": articles_only, "query": q, "count": len(articles_only)}


# ---------------------------------------------------------------------------
# Vulnerabilities Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/vulnerabilities", response_model=VulnerabilityListResponse, tags=["vulnerabilities"])
async def list_vulnerabilities(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    severity: str | None = Query(None, description="Filter by severity: CRITICAL, HIGH, MEDIUM, LOW"),
    source: str | None = Query(None, description="Filter by data source: 'nvd' or 'kev'"),
    kev_only: bool = Query(False, description="If True, only return CISA KEV catalog items"),
):
    """Fetch paginated vulnerabilities with severity, source, and KEV filtering."""
    client = get_supabase_client(use_service_key=False)
    query = client.table("vulnerabilities").select("*", count="exact")
    if severity:
        query = query.eq("severity", severity.upper())
    if source:
        query = query.eq("source", source.lower())
    if kev_only:
        query = query.not_.is_("kev_due_date", "null")

    offset = (page - 1) * page_size
    res = query.order("published_at", desc=True).range(offset, offset + page_size - 1).execute()

    total = res.count if res.count is not None else len(res.data or [])
    items = res.data or []
    has_more = offset + len(items) < total

    return VulnerabilityListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_more=has_more,
    )


@app.get("/api/vulnerabilities/{cve_id}", response_model=Vulnerability, tags=["vulnerabilities"])
async def get_vulnerability(cve_id: str):
    """Get detailed information for a single vulnerability by CVE ID."""
    client = get_supabase_client(use_service_key=False)
    res = client.table("vulnerabilities").select("*").eq("cve_id", cve_id.upper()).limit(1).execute()
    if not res.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vulnerability {cve_id.upper()} not found.",
        )
    return res.data[0]


# ---------------------------------------------------------------------------
# RAG Chat Endpoint (Server-Sent Events)
# ---------------------------------------------------------------------------

@app.post("/api/chat", tags=["rag"])
async def rpc_chat(request: ChatRequest):
    """
    Stream RAG answers with threat intelligence citations via Server-Sent Events (SSE).
    
    Returns an event stream where each event is formatted as `data: <json>\\n\\n`.
    Event types: 'token', 'source', 'done', or 'error'.
    """
    return StreamingResponse(
        stream_rag_chat(request.query),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
