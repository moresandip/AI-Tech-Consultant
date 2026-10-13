"""RAG answer synthesis using Claude claude-sonnet-4-5.

Flow:
  1. Retrieve top-k chunks from ChromaDB (embedder.retrieve_chunks)
  2. Separate text chunks from image caption chunks
  3. Call Claude claude-sonnet-4-5 with the question + retrieved context
  4. If confidence < threshold → escalate to human task
  5. Log everything to QueryLog for evals
"""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone

from anthropic import AsyncAnthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import ImageResult, QueryRequest, QueryResponse, SourceChunk
from core.embedder import retrieve_chunks
from core.settings import settings
from db.models import HumanTaskModel, PromptVersion, QueryLog

logger = logging.getLogger(__name__)

_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


# ─── Prompt versioning ────────────────────────────────────────────────────────

ANSWER_PROMPT_KEY = "knowledge_brain_answer_v1"
ANSWER_PROMPT_DEFAULT = """\
You are a helpful support assistant for Brilliant Directories, a software platform for building directory websites.

Answer the user's question using ONLY the context provided below. 
- Be specific and actionable.
- If the context includes a screenshot description, mention what the user will see.
- If the context does not contain enough information to answer, say exactly: "I don't have enough information to answer this question."
- Always end with the article titles you used, formatted as: Sources: [Title 1], [Title 2]

Context:
{context}

Question: {question}

Answer:"""


async def _get_active_prompt(session: AsyncSession, key: str, default: str) -> str:
    result = await session.execute(
        select(PromptVersion)
        .where(PromptVersion.prompt_key == key, PromptVersion.is_active.is_(True))
        .order_by(PromptVersion.version.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if row:
        return row.content
    # Store the default so it appears in version history
    session.add(PromptVersion(
        prompt_key=key, version=1, content=default, is_active=True
    ))
    return default


# ─── Main answer function ─────────────────────────────────────────────────────

async def answer_question(body: QueryRequest, session: AsyncSession) -> QueryResponse:
    query_id = str(uuid.uuid4())
    start = time.monotonic()

    # 1. Retrieve
    chunks = retrieve_chunks(body.question, top_k=body.top_k,
                             include_images=body.include_images)

    # 2. Separate text chunks from image captions
    text_chunks = [c for c in chunks if c["meta"].get("chunk_type") != "image_caption"]
    image_chunks = [c for c in chunks if c["meta"].get("chunk_type") == "image_caption"]

    best_score = chunks[0]["score"] if chunks else 0.0

    # 3. Build context string
    context_parts = []
    for c in text_chunks[:5]:
        title = c["meta"].get("article_title", "Unknown")
        context_parts.append(f"### {title}\n{c['text']}")
    for c in image_chunks[:3]:
        title = c["meta"].get("article_title", "Unknown")
        context_parts.append(f"### Screenshot from: {title}\n{c['text']}")
    context = "\n\n".join(context_parts) or "No relevant articles found."

    # 4. Load active prompt
    prompt_template = await _get_active_prompt(session, ANSWER_PROMPT_KEY, ANSWER_PROMPT_DEFAULT)
    prompt = prompt_template.format(context=context, question=body.question)

    # 5. Call Claude
    claude = _get_client()
    escalated = False
    human_task_id = None
    answer = ""
    input_tokens = output_tokens = 0

    if best_score < settings.confidence_threshold:
        # Not enough context — escalate
        escalated = True
        answer = (
            "I don't have enough information to answer this confidently. "
            "A human expert has been notified and will respond shortly."
        )
        task = HumanTaskModel(
            question=body.question,
            query_log_id=query_id,
        )
        session.add(task)
        await session.flush()
        human_task_id = str(task.id)
    else:
        try:
            response = await claude.messages.create(
                model=settings.model_balanced,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            answer = response.content[0].text.strip()
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
        except Exception as exc:
            logger.error("Claude call failed: %s", exc)
            answer = "I encountered an error. Please try again."

    latency_ms = int((time.monotonic() - start) * 1000)

    # 6. Build sources list
    seen_articles: set[str] = set()
    sources: list[SourceChunk] = []
    images: list[ImageResult] = []

    for c in text_chunks:
        aid = c["meta"].get("article_id", "")
        if aid not in seen_articles:
            seen_articles.add(aid)
            sources.append(SourceChunk(
                article_id=aid,
                title=c["meta"].get("article_title", ""),
                url=c["meta"].get("article_url", ""),
                excerpt=c["text"][:200],
                score=c["score"],
            ))

    for c in image_chunks:
        images.append(ImageResult(
            image_url=c["meta"].get("image_url", ""),
            caption=c["text"].replace("[Screenshot] ", ""),
            article_id=c["meta"].get("article_id", ""),
            article_title=c["meta"].get("article_title", ""),
        ))

    # 7. Log
    session.add(QueryLog(
        id=query_id,
        question=body.question,
        answer=answer,
        confidence=best_score,
        sources=[s.model_dump() for s in sources],
        escalated=escalated,
        model_used=settings.model_balanced,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    ))

    return QueryResponse(
        query_id=query_id,
        question=body.question,
        answer=answer,
        confidence=best_score,
        sources=sources,
        images=images,
        escalated=escalated,
        human_task_id=human_task_id,
    )
