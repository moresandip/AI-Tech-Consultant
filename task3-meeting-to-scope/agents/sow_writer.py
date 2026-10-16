"""Agent 5: SOW writer — produces the internal scope of work document.

This is for the development team, not the client.
Clear, precise, technical markdown.
"""

from __future__ import annotations

import logging
import os
from datetime import date

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


SOW_PROMPT = """\
Write an internal Scope of Work document for the development team.

Project: {project_name}
Client: {client_name}
Date: {today}
Goal: {client_goals}
Deadline: {deadline}

Requirements and feasibility:
{requirements_text}

Task list with estimates:
{tasks_text}

Write a professional SOW in markdown with these sections:
# Scope of Work: [Project Name]
## Project Overview
## In Scope
(numbered list of deliverables with hours and type: setting/dev)
## Out of Scope  
(list 3-5 common scope creep areas to explicitly exclude)
## Technical Notes
(implementation approach for custom dev items)
## Timeline
(estimated based on hours, assuming 6h productive dev/day)
## Total Estimate
(table: min hours, max hours, min cost at $RATE/h, max cost)

Be precise. Write for a senior developer who will read this before starting."""


async def write_sow(
    client_name: str,
    project_name: str,
    client_goals: str,
    deadline: str | None,
    requirements: list[dict],
    feasibility: list[dict],
    tasks: list[dict],
    hourly_rate: float = 75.0,
) -> str:
    """Return a markdown SOW document."""
    feasibility_map = {f["requirement_title"]: f for f in feasibility}

    req_lines = []
    for r in requirements:
        f = feasibility_map.get(r["title"], {})
        status = "✅ Setting" if f.get("can_be_done_with_setting") else "🔧 Dev"
        req_lines.append(f"- [{status}] **{r['title']}**: {r['description']}")

    task_lines = []
    total_min = 0.0
    total_max = 0.0
    for t in tasks:
        h_min = t.get("hours_min", 0)
        h_max = t.get("hours_max", 0)
        total_min += h_min
        total_max += h_max
        task_lines.append(
            f"- **{t['task']}** ({t['type']}): {h_min}–{h_max}h | {t.get('notes', '')}"
        )

    claude = _get_client()
    resp = await claude.messages.create(
        model=MODEL_BALANCED,
        max_tokens=3000,
        messages=[{
            "role": "user",
            "content": SOW_PROMPT.format(
                project_name=project_name,
                client_name=client_name,
                today=date.today().isoformat(),
                client_goals=client_goals,
                deadline=deadline or "Not specified",
                requirements_text="\n".join(req_lines),
                tasks_text="\n".join(task_lines),
            ).replace("$RATE", str(int(hourly_rate))),
        }],
    )
    return resp.content[0].text.strip()
