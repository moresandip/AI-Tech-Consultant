"""FastAPI routes for Task 3 — Meeting to SOW."""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agents.diff_agent import compute_diff
from agents.estimator import estimate_hours
from agents.feasibility import check_feasibility
from agents.proposal_writer import write_proposal
from agents.requirements import extract_requirements
from agents.sow_writer import write_sow
from agents.transcriber import process_transcript
from db.models import Meeting, ScopeOfWork
from db.postgres import get_session

router = APIRouter()


# ─── Schemas ──────────────────────────────────────────────────────────────────

class MeetingInput(BaseModel):
    client_name: str
    project_name: str
    meeting_date: str | None = None
    transcript: str = Field(..., min_length=50)
    is_followup: bool = False
    parent_meeting_id: str | None = None
    hourly_rate: float = Field(75.0, ge=10.0, le=500.0)


class ApproveRequest(BaseModel):
    approved: bool = True


class SOWResponse(BaseModel):
    sow_id: str
    meeting_id: str
    version: int
    requirements: list[dict]
    feasibility: list[dict]
    tasks: list[dict]
    sow_markdown: str
    proposal_markdown: str
    total_hours_min: float
    total_hours_max: float
    total_cost_min: float
    total_cost_max: float
    diff_summary: str | None
    new_items: list | None
    changed_items: list | None
    out_of_scope_items: list | None
    approved: bool
    pipeline_steps: list[dict]
    latency_ms_total: int


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/meetings/process", response_model=SOWResponse, tags=["SOW"])
async def process_meeting(
    body: MeetingInput,
    session: AsyncSession = Depends(get_session),
) -> SOWResponse:
    """Run the full multi-agent pipeline on a meeting transcript."""
    start = time.monotonic()
    steps: list[dict] = []

    def log_step(name: str, detail: str = "") -> None:
        elapsed = int((time.monotonic() - start) * 1000)
        steps.append({"step": name, "elapsed_ms": elapsed, "detail": detail})

    # Store meeting
    meeting = Meeting(
        client_name=body.client_name,
        project_name=body.project_name,
        meeting_date=body.meeting_date,
        transcript=body.transcript,
        is_followup=body.is_followup,
        parent_meeting_id=body.parent_meeting_id,
    )
    session.add(meeting)
    await session.flush()
    log_step("meeting_stored", str(meeting.id))

    # Agent 1: Process transcript (chunk if long)
    processed = await process_transcript(body.transcript)
    log_step("transcript_processed", f"{len(processed)} chars")

    # Agent 2: Extract requirements
    req_data = await extract_requirements(processed)
    requirements = req_data.get("requirements", [])
    log_step("requirements_extracted", f"{len(requirements)} items")

    # Agent 3: Feasibility check (calls Task 1)
    feasibility = await check_feasibility(requirements)
    log_step("feasibility_checked")

    # Agent 4: Hour estimation
    tasks = await estimate_hours(requirements, feasibility)
    log_step("hours_estimated", f"{len(tasks)} tasks")

    total_min = sum(t.get("hours_min", 0) for t in tasks)
    total_max = sum(t.get("hours_max", 0) for t in tasks)

    # Agent 7: Diff (if follow-up)
    diff_data: dict = {}
    if body.is_followup and body.parent_meeting_id:
        parent_sow = (await session.execute(
            select(ScopeOfWork)
            .where(ScopeOfWork.meeting_id == body.parent_meeting_id)
            .order_by(ScopeOfWork.version.desc()).limit(1)
        )).scalar_one_or_none()

        if parent_sow and parent_sow.requirements:
            diff_data = await compute_diff(parent_sow.requirements, requirements)
            log_step("diff_computed", diff_data.get("summary", ""))

    # Agent 5: SOW
    sow_md = await write_sow(
        client_name=body.client_name,
        project_name=body.project_name,
        client_goals=req_data.get("client_goals", ""),
        deadline=req_data.get("deadline_mentioned"),
        requirements=requirements,
        feasibility=feasibility,
        tasks=tasks,
        hourly_rate=body.hourly_rate,
    )
    log_step("sow_written")

    # Agent 6: Proposal (Opus 4)
    proposal_md = await write_proposal(
        client_name=body.client_name,
        project_name=body.project_name,
        client_goals=req_data.get("client_goals", ""),
        deadline=req_data.get("deadline_mentioned"),
        budget=req_data.get("budget_mentioned"),
        tasks=tasks,
        hourly_rate=body.hourly_rate,
    )
    log_step("proposal_written")

    # Store SOW
    # Get version number
    prev_version = (await session.execute(
        select(ScopeOfWork.version)
        .where(ScopeOfWork.meeting_id == str(meeting.id))
        .order_by(ScopeOfWork.version.desc()).limit(1)
    )).scalar_one_or_none() or 0

    sow = ScopeOfWork(
        meeting_id=str(meeting.id),
        version=prev_version + 1,
        requirements=requirements,
        feasibility=feasibility,
        tasks=tasks,
        sow_markdown=sow_md,
        proposal_markdown=proposal_md,
        diff_summary=diff_data.get("summary"),
        new_items=diff_data.get("new_items"),
        changed_items=diff_data.get("changed"),
        out_of_scope_items=diff_data.get("out_of_scope"),
        total_hours_min=total_min,
        total_hours_max=total_max,
        total_cost_min=total_min * body.hourly_rate,
        total_cost_max=total_max * body.hourly_rate,
        hourly_rate=body.hourly_rate,
        pipeline_steps=steps,
        model_used_extraction="claude-sonnet-4-5",
        model_used_proposal="claude-opus-4-5",
        latency_ms_total=int((time.monotonic() - start) * 1000),
    )
    session.add(sow)
    await session.flush()
    log_step("sow_stored", str(sow.id))

    return SOWResponse(
        sow_id=str(sow.id),
        meeting_id=str(meeting.id),
        version=sow.version,
        requirements=requirements,
        feasibility=feasibility,
        tasks=tasks,
        sow_markdown=sow_md,
        proposal_markdown=proposal_md,
        total_hours_min=total_min,
        total_hours_max=total_max,
        total_cost_min=sow.total_cost_min or 0,
        total_cost_max=sow.total_cost_max or 0,
        diff_summary=diff_data.get("summary"),
        new_items=diff_data.get("new_items"),
        changed_items=diff_data.get("changed"),
        out_of_scope_items=diff_data.get("out_of_scope"),
        approved=False,
        pipeline_steps=steps,
        latency_ms_total=sow.latency_ms_total or 0,
    )


