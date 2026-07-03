"""
Pydantic V2 data models for the Cybersecurity Knowledge Repository.

These models are shared between the API layer and the ingestion pipeline.
All models use Pydantic V2 conventions (model_config, ConfigDict).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Articles (News & Research streams)
# ---------------------------------------------------------------------------

class ArticleBase(BaseModel):
    """Base fields for an article (used for both creation and reading)."""
    model_config = ConfigDict(from_attributes=True)

    source: str = Field(description="Source identifier, e.g. 'the_hacker_news', 'krebs_on_security'")
    stream: str = Field(description="Content stream: 'news' or 'research'")
    title: str = Field(description="Article title")
    url: str = Field(description="Canonical URL (unique across articles)")
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    raw_content: Optional[str] = Field(None, description="Full article text (if available from feed)")
    tags: list[str] = Field(default_factory=list)


class ArticleEnrichment(BaseModel):
    """AI-generated enrichment fields, populated by the Gemini pipeline."""
    summary_bullets: list[str] = Field(
        default_factory=list,
        description="Exactly 3 concise bullet points summarizing the article",
    )
    business_angle: Optional[str] = Field(
        None,
        description="Why a CISO or business leader should care",
    )
    interview_nugget: Optional[str] = Field(
        None,
        description="A memorable talking point for cybersecurity interviews",
    )


class Article(ArticleBase, ArticleEnrichment):
    """Full article model as returned from the database."""
    id: UUID
    enriched: bool = False
    created_at: datetime
    updated_at: datetime


class ArticleCreate(ArticleBase):
    """Schema for inserting a new article (no id or timestamps)."""
    pass


class ArticleListResponse(BaseModel):
    """Paginated article list response."""
    items: list[Article]
    total: int
    page: int
    page_size: int
    has_more: bool


# ---------------------------------------------------------------------------
# Vulnerabilities (NVD + CISA KEV)
# ---------------------------------------------------------------------------

class VulnerabilityBase(BaseModel):
    """Base fields for a vulnerability entry."""
    model_config = ConfigDict(from_attributes=True)

    cve_id: str = Field(description="CVE identifier, e.g. 'CVE-2024-1234'")
    source: str = Field(description="Data source: 'nvd' or 'kev'")
    description: Optional[str] = None
    cvss_v3_score: Optional[float] = Field(None, ge=0.0, le=10.0)
    cvss_v3_vector: Optional[str] = None
    severity: Optional[str] = Field(
        None,
        description="Severity rating: CRITICAL, HIGH, MEDIUM, or LOW",
    )
    cwe_ids: list[str] = Field(default_factory=list)
    affected_products: Optional[dict] = Field(
        None,
        description="CPE match data from NVD (JSON)",
    )
    reference_urls: Optional[dict] = Field(
        None,
        description="Reference URLs and tags (JSON)",
    )
    kev_known_ransomware: Optional[bool] = Field(
        None,
        description="CISA KEV: known to be used in ransomware campaigns",
    )
    kev_due_date: Optional[date] = Field(
        None,
        description="CISA KEV: remediation due date",
    )
    published_at: Optional[datetime] = None
    last_modified: Optional[datetime] = None


class Vulnerability(VulnerabilityBase, ArticleEnrichment):
    """Full vulnerability model as returned from the database."""
    id: UUID
    enriched: bool = False
    created_at: datetime


class VulnerabilityCreate(VulnerabilityBase):
    """Schema for inserting a new vulnerability (no id or timestamps)."""
    pass


class VulnerabilityListResponse(BaseModel):
    """Paginated vulnerability list response."""
    items: list[Vulnerability]
    total: int
    page: int
    page_size: int
    has_more: bool


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

class UserBase(BaseModel):
    """Public user fields."""
    email: str
    full_name: Optional[str] = None


class UserCreate(UserBase):
    """Registration payload (includes plaintext password)."""
    password: str = Field(min_length=8, description="Must be at least 8 characters")


class User(UserBase):
    """User as returned from the database (never includes password)."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    is_active: bool = True
    created_at: datetime


class Token(BaseModel):
    """JWT access token response."""
    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """Decoded JWT payload."""
    sub: str  # user id (UUID as string)
    exp: datetime


# ---------------------------------------------------------------------------
# RAG Chat
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    """User's question to the RAG system."""
    query: str = Field(min_length=1, max_length=2000)
    stream: bool = Field(True, description="If True, response is streamed via SSE")


class ChatChunk(BaseModel):
    """
    A single chunk in the SSE stream from the RAG endpoint.

    Types:
      - 'token'  : a piece of the generated answer
      - 'source' : a relevant source document (sent after answer)
      - 'done'   : signals the stream is complete
      - 'error'  : an error occurred during generation
    """
    type: str = Field(description="Chunk type: 'token', 'source', 'done', or 'error'")
    content: str = ""
    sources: list[dict] = Field(default_factory=list)
