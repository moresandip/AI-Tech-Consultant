"""Agent 3: Feasibility checker — calls Knowledge Brain API.

For each requirement, checks whether it can be solved with an existing
Brilliant Directories setting/feature (no custom dev needed, much cheaper for client)
vs. requiring custom code.

This is the key cost-saving step: a setting that takes 5 minutes to configure
should not be quoted as 10 hours of development.
"""

from __future__ import annotations

import asyncio
import logging
import os

import httpx

logger = logging.getLogger(__name__)

TASK1_API_URL = os.getenv("TASK1_API_URL", "http://localhost:8001")


async def _check_one(client: httpx.AsyncClient, requirement: dict) -> dict:
    """Check a single requirement against the Knowledge Brain."""
    query = f"Does Brilliant Directories have a built-in setting or feature for: {requirement['title']}? {requirement['description']}"

    try:
        resp = await client.post(
            f"{TASK1_API_URL}/api/query",
            json={"question": query, "top_k": 3, "include_images": False},
            timeout=20,
        )
        data = resp.json()
        answer = data.get("answer", "")
        confidence = data.get("confidence", 0.0)
        sources = data.get("sources", [])

        # Heuristic: if answer mentions "setting", "enable", "toggle", "admin panel"
        # and confidence is high, it's likely a built-in feature
        keywords = ["setting", "enable", "toggle", "admin panel", "admin area",
                    "configuration", "built-in", "already available"]
        is_builtin = (
            confidence > 0.55 and
            any(kw.lower() in answer.lower() for kw in keywords)
        )

        return {
            "requirement_title": requirement["title"],
            "can_be_done_with_setting": is_builtin,
            "confidence": round(confidence, 3),
            "kb_answer": answer[:500],
            "kb_sources": [s["url"] for s in sources[:2]],
            "recommendation": (
                "✅ Use existing platform setting — no dev work needed"
                if is_builtin else
                "🔧 Requires custom development"
            ),
        }
    except Exception as exc:
        logger.warning("Feasibility check failed for '%s': %s", requirement["title"], exc)
        return {
            "requirement_title": requirement["title"],
            "can_be_done_with_setting": False,
            "confidence": 0.0,
            "kb_answer": "Could not check Knowledge Brain.",
            "kb_sources": [],
            "recommendation": "🔧 Requires custom development (KB unavailable)",
        }


async def check_feasibility(requirements: list[dict]) -> list[dict]:
    """Check all requirements concurrently. Returns list of feasibility dicts."""
    async with httpx.AsyncClient() as client:
        results = await asyncio.gather(*[_check_one(client, r) for r in requirements])
    return list(results)