@router.post("/sow/{sow_id}/approve", tags=["SOW"])
async def approve_sow(
    sow_id: str,
    body: ApproveRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Human approves (or rejects) a SOW before it goes to the client."""
    from datetime import datetime, timezone
    sow = (await session.execute(
        select(ScopeOfWork).where(ScopeOfWork.id == sow_id)
    )).scalar_one_or_none()
    if not sow:
        raise HTTPException(404, "SOW not found.")
    sow.approved = body.approved
    sow.approved_at = datetime.now(tz=timezone.utc)
    return {"ok": True, "approved": body.approved, "sow_id": sow_id}


@router.get("/meetings", tags=["SOW"])
async def list_meetings(
    session: AsyncSession = Depends(get_session),
    limit: int = 20,
) -> list[dict]:
    rows = (await session.execute(
        select(Meeting).order_by(Meeting.created_at.desc()).limit(limit)
    )).scalars().all()
    return [
        {
            "id": r.id,
            "client_name": r.client_name,
            "project_name": r.project_name,
            "meeting_date": r.meeting_date,
            "is_followup": r.is_followup,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.get("/sow/{sow_id}", response_model=SOWResponse, tags=["SOW"])
async def get_sow(
    sow_id: str,
    session: AsyncSession = Depends(get_session),
) -> SOWResponse:
    sow = (await session.execute(
        select(ScopeOfWork).where(ScopeOfWork.id == sow_id)
    )).scalar_one_or_none()
    if not sow:
        raise HTTPException(404, "SOW not found.")
    return SOWResponse(
        sow_id=str(sow.id),
        meeting_id=sow.meeting_id,
        version=sow.version,
        requirements=sow.requirements or [],
        feasibility=sow.feasibility or [],
        tasks=sow.tasks or [],
        sow_markdown=sow.sow_markdown or "",
        proposal_markdown=sow.proposal_markdown or "",
        total_hours_min=sow.total_hours_min or 0,
        total_hours_max=sow.total_hours_max or 0,
        total_cost_min=sow.total_cost_min or 0,
        total_cost_max=sow.total_cost_max or 0,
        diff_summary=sow.diff_summary,
        new_items=sow.new_items,
        changed_items=sow.changed_items,
        out_of_scope_items=sow.out_of_scope_items,
        approved=sow.approved,
        pipeline_steps=sow.pipeline_steps or [],
        latency_ms_total=sow.latency_ms_total or 0,
    )
