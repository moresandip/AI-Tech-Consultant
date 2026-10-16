"""Agent 7: Diff agent — shows what changed between two SOW versions.

For follow-up meetings: compares the new requirement list against the previous
SOW to show:
- New items (not in original)
- Changed items (same title, different scope)
- Out-of-scope items (requested but not in the original agreement)
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


DIFF_PROMPT = """\
You are comparing two sets of project requirements.

ORIGINAL requirements (from first meeting):
{original}

NEW requirements (from follow-up meeting):
{new_requirements}

Classify each new requirement into exactly one of these categories:
- "unchanged": same as original, no change
- "changed": same topic but scope changed (describe the change)
- "new": brand new item not in original
- "out_of_scope": requested item that goes beyond what was originally agreed

Respond ONLY with valid JSON:
{{
  "unchanged": ["title1", "title2"],
  "changed": [{{"title": "...", "original": "...", "new": "...", "change_summary": "..."}}],
  "new_items": [{{"title": "...", "description": "...", "needs_additional_quote": true}}],
  "out_of_scope": [{{"title": "...", "description": "...", "reason": "..."}}],
  "summary": "One sentence describing the key changes from the follow-up meeting"
}}"""


async def compute_diff(
    original_requirements: list[dict],
    new_requirements: list[dict],
) -> dict:
    """Return diff dict showing new, changed, and out-of-scope items."""
    original_text = "\n".join(
        f"- {r['title']}: {r['description']}" for r in original_requirements
    )
    new_text = "\n".join(
        f"- {r['title']}: {r['description']}" for r in new_requirements
    )

    claude = _get_client()
    try:
        resp = await claude.messages.create(
            model=MODEL_BALANCED,
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": DIFF_PROMPT.format(
                    original=original_text,
                    new_requirements=new_text,
                ),
            }],
        )
        text = resp.content[0].text.strip()
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:-1])
        return json.loads(text)
    except Exception as exc:
        logger.error("Diff computation failed: %s", exc)
        return {
            "unchanged": [],
            "changed": [],
            "new_items": [{"title": r["title"], "description": r["description"],
                           "needs_additional_quote": True}
                          for r in new_requirements],
            "out_of_scope": [],
            "summary": "Could not compute diff — treating all new items as additions.",
        }
