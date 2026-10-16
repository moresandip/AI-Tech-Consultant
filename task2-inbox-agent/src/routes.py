"""FastAPI routes for Task 2 — Inbox Agent."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

try:
    from src.email.classifier import classify_email
    from src.drafting.drafter import draft_reply
    from src.feedback.learner import (
        get_few_shot_examples,
        is_auto_approved,
        record_feedback,
    )
    from src.models import Draft, Email, EmailTypeStats, Feedback
    from src.postgres import get_session
except ImportError:
    from email.classifier import classify_email
    from drafting.drafter import draft_reply
    from feedback.learner import (
        get_few_shot_examples,
        is_auto_approved,
        record_feedback,
    )
    from models import Draft, Email, EmailTypeStats, Feedback
    from postgres import get_session

router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────────────

class InboundEmail(BaseModel):
    sender_email: str
    sender_name: str = ""
    subject: str
    body: str


class DraftResponse(BaseModel):
    email_id: str
    draft_id: str
    draft_body: str
    category: str
    intent: str
    urgency: str
    summary: str
    auto_sent: bool
    kb_sources: list[dict]
    model_used: str
    latency_ms: int
    input_tokens: int
    output_tokens: int


class FeedbackBody(BaseModel):
    action: str = Field(..., pattern="^(sent_as_is|edited|replaced)$")
    final_body: str


class StatsResponse(BaseModel):
    total_emails: int
    total_drafted: int
    auto_approved_categories: list[str]
    category_stats: list[dict]


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/emails/process", response_model=DraftResponse, tags=["Inbox"])
async def process_email(
    body: InboundEmail,
    session: AsyncSession = Depends(get_session),
) -> DraftResponse:
    """Classify an email, draft a reply, and return for human review (or auto-send)."""
    # 1. Classify
    classification = await classify_email(body.subject, body.body)

    # 2. Store email
    email = Email(
        sender_email=body.sender_email,
        sender_name=body.sender_name,
        subject=body.subject,
        body=body.body,
        category=classification["category"],
        intent=classification["intent"],
    )
    session.add(email)
    await session.flush()

    # 3. Check auto-approval
    auto_send = await is_auto_approved(session, classification["category"])

    # 4. Get few-shot examples from past approved drafts
    examples = await get_few_shot_examples(session, classification["category"])

    # 5. Draft
    draft_data = await draft_reply(
        email_id=str(email.id),
        sender_name=body.sender_name,
        sender_email=body.sender_email,
        subject=body.subject,
        body=body.body,
        classification=classification,
        few_shot_examples=examples,
    )

    # 6. Store draft
    draft = Draft(
        email_id=str(email.id),
        version=1,
        body=draft_data["body"],
        generated_by="ai",
        model_used=draft_data["model_used"],
        kb_sources=draft_data["kb_sources"],
        input_tokens=draft_data["input_tokens"],
        output_tokens=draft_data["output_tokens"],
        latency_ms=draft_data["latency_ms"],
    )
    session.add(draft)
    await session.flush()

    # 7. If auto-approved, record as sent_as_is
    if auto_send:
        email.status = "sent"
        email.auto_sent = True
        await record_feedback(
            session, str(email.id), str(draft.id),
            classification["category"], "sent_as_is",
            draft_data["body"], draft_data["body"],
        )
    else:
        email.status = "drafted"

    return DraftResponse(
        email_id=str(email.id),
        draft_id=str(draft.id),
        draft_body=draft_data["body"],
        category=classification["category"],
        intent=classification["intent"],
        urgency=classification["urgency"],
        summary=classification["summary"],
        auto_sent=auto_send,
        kb_sources=draft_data["kb_sources"],
        model_used=draft_data["model_used"],
        latency_ms=draft_data["latency_ms"],
        input_tokens=draft_data["input_tokens"],
        output_tokens=draft_data["output_tokens"],
    )


@router.post("/emails/{email_id}/feedback", tags=["Inbox"])
async def submit_feedback(
    email_id: str,
    body: FeedbackBody,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Human sends, edits, or replaces a draft. Records learning signal."""
    # Get email and latest draft
    email_row = (await session.execute(
        select(Email).where(Email.id == email_id)
    )).scalar_one_or_none()
    if not email_row:
        raise HTTPException(404, "Email not found.")

    draft_row = (await session.execute(
        select(Draft).where(Draft.email_id == email_id)
        .order_by(Draft.version.desc()).limit(1)
    )).scalar_one_or_none()
    if not draft_row:
        raise HTTPException(404, "No draft found for this email.")

    result = await record_feedback(
        session, email_id, str(draft_row.id),
        email_row.category or "other", body.action,
        draft_row.body, body.final_body,
    )

    email_row.status = "sent"
    return {"ok": True, **result}


@router.get("/emails", tags=["Inbox"])
async def list_emails(
    session: AsyncSession = Depends(get_session),
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    query = select(Email).order_by(Email.received_at.desc()).limit(limit).offset(offset)
    if status:
        query = query.where(Email.status == status)
    rows = (await session.execute(query)).scalars().all()
    return [
        {
            "id": r.id,
            "sender_email": r.sender_email,
            "sender_name": r.sender_name,
            "subject": r.subject,
            "category": r.category,
            "intent": r.intent,
            "status": r.status,
            "auto_sent": r.auto_sent,
            "received_at": r.received_at.isoformat() if r.received_at else None,
        }
        for r in rows
    ]


@router.get("/emails/{email_id}/draft", tags=["Inbox"])
async def get_draft(
    email_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict:
    draft = (await session.execute(
        select(Draft).where(Draft.email_id == email_id)
        .order_by(Draft.version.desc()).limit(1)
    )).scalar_one_or_none()
    if not draft:
        raise HTTPException(404, "No draft.")
    return {
        "draft_id": str(draft.id),
        "body": draft.body,
        "model_used": draft.model_used,
        "kb_sources": draft.kb_sources,
        "input_tokens": draft.input_tokens,
        "output_tokens": draft.output_tokens,
        "latency_ms": draft.latency_ms,
    }


@router.get("/stats", response_model=StatsResponse, tags=["Stats"])
async def get_stats(session: AsyncSession = Depends(get_session)) -> StatsResponse:
    from sqlalchemy import func

    total_emails = (await session.execute(
        select(func.count(Email.id))
    )).scalar() or 0

    total_drafted = (await session.execute(
        select(func.count(Draft.id))
    )).scalar() or 0

    cat_rows = (await session.execute(select(EmailTypeStats))).scalars().all()
    auto_approved = [r.category for r in cat_rows if r.auto_approved]
    category_stats = [
        {
            "category": r.category,
            "consecutive_perfect": r.consecutive_perfect,
            "auto_approved": r.auto_approved,
            "total_sent": r.total_sent,
            "total_edited": r.total_edited,
        }
        for r in cat_rows
    ]

    return StatsResponse(
        total_emails=total_emails,
        total_drafted=total_drafted,
        auto_approved_categories=auto_approved,
        category_stats=category_stats,
    )
