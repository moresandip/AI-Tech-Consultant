"""Agent 1: Transcript chunker and summariser.

Transcripts from client meetings can be very long (1-2 hours = 10,000+ tokens).
Strategy:
- If transcript fits in Claude's context (<150k tokens): process directly.
- If too long: split into overlapping segments, summarise each, then synthesise.

This keeps the full context available to the requirements extractor without
hitting token limits or losing important details from long meetings.
"""

from __future__ import annotations

import logging
import os

import tiktoken
from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL_BALANCED = os.getenv("MODEL_BALANCED", "claude-sonnet-4-5")
MAX_DIRECT_TOKENS = 150_000   # Claude claude-sonnet-4-5 context limit
SEGMENT_SIZE_TOKENS = 30_000
SEGMENT_OVERLAP_TOKENS = 2_000

_enc = tiktoken.get_encoding("cl100k_base")
_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    return _client


def _count_tokens(text: str) -> int:
    return len(_enc.encode(text))


def _split_transcript(text: str) -> list[str]:
    """Split transcript into overlapping token-based segments."""
    tokens = _enc.encode(text)
    segments = []
    step = SEGMENT_SIZE_TOKENS - SEGMENT_OVERLAP_TOKENS
    for i in range(0, len(tokens), step):
        seg_tokens = tokens[i: i + SEGMENT_SIZE_TOKENS]
        segments.append(_enc.decode(seg_tokens))
        if i + SEGMENT_SIZE_TOKENS >= len(tokens):
            break
    return segments


SEGMENT_SUMMARY_PROMPT = """\
You are summarising a segment of a client meeting transcript.
Extract ALL requirements, feature requests, complaints, questions, and decisions mentioned.
Be comprehensive — do not omit any technical detail. Output as plain text.

Transcript segment:
{segment}

Summary of requirements and decisions:"""

SYNTHESIS_PROMPT = """\
You are synthesising summaries from different segments of the same client meeting.
Combine these into one unified, deduplicated list of ALL client requirements and discussion points.

Summaries:
{summaries}

Unified requirements list:"""


async def process_transcript(transcript: str) -> str:
    """Return a clean, complete requirements summary from a transcript.
    
    For short transcripts: returns as-is (the extractor agent will parse it).
    For long transcripts: chunk → summarise each → synthesise.
    """
    token_count = _count_tokens(transcript)
    logger.info("Transcript tokens: %d", token_count)

    if token_count <= MAX_DIRECT_TOKENS:
        logger.info("Transcript fits in context — passing directly.")
        return transcript

    # Long transcript: chunk and summarise
    logger.info("Long transcript — chunking into segments.")
    segments = _split_transcript(transcript)
    claude = _get_client()

    summaries = []
    for i, seg in enumerate(segments):
        logger.info("Summarising segment %d/%d", i + 1, len(segments))
        resp = await claude.messages.create(
            model=MODEL_BALANCED,
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": SEGMENT_SUMMARY_PROMPT.format(segment=seg),
            }],
        )
        summaries.append(f"[Segment {i+1}]\n{resp.content[0].text.strip()}")

    # Synthesise
    combined = "\n\n".join(summaries)
    resp = await claude.messages.create(
        model=MODEL_BALANCED,
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": SYNTHESIS_PROMPT.format(summaries=combined),
        }],
    )
    return resp.content[0].text.strip()
