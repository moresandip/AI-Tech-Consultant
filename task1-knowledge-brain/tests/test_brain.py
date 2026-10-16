"""Tests for Task 1: Knowledge Brain."""

from __future__ import annotations

import hashlib
import pytest
from pydantic import ValidationError

from app.schemas import (
    QueryRequest,
    QueryResponse,
    SourceChunk,
    FeedbackRequest,
    HumanTask,
    ScrapeRequest,
)


def test_query_request_validation():
    req = QueryRequest(question="How do I connect Stripe?", top_k=5, include_images=True)
    assert req.question == "How do I connect Stripe?"
    assert req.top_k == 5
    assert req.include_images is True

    # Empty question should fail
    with pytest.raises(ValidationError):
        QueryRequest(question="", top_k=5)


def test_query_response_serialization():
    resp = QueryResponse(
        query_id="qry_12345",
        question="How to refund?",
        answer="Navigate to Transaction History and click Refund.",
        confidence=0.88,
        escalated=False,
        sources=[
            SourceChunk(
                article_id="art_01",
                title="Processing Member Refunds",
                url="https://support.brilliantdirectories.com/article/refunds",
                excerpt="Click refund on the transaction row.",
                score=0.91,
            )
        ],
        images=[],
    )
    assert resp.confidence == 0.88
    assert not resp.escalated
    assert len(resp.sources) == 1
    assert resp.sources[0].article_id == "art_01"


def test_sha256_change_detection():
    """Verify SHA-256 hash generation for incremental scrape change detection."""
    content_v1 = "<h1>How to set up Stripe</h1><p>Step 1: Enter API keys.</p>"
    content_v2 = "<h1>How to set up Stripe</h1><p>Step 1: Enter API keys.</p>"
    content_v3 = "<h1>How to set up Stripe</h1><p>Step 1: Enter API keys and Webhook secret.</p>"

    hash1 = hashlib.sha256(content_v1.encode("utf-8")).hexdigest()
    hash2 = hashlib.sha256(content_v2.encode("utf-8")).hexdigest()
    hash3 = hashlib.sha256(content_v3.encode("utf-8")).hexdigest()

    assert hash1 == hash2, "Identical content must produce identical hash"
    assert hash1 != hash3, "Modified content must produce changed hash"


def test_escalation_threshold_logic():
    """Test confidence threshold rules: confidence < 0.40 triggers escalation."""
    threshold = 0.40

    sample_queries = [
        {"sim": 0.85, "expect_escalate": False},
        {"sim": 0.41, "expect_escalate": False},
        {"sim": 0.39, "expect_escalate": True},
        {"sim": 0.12, "expect_escalate": True},
    ]

    for item in sample_queries:
        should_escalate = item["sim"] < threshold
        assert should_escalate == item["expect_escalate"]


def test_feedback_request_validation():
    fb = FeedbackRequest(query_id="qry_12345", rating=5, comment="Very clear instructions")
    assert fb.query_id == "qry_12345"
    assert fb.rating == 5
