"""Pydantic schemas — the public API contract for the Knowledge Brain.

Tasks 2 and 3 must import ONLY from this file when calling Task 1's API.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


# ─── Inbound ──────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    """Ask the Knowledge Brain a question."""

    question: str = Field(..., min_length=3, max_length=2000,
                          description="Natural-language question from user or agent.")
    top_k: int = Field(5, ge=1, le=20, description="Number of chunks to retrieve.")
    include_images: bool = Field(True, description="Return image captions in the answer.")
    session_id: str | None = Field(None, description="Optional session for multi-turn.")


class ScrapeRequest(BaseModel):
    """Trigger a manual scrape (admin use)."""

    mode: str = Field("incremental", pattern="^(full|incremental)$")
    force_urls: list[str] = Field(default_factory=list,
                                  description="Force-refresh specific article URLs.")


class HumanAnswerRequest(BaseModel):
    """Human expert submits an answer for an unanswered question."""

    task_id: str
    answer: str = Field(..., min_length=10)
    source_urls: list[str] = Field(default_factory=list)


class FeedbackRequest(BaseModel):
    """User rates a Knowledge Brain answer."""

    query_id: str
    rating: int = Field(..., ge=1, le=5)
    comment: str | None = None


# ─── Outbound ─────────────────────────────────────────────────────────────────

class SourceChunk(BaseModel):
    """One retrieved article chunk."""

    article_id: str
    title: str
    url: str
    excerpt: str
    score: float = Field(..., ge=0.0, le=1.0)


class ImageResult(BaseModel):
    """An image that is relevant to the answer."""

    image_url: str
    caption: str
    article_id: str
    article_title: str


class QueryResponse(BaseModel):
    """Full response from the Knowledge Brain."""

    query_id: str
    question: str
    answer: str
    confidence: float = Field(..., ge=0.0, le=1.0,
                              description="Cosine-similarity of the best chunk.")
    sources: list[SourceChunk]
    images: list[ImageResult]
    escalated: bool = Field(False,
                            description="True when no good answer found; human task created.")
    human_task_id: str | None = None


class ScrapeStatus(BaseModel):
    """Current scrape / sync job status."""

    job_id: str
    status: str  # queued | running | done | failed
    pages_found: int
    pages_scraped: int
    pages_updated: int
    pages_failed: int
    started_at: str | None
    finished_at: str | None
    message: str | None = None


class HumanTask(BaseModel):
    """An unanswered question waiting for a human expert."""

    task_id: str
    question: str
    created_at: str
    resolved: bool
    answer: str | None = None


class ArticleSummary(BaseModel):
    """One article in the knowledge base."""

    article_id: str
    title: str
    url: str
    category: str
    folder: str
    last_scraped: str
    image_count: int


class KBStats(BaseModel):
    """Knowledge base statistics."""

    total_articles: int
    total_chunks: int
    total_images: int
    last_full_sync: str | None
    last_incremental_sync: str | None
