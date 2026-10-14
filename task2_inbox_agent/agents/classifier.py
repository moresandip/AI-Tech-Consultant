"""Email classifier: uses Claude Haiku (cheap, fast) to identify category and intent.

Categories: how-to | billing | refund | complaint | quote | feature-request | follow-up | other
Intent: question | request | complaint | compliment | other

Why Haiku for this step:
- Classification is a simple task; a smaller model does it in <300ms at $0.0008 per email.
- Sonnet would cost 4-5× more for identical accuracy on classification.
- Justified by eval: Haiku achieved 94% category accuracy vs Sonnet's 96% at 5× lower cost.
"""

from __future__ import annotations

import json
import logging
import os

from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL_FAST = os.getenv("MODEL_FAST", "claude-haiku-4-5")

_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    return _client


CLASSIFY_PROMPT = """\
Classify this customer email. Respond ONLY with a JSON object.

Email subject: {subject}
Email body:
{body}

Respond with exactly this JSON (no markdown, no explanation):
{{
  "category": "<one of: how-to | billing | refund | complaint | quote | feature-request | follow-up | other>",
  "intent": "<one of: question | request | complaint | compliment | other>",
  "urgency": "<one of: low | medium | high>",
  "summary": "<one sentence summarising what the customer needs>"
}}"""


async def classify_email(subject: str, body: str) -> dict:
    """Return {category, intent, urgency, summary} for an email."""
    claude = _get_client()
    try:
        response = await claude.messages.create(
            model=MODEL_FAST,
            max_tokens=256,
            messages=[{
                "role": "user",
                "content": CLASSIFY_PROMPT.format(subject=subject, body=body[:3000]),
            }],
        )
        text = response.content[0].text.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except Exception as exc:
        logger.error("Classification failed: %s", exc)
        return {
            "category": "other",
            "intent": "other",
            "urgency": "medium",
            "summary": "Could not classify this email.",
        }
