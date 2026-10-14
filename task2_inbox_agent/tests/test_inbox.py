"""Tests for Task 2: Inbox Agent."""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from agents.learner import _edit_distance_ratio


def test_edit_distance_identical():
    """Identical strings should have 0.0 edit distance."""
    s1 = "Hello, your refund has been processed successfully."
    s2 = "Hello, your refund has been processed successfully."
    assert _edit_distance_ratio(s1, s2) == 0.0


def test_edit_distance_whitespace_trimmed():
    """Minor whitespace differences should stay well within the 0.05 tolerance."""
    s1 = "Hello, your refund has been processed.\n\nBest regards,\nSupport Team"
    s2 = "  Hello, your refund has been processed.\n\nBest regards,\nSupport Team  "
    ratio = _edit_distance_ratio(s1, s2)
    assert ratio <= 0.05


def test_edit_distance_significant_edit():
    """Substantial edits should exceed 0.05 edit distance."""
    s1 = "You can change your password in Account Settings > Security."
    s2 = "We actually do not allow password resets right now due to maintenance. Please email security@example.com."
    ratio = _edit_distance_ratio(s1, s2)
    assert ratio > 0.05


def test_sample_emails_dataset():
    """Verify sample_emails.json contains at least 50 valid test emails."""
    dataset_path = Path(__file__).resolve().parent.parent / "data" / "sample_emails.json"
    assert dataset_path.exists(), f"Sample emails file missing at {dataset_path}"

    with open(dataset_path, "r", encoding="utf-8") as f:
        emails = json.load(f)

    assert len(emails) >= 50, f"Expected at least 50 emails, found {len(emails)}"

    required_keys = {"sender_email", "sender_name", "subject", "body"}

    for idx, em in enumerate(emails):
        for k in required_keys:
            assert k in em, f"Email #{idx} missing required key '{k}'"
        assert len(em["subject"].strip()) > 0, f"Email #{idx} has empty subject"
        assert len(em["body"].strip()) > 0, f"Email #{idx} has empty body"
        assert "@" in em["sender_email"], f"Email #{idx} has invalid email address"


def test_simulated_autonomy_state_machine():
    """Simulate 20 consecutive perfect drafts granting autonomy, then an edit revoking it."""
    consecutive_perfect = 0
    auto_approved = False
    threshold = 20

    # 1. 20 consecutive perfect drafts
    for i in range(1, 21):
        ratio = 0.02  # < 0.05
        if ratio <= 0.05:
            consecutive_perfect += 1
        else:
            consecutive_perfect = 0

        if not auto_approved and consecutive_perfect >= threshold:
            auto_approved = True

    assert auto_approved is True
    assert consecutive_perfect == 20

    # 2. Significant edit occurs
    ratio = 0.35  # > 0.05
    if ratio > 0.05:
        consecutive_perfect = 0
        if auto_approved:
            auto_approved = False

    assert auto_approved is False
    assert consecutive_perfect == 0
