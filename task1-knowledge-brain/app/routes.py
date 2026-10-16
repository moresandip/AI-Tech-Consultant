"""FastAPI route definitions for the Knowledge Brain."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, status

from app.schemas import (
    ArticleSummary,
    FeedbackRequest,
    HumanAnswerRequest,
    HumanTask,
    KBStats,
    QueryRequest,
    QueryResponse,
    ScrapeRequest,
    ScrapeStatus,
)
from app.chatbot import answer_question
from ingestion.scraper import run_full_scrape, run_incremental_scrape
from app.postgres import get_session
from app.models import Article, HumanTaskModel, QueryLog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.settings import settings

router = APIRouter()


# ─── Auth ─────────────────────────────────────────────────────────────────────

async def verify_api_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
    if x_api_key != settings.task1_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Invalid or missing X-API-Key header.")


# ─── Core query endpoint (used by Tasks 2 and 3) ─────────────────────────────

@router.post(
    "/query",
    response_model=QueryResponse,
    summary="Query the Knowledge Brain",
    description=(
        "Ask a natural-language question. Returns an answer, cited sources, "
        "and any relevant screenshot captions. If confidence < 0.4 the question "
        "is escalated to a human expert and `escalated=true` is returned."
    ),
    tags=["Query"],
)
async def query(
    body: QueryRequest,
    session: AsyncSession = Depends(get_session),
) -> QueryResponse:
    return await answer_question(body, session)


# ─── Scrape management (admin) ────────────────────────────────────────────────

_scrape_jobs: dict[str, ScrapeStatus] = {}


@router.post(
    "/scrape/full",
    response_model=ScrapeStatus,
    summary="Trigger a full scrape",
    tags=["Scrape"],
    dependencies=[Depends(verify_api_key)],
)
async def scrape_full(
    body: ScrapeRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> ScrapeStatus:
    job_id = str(uuid.uuid4())
    status_obj = ScrapeStatus(
        job_id=job_id, status="queued",
        pages_found=0, pages_scraped=0, pages_updated=0,
        pages_failed=0, started_at=None, finished_at=None,
    )
    _scrape_jobs[job_id] = status_obj
    background_tasks.add_task(run_full_scrape, job_id, _scrape_jobs)
    return status_obj


@router.post(
    "/scrape/incremental",
    response_model=ScrapeStatus,
    summary="Trigger an incremental sync",
    tags=["Scrape"],
    dependencies=[Depends(verify_api_key)],
)
async def scrape_incremental(
    background_tasks: BackgroundTasks,
) -> ScrapeStatus:
    job_id = str(uuid.uuid4())
    status_obj = ScrapeStatus(
        job_id=job_id, status="queued",
        pages_found=0, pages_scraped=0, pages_updated=0,
        pages_failed=0, started_at=None, finished_at=None,
    )
    _scrape_jobs[job_id] = status_obj
    background_tasks.add_task(run_incremental_scrape, job_id, _scrape_jobs)
    return status_obj


@router.get(
    "/scrape/status/{job_id}",
    response_model=ScrapeStatus,
    tags=["Scrape"],
)
async def scrape_status(job_id: str) -> ScrapeStatus:
    if job_id not in _scrape_jobs:
        raise HTTPException(404, "Job not found.")
    return _scrape_jobs[job_id]


# ─── Human-in-the-loop ───────────────────────────────────────────────────────

@router.get(
    "/human-tasks",
    response_model=list[HumanTask],
    summary="List unresolved escalated questions",
    tags=["Human Tasks"],
    dependencies=[Depends(verify_api_key)],
)
async def list_human_tasks(
    session: AsyncSession = Depends(get_session),
) -> list[HumanTask]:
    result = await session.execute(
        select(HumanTaskModel).where(HumanTaskModel.resolved.is_(False))
    )
    rows = result.scalars().all()
    return [
        HumanTask(
            task_id=str(r.id),
            question=r.question,
            created_at=r.created_at.isoformat(),
            resolved=r.resolved,
            answer=r.answer,
        )
        for r in rows
    ]


@router.post(
    "/human-tasks/{task_id}/resolve",
    summary="Human expert submits answer; it flows back into the KB",
    tags=["Human Tasks"],
    dependencies=[Depends(verify_api_key)],
)
async def resolve_human_task(
    task_id: str,
    body: HumanAnswerRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    from retrieval.embedder import upsert_human_answer

    result = await session.execute(
        select(HumanTaskModel).where(HumanTaskModel.id == task_id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(404, "Task not found.")

    task.answer = body.answer
    task.resolved = True
    await session.commit()

    # Embed the answer so future queries can find it
    await upsert_human_answer(task_id, task.question, body.answer, body.source_urls)
    return {"ok": True, "task_id": task_id}


# ─── Feedback ─────────────────────────────────────────────────────────────────

@router.post("/feedback", tags=["Feedback"])
async def submit_feedback(
    body: FeedbackRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    result = await session.execute(
        select(QueryLog).where(QueryLog.id == body.query_id)
    )
    log = result.scalar_one_or_none()
    if log:
        log.rating = body.rating
        log.feedback_comment = body.comment
        await session.commit()
    return {"ok": True}


# ─── Stats & listing ──────────────────────────────────────────────────────────

@router.get("/stats", response_model=KBStats, tags=["Meta"])
async def stats(session: AsyncSession = Depends(get_session)) -> KBStats:
    from app.models import ScrapeMeta, ImageCaption
    from retrieval.embedder import get_chroma_stats

    article_count = (await session.execute(select(func.count(Article.id)))).scalar() or 0
    image_count = (await session.execute(select(func.count(ImageCaption.id)))).scalar() or 0

    chroma = get_chroma_stats()
    last_full = await session.execute(
        select(ScrapeMeta.finished_at).where(ScrapeMeta.mode == "full")
        .order_by(ScrapeMeta.finished_at.desc()).limit(1)
    )
    last_full_row = last_full.scalar_one_or_none()
    last_inc = await session.execute(
        select(ScrapeMeta.finished_at).where(ScrapeMeta.mode == "incremental")
        .order_by(ScrapeMeta.finished_at.desc()).limit(1)
    )
    last_inc_row = last_inc.scalar_one_or_none()

    return KBStats(
        total_articles=article_count or 0,
        total_chunks=chroma.get("total_chunks", 0),
        total_images=image_count or 0,
        last_full_sync=last_full_row.isoformat() if last_full_row else None,
        last_incremental_sync=last_inc_row.isoformat() if last_inc_row else None,
    )


@router.get("/articles", response_model=list[ArticleSummary], tags=["Meta"])
async def list_articles(
    session: AsyncSession = Depends(get_session),
    limit: int = 100,
    offset: int = 0,
) -> list[ArticleSummary]:
    result = await session.execute(
        select(Article).order_by(Article.category, Article.title)
        .limit(limit).offset(offset)
    )
    rows = result.scalars().all()
    return [
        ArticleSummary(
            article_id=str(r.id),
            title=r.title,
            url=r.url,
            category=r.category or "",
            folder=r.folder or "",
            last_scraped=r.last_scraped.isoformat() if r.last_scraped else "",
            image_count=r.image_count or 0,
        )
        for r in rows
    ]
