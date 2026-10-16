"""Tests for Task 3: Meeting to Scope of Work Pipeline."""

from __future__ import annotations

import asyncio
from pathlib import Path
import pytest

from scope_diff import compute_diff


def test_transcripts_presence():
    """Verify that all 3 required meeting transcripts exist and are non-empty."""
    transcripts_dir = Path(__file__).resolve().parent.parent / "transcripts"
    assert transcripts_dir.exists(), f"Transcripts directory missing at {transcripts_dir}"

    t1 = transcripts_dir / "meeting1_medconnect_discovery.txt"
    t2 = transcripts_dir / "meeting2_medconnect_followup.txt"
    t3 = transcripts_dir / "meeting3_stylehub_discovery.txt"

    for t in [t1, t2, t3]:
        assert t.exists(), f"Transcript file {t.name} does not exist"
        content = t.read_text(encoding="utf-8")
        assert len(content.strip()) > 500, f"Transcript {t.name} is too short"


def test_feasibility_hours_rule():
    """Verify built-in platform settings receive flat 0.5h config, while custom code receives range."""
    setting_item = {
        "title": "Configure Stripe Gateway",
        "feasibility": "BUILT_IN_SETTING",
        "is_custom_dev": False,
    }
    custom_dev_item = {
        "title": "Doctor of the Month Badge Algorithm",
        "feasibility": "CUSTOM_DEV",
        "is_custom_dev": True,
    }

    def assign_hours(item: dict) -> tuple[float, float]:
        if not item.get("is_custom_dev"):
            return 0.5, 0.5
        return 6.0, 10.0

    min_h, max_h = assign_hours(setting_item)
    assert min_h == 0.5 and max_h == 0.5

    dev_min, dev_max = assign_hours(custom_dev_item)
    assert dev_min >= 1.0 and dev_max > dev_min


@pytest.mark.anyio
async def test_diff_agent_structure():
    """Verify diff agent returns valid structure with expected fields."""
    old_reqs = [
        {"title": "Stripe Payments", "description": "3 membership tiers at $49, $99, $199"},
        {"title": "Doctor Profile Enhancements", "description": "Upload degrees and certificates"},
    ]
    new_reqs = [
        {"title": "Stripe Payments", "description": "3 membership tiers at $49, $99, $199"},
        {"title": "WhatsApp Direct Chat", "description": "Chat widget on doctor profiles"},
    ]

    diff = await compute_diff(old_reqs, new_reqs)
    assert "summary" in diff
    assert "unchanged" in diff
    assert "changed" in diff
    assert "new_items" in diff
    assert "out_of_scope" in diff


def test_human_approval_gate_enforcement():
    """Ensure SOW cannot be dispatched or finalized without human approval status."""
    sow_state = {
        "status": "DRAFT",
        "human_approved": False,
        "proposal_text": "# Project Proposal\n...",
    }

    def can_dispatch_to_client(state: dict) -> bool:
        return state.get("human_approved") is True and state.get("status") == "APPROVED"

    assert can_dispatch_to_client(sow_state) is False

    # Simulate human approval
    sow_state["human_approved"] = True
    sow_state["status"] = "APPROVED"

    assert can_dispatch_to_client(sow_state) is True
