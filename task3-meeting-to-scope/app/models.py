"""ORM models for Task 3 — Meeting to SOW."""

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


class Meeting(Base):
    """One client meeting with one or more transcripts."""
    __tablename__ = "meetings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    client_name: Mapped[str] = mapped_column(String(256), nullable=False)
    project_name: Mapped[str] = mapped_column(String(256), nullable=False)
    meeting_date: Mapped[str | None] = mapped_column(String(32))
    transcript: Mapped[str] = mapped_column(Text, nullable=False)
    is_followup: Mapped[bool] = mapped_column(Boolean, default=False)
    parent_meeting_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                  server_default=func.now())


class ScopeOfWork(Base):
    """A versioned scope of work document for a meeting."""
    __tablename__ = "scopes_of_work"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    meeting_id: Mapped[str] = mapped_column(String(36), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)

    # Extracted requirements
    requirements: Mapped[list | None] = mapped_column(JSONB)  # list of {title, description, type}

    # Feasibility checks against Knowledge Brain
    feasibility: Mapped[list | None] = mapped_column(JSONB)  # list of {req, can_be_done_with_setting, detail}

    # Task list with estimates
    tasks: Mapped[list | None] = mapped_column(JSONB)  # list of {task, hours_min, hours_max, type}

    # SOW document (markdown)
    sow_markdown: Mapped[str | None] = mapped_column(Text)

    # Proposal (client-facing markdown)
    proposal_markdown: Mapped[str | None] = mapped_column(Text)

    # Diff from previous version (for follow-up meetings)
    diff_summary: Mapped[str | None] = mapped_column(Text)
    new_items: Mapped[list | None] = mapped_column(JSONB)
    changed_items: Mapped[list | None] = mapped_column(JSONB)
    out_of_scope_items: Mapped[list | None] = mapped_column(JSONB)

    # Totals
    total_hours_min: Mapped[float | None] = mapped_column(Float)
    total_hours_max: Mapped[float | None] = mapped_column(Float)
    total_cost_min: Mapped[float | None] = mapped_column(Float)
    total_cost_max: Mapped[float | None] = mapped_column(Float)
    hourly_rate: Mapped[float] = mapped_column(Float, default=75.0)

    # Approval workflow
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Pipeline metadata
    pipeline_steps: Mapped[list | None] = mapped_column(JSONB)  # step log
    model_used_extraction: Mapped[str | None] = mapped_column(String(64))
    model_used_proposal: Mapped[str | None] = mapped_column(String(64))
    latency_ms_total: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                  server_default=func.now())
