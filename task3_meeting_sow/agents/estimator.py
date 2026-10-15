"""Agent 4: Hour estimator.

For each requirement that needs custom development (not a platform setting),
generates a min/max hour estimate using Claude claude-sonnet-4-5.

Settings-based items get a fixed 0.5h (configuration time).
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


ESTIMATE_PROMPT = """\
You are an experienced Brilliant Directories developer estimating development hours.
The platform is a PHP/MySQL SaaS with extensive hooks and API.

Estimate each task below. Be realistic — include time for testing, QA, and deployment.
For simple setting changes: 0.5h. For new integrations: 8-20h. For custom features: 4-16h.

Respond with ONLY valid JSON (no markdown):
{{
  "tasks": [
    {{
      "task": "Task name",
      "type": "configuration | integration | custom_feature | content | design",
      "hours_min": 2,
      "hours_max": 4,
      "notes": "What this estimate includes"
    }}
  ]
}}

Tasks to estimate:
{tasks_text}"""


async def estimate_hours(
    requirements: list[dict],
    feasibility: list[dict],
) -> list[dict]:
    """Return a task list with hour estimates."""
    # Map feasibility by title
    feasibility_map = {f["requirement_title"]: f for f in feasibility}

    tasks_to_estimate = []
    quick_tasks = []

    for req in requirements:
        feat = feasibility_map.get(req["title"], {})
        if feat.get("can_be_done_with_setting"):
            quick_tasks.append({
                "task": req["title"],
                "type": "configuration",
                "hours_min": 0.25,
                "hours_max": 0.5,
                "notes": "Platform setting — configuration only. " + feat.get("recommendation", ""),
            })
        else:
            tasks_to_estimate.append(
                f"- {req['title']}: {req['description']} (type: {req['type']})"
            )

    if not tasks_to_estimate:
        return quick_tasks

    tasks_text = "\n".join(tasks_to_estimate)
    claude = _get_client()
    try:
        resp = await claude.messages.create(
            model=MODEL_BALANCED,
            max_tokens=2048,
            messages=[{
                "role": "user",
                "content": ESTIMATE_PROMPT.format(tasks_text=tasks_text),
            }],
        )
        text = resp.content[0].text.strip()
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:-1])
        estimated = json.loads(text)
        return quick_tasks + estimated.get("tasks", [])
    except Exception as exc:
        logger.error("Hour estimation failed: %s", exc)
        return quick_tasks + [
            {"task": t, "type": "custom_feature", "hours_min": 4, "hours_max": 8,
             "notes": "Estimate unavailable"}
            for t in tasks_to_estimate
        ]
