"""Agent 2: Requirements extractor.

Converts a processed transcript/summary into a structured list of requirements
using Claude claude-sonnet-4-5 with strict JSON output.

Each requirement has:
- title: short name (5 words max)
- description: what the client wants in plain English
- type: "feature" | "fix" | "content" | "integration" | "design"
- priority: "must-have" | "nice-to-have" | "question"
- vague: bool — is this too vague to estimate? (e.g. "make search better")
- clarifying_question: if vague, what should we ask?
"""

from __future__ import annotations

import json
import logging
import os

from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL_BALANCED = os.getenv("MODEL_BALANCED", "claude-sonnet-4-5")

_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    return _client


EXTRACT_PROMPT = """\
You are a senior technical consultant extracting requirements from a client meeting.

Analyse the meeting content below and extract ALL client requirements, feature requests, and action items.
For each requirement, flag if it is too vague to estimate (e.g. "improve performance", "make it better").

Respond with ONLY valid JSON — no markdown, no explanation.

Format:
{{
  "requirements": [
    {{
      "title": "Short title (max 6 words)",
      "description": "What the client wants, in plain English",
      "type": "feature | fix | content | integration | design",
      "priority": "must-have | nice-to-have | question",
      "vague": true | false,
      "clarifying_question": "Question to ask if vague, else null"
    }}
  ],
  "client_goals": "One sentence describing the overall project goal",
  "deadline_mentioned": "Deadline if mentioned, else null",
  "budget_mentioned": "Budget if mentioned, else null"
}}

Meeting content:
{transcript}"""


async def extract_requirements(processed_transcript: str) -> dict:
    """Return structured requirements dict from processed transcript."""
    claude = _get_client()
    try:
        resp = await claude.messages.create(
            model=MODEL_BALANCED,
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": EXTRACT_PROMPT.format(transcript=processed_transcript[:80000]),
            }],
        )
        text = resp.content[0].text.strip()
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:-1])
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error("JSON parse error in requirements: %s", e)
        return {"requirements": [], "client_goals": "", "deadline_mentioned": None,
                "budget_mentioned": None}
    except Exception as exc:
        logger.error("Requirements extraction failed: %s", exc)
        return {"requirements": [], "client_goals": "", "deadline_mentioned": None,
                "budget_mentioned": None}
