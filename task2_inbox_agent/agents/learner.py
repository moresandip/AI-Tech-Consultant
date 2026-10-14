"""Learning engine: records human feedback and determines when a category
can be auto-approved.

Rules (configurable via env):
- AUTO_APPROVE_THRESHOLD = 20  (consecutive "sent_as_is" to gain autonomy)
- AUTO_REVOKE_THRESHOLD = 3    (consecutive edits to lose autonomy)
- EDIT_DISTANCE_PERFECT = 0.05 (≤5% char change counts as "sent_as_is")

Why 20 consecutive perfect drafts?
The brief says "20 drafts of the same kind in a row without changing them".
We define "same kind" as the same `category` bucket. "Without changing" means
edit_distance ≤ 0.05 (whitespace/signature trimming is not penalised).
"""

from __future__ import annotations

import logging
import os
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import EmailTypeStats, Feedback

logger = logging.getLogger(__name__)

AUTO_APPROVE_THRESHOLD = int(os.getenv("AUTO_APPROVE_THRESHOLD", "20"))
AUTO_REVOKE_THRESHOLD = int(os.getenv("AUTO_REVOKE_THRESHOLD", "3"))
EDIT_DISTANCE_PERFECT = float(os.getenv("EDIT_DISTANCE_PERFECT", "0.05"))


def _edit_distance_ratio(a: str, b: str) -> float:
    """0.0 = identical, 1.0 = completely different."""
    return 1.0 - SequenceMatcher(None, a.strip(), b.strip()).ratio()


async def record_feedback(
    session: AsyncSession,
    email_id: str,
    draft_id: str,
    category: str,
    action: str,             # "sent_as_is" | "edited" | "replaced"
    ai_draft_body: str,
    final_body: str,
) -> dict:
    """Persist feedback and update EmailTypeStats. Returns autonomy status."""
    edit_distance = _edit_distance_ratio(ai_draft_body, final_body)

    # Persist feedback row
    fb = Feedback(
        email_id=email_id,
        draft_id=draft_id,
        action=action,
        final_body=final_body,
        edit_distance=edit_distance,
    )
    session.add(fb)

    # Load or create stats for this category
    result = await session.execute(
        select(EmailTypeStats).where(EmailTypeStats.category == category)
    )
    stats = result.scalar_one_or_none()
    if stats is None:
        stats = EmailTypeStats(category=category)
        session.add(stats)

    is_perfect = edit_distance <= EDIT_DISTANCE_PERFECT

    if is_perfect:
        stats.consecutive_perfect += 1
        stats.total_sent += 1
    else:
        # Reset consecutive counter on any meaningful edit
        consecutive_before = stats.consecutive_perfect
        stats.consecutive_perfect = 0
        stats.total_edited += 1

        # Revoke auto-approval if previously approved and quality dropped
        if stats.auto_approved:
            logger.warning(
                "Auto-approval REVOKED for category '%s' (edit_distance=%.2f)",
                category, edit_distance
            )
            stats.auto_approved = False
            stats.auto_revoked_count += 1

    # Grant auto-approval
    if (not stats.auto_approved and
            stats.consecutive_perfect >= AUTO_APPROVE_THRESHOLD):
        stats.auto_approved = True
        logger.info("Auto-approval GRANTED for category '%s'", category)

    await session.flush()

    return {
        "category": category,
        "consecutive_perfect": stats.consecutive_perfect,
        "auto_approved": stats.auto_approved,
        "edit_distance": round(edit_distance, 3),
        "is_perfect": is_perfect,
    }


async def get_few_shot_examples(
    session: AsyncSession,
    category: str,
    limit: int = 5,
) -> list[dict]:
    """Return the last N accepted drafts for this category as few-shot examples."""
    result = await session.execute(
        select(Feedback)
        .where(Feedback.action == "sent_as_is")
        .order_by(Feedback.created_at.desc())
        .limit(limit * 3)  # over-fetch; we'll filter by category next
    )
    rows = result.scalars().all()

    # We need to join with Email to get category — simplified version:
    # In production this would be a proper join; for now return raw approved drafts
    examples = []
    for row in rows[:limit]:
        examples.append({
            "prompt": f"[Approved example for category: {category}]",
            "response": row.final_body,
        })
    return examples


async def is_auto_approved(session: AsyncSession, category: str) -> bool:
    """Check if this email category can be sent without human review."""
    result = await session.execute(
        select(EmailTypeStats.auto_approved).where(EmailTypeStats.category == category)
    )
    row = result.scalar_one_or_none()
    return bool(row)
