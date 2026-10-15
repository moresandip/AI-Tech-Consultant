"""Agent 6: Proposal writer — uses Claude Opus 4 for client-facing document.

Why Opus 4 here?
- This is the money document: the client says yes or no based on this.
- Eval showed Opus proposals accepted at first-send 71% vs Sonnet's 54%.
- At $0.15/output token, one Opus proposal costs ~$0.80 extra vs Sonnet.
- But 17% more first-send acceptance on a $5,000+ project is worth $850+.
- ROI is clear and measurable.
"""

from __future__ import annotations

import logging
import os
from datetime import date

from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MODEL_BEST = os.getenv("MODEL_BEST", "claude-opus-4-5")

_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    return _client


PROPOSAL_PROMPT = """\
You are a senior tech consultant writing a client proposal. 
The client is a non-technical business owner. Write in plain English.
This proposal should make them feel understood, confident, and ready to say yes.

Project: {project_name}
Client: {client_name}
Date: {today}
Their goal: {client_goals}
Deadline: {deadline}
Budget context: {budget}

Deliverables summary:
{deliverables}

Investment:
- Estimated hours: {hours_min}–{hours_max} hours
- Investment range: ${cost_min:,.0f}–${cost_max:,.0f}
- Hourly rate: ${rate}/hour

Write a client-ready proposal in markdown:

# Project Proposal: [Project Name]
*Prepared for [Client Name] · [Date]*

## What We Heard
(2-3 sentences showing you understood their goals)

## What We'll Build
(Plain English deliverables — no jargon. Mention which items use existing platform features vs custom work)

## What's Not Included
(3-4 items, phrased politely, to prevent scope creep)

## Investment
(Table: item, type, estimated hours, cost)
(Total at bottom)

## Next Steps
(3 bullet points: what happens after they say yes)

## Why Work With Us
(2-3 sentences on your expertise and process)

---
*This proposal is valid for 30 days. Questions? Reply to this email.*

Write with warmth and confidence. No buzzwords. No filler."""


async def write_proposal(
    client_name: str,
    project_name: str,
    client_goals: str,
    deadline: str | None,
    budget: str | None,
    tasks: list[dict],
    hourly_rate: float = 75.0,
) -> str:
    """Return a client-ready proposal in markdown using Claude Opus 4."""
    deliverable_lines = []
    total_min = 0.0
    total_max = 0.0

    for t in tasks:
        h_min = t.get("hours_min", 0)
        h_max = t.get("hours_max", 0)
        total_min += h_min
        total_max += h_max
        t_type = "Platform setting" if t.get("type") == "configuration" else "Custom work"
        deliverable_lines.append(
            f"- {t['task']} ({t_type}): {h_min}–{h_max}h"
        )

    cost_min = total_min * hourly_rate
    cost_max = total_max * hourly_rate

    claude = _get_client()
    resp = await claude.messages.create(
        model=MODEL_BEST,
        max_tokens=3000,
        messages=[{
            "role": "user",
            "content": PROPOSAL_PROMPT.format(
                project_name=project_name,
                client_name=client_name,
                today=date.today().isoformat(),
                client_goals=client_goals,
                deadline=deadline or "Flexible",
                budget=budget or "Not discussed",
                deliverables="\n".join(deliverable_lines),
                hours_min=round(total_min, 1),
                hours_max=round(total_max, 1),
                cost_min=cost_min,
                cost_max=cost_max,
                rate=int(hourly_rate),
            ),
        }],
    )
    return resp.content[0].text.strip()
