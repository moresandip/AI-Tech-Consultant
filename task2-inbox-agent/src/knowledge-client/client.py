"""Knowledge Brain API client for Task 2 Inbox Agent.

Calls Task 1's `/api/query` endpoint.
Tasks 2 and 3 NEVER touch Task 1's database or ChromaDB directly.
"""

from __future__ import annotations

import logging
import os
from typing import Any
import httpx

logger = logging.getLogger(__name__)

TASK1_API_URL = os.getenv("TASK1_API_URL", "http://localhost:8001")
TASK1_API_KEY = os.getenv("TASK1_API_KEY", "dev-secret-task1")


class KnowledgeClient:
    """Async client for querying the Task 1 Knowledge Brain."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = (base_url or TASK1_API_URL).rstrip("/")
        self.api_key = api_key or TASK1_API_KEY

    async def query(
        self,
        question: str,
        top_k: int = 3,
        include_images: bool = True,
    ) -> dict[str, Any]:
        """Query the Knowledge Brain for facts and source articles."""
        url = f"{self.base_url}/api/query"
        headers = {"X-API-Key": self.api_key}
        payload = {
            "question": question,
            "top_k": top_k,
            "include_images": include_images,
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    return resp.json()
                logger.warning("KB query returned status %d: %s", resp.status_code, resp.text)
        except Exception as exc:
            logger.warning("Failed to reach Knowledge Brain at %s: %s", url, exc)

        # Fallback response if KB is offline
        return {
            "answer": "No knowledge base context available at this moment.",
            "sources": [],
            "confidence": 0.0,
            "escalated": False,
        }


# Convenience singleton
knowledge_client = KnowledgeClient()
