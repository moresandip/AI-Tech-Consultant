"""SQLAlchemy async models for Task 1 — Knowledge Brain."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func, JSON,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


class Article(Base):
    """One help-center article (folder-level page)."""
    __tablename__ = "articles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    url: Mapped[str] = mapped_column(String(2048), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    category: Mapped[str | None] = mapped_column(String(256))
    folder: Mapped[str | None] = mapped_column(String(256))
    raw_html: Mapped[str | None] = mapped_column(Text)
    clean_text: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(64))  # SHA-256
    last_modified_remote: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_scraped: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    image_count: Mapped[int] = mapped_column(Integer, default=0)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    images: Mapped[list["ImageCaption"]] = relationship(back_populates="article",
                                                         cascade="all, delete-orphan")
    chunks: Mapped[list["ArticleChunk"]] = relationship(back_populates="article",
                                                         cascade="all, delete-orphan")


class ArticleChunk(Base):
    """One text chunk from an article, stored for audit; vectors live in ChromaDB."""
    __tablename__ = "article_chunks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    article_id: Mapped[str] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"))
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0)

    article: Mapped["Article"] = relationship(back_populates="chunks")


class ImageCaption(Base):
    """Claude-generated caption for one screenshot inside an article."""
    __tablename__ = "image_captions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    article_id: Mapped[str] = mapped_column(ForeignKey("articles.id", ondelete="CASCADE"))
    image_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    caption: Mapped[str] = mapped_column(Text, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)

    article: Mapped["Article"] = relationship(back_populates="images")


class QueryLog(Base):
    """Every question asked of the Knowledge Brain, for evals and feedback."""
    __tablename__ = "query_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    sources: Mapped[dict | None] = mapped_column(JSON)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)
    rating: Mapped[int | None] = mapped_column(Integer)          # 1-5
    feedback_comment: Mapped[str | None] = mapped_column(Text)
    model_used: Mapped[str | None] = mapped_column(String(64))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                  server_default=func.now())


class HumanTaskModel(Base):
    """An unanswered question escalated to a human expert."""
    __tablename__ = "human_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    query_log_id: Mapped[str | None] = mapped_column(String(36))
    answer: Mapped[str | None] = mapped_column(Text)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                  server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PromptVersion(Base):
    """Versioned prompt store — every prompt change is recorded for rollback."""
    __tablename__ = "prompt_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    prompt_key: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    eval_score: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                  server_default=func.now())


class ScrapeMeta(Base):
    """Audit log for every scrape job."""
    __tablename__ = "scrape_meta"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    mode: Mapped[str] = mapped_column(String(32))   # full | incremental
    pages_found: Mapped[int] = mapped_column(Integer, default=0)
    pages_scraped: Mapped[int] = mapped_column(Integer, default=0)
    pages_updated: Mapped[int] = mapped_column(Integer, default=0)
    pages_failed: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
