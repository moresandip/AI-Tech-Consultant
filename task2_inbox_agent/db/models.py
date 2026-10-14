"""SQLAlchemy models for Task 2 — Inbox Agent."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


class Email(Base):
    """One inbound customer email."""
    __tablename__ = "emails"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    sender_email: Mapped[str] = mapped_column(String(256), nullable=False)
    sender_name: Mapped[str | None] = mapped_column(String(256))
    subject: Mapped[str] = mapped_column(String(512), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                   server_default=func.now())
    category: Mapped[str | None] = mapped_column(String(64))   # how-to, refund, complaint …
    intent: Mapped[str | None] = mapped_column(String(64))     # question, request, complaint …
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending|drafted|sent
    auto_sent: Mapped[bool] = mapped_column(Boolean, default=False)


class Draft(Base):
    """An AI-generated or human-edited reply draft."""
    __tablename__ = "drafts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email_id: Mapped[str] = mapped_column(String(36), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    generated_by: Mapped[str] = mapped_column(String(32), default="ai")  # ai | human
    model_used: Mapped[str | None] = mapped_column(String(64))
    kb_sources: Mapped[list | None] = mapped_column(JSONB)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                  server_default=func.now())


class Feedback(Base):
    """What the human did with a draft: sent as-is, edited, or replaced."""
    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email_id: Mapped[str] = mapped_column(String(36), nullable=False)
    draft_id: Mapped[str] = mapped_column(String(36), nullable=False)
    action: Mapped[str] = mapped_column(String(32))  # sent_as_is | edited | replaced
    final_body: Mapped[str] = mapped_column(Text, nullable=False)
    edit_distance: Mapped[float | None] = mapped_column(Float)  # 0 = perfect, 1 = fully replaced
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                  server_default=func.now())


class EmailTypeStats(Base):
    """Tracks how many consecutive perfect drafts a category has produced."""
    __tablename__ = "email_type_stats"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    category: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    consecutive_perfect: Mapped[int] = mapped_column(Integer, default=0)
    auto_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    total_sent: Mapped[int] = mapped_column(Integer, default=0)
    total_edited: Mapped[int] = mapped_column(Integer, default=0)
    auto_revoked_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                   server_default=func.now(),
                                                   onupdate=func.now())


class PromptVersion(Base):
    """Versioned prompts for the Inbox Agent."""
    __tablename__ = "inbox_prompt_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    prompt_key: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    eval_score: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                  server_default=func.now())
