"""Claude multimodal image captioning for help-center screenshots.

Every image found in an article is downloaded and sent to Claude claude-sonnet-4-5
along with the article title for context. The caption is stored in Postgres and
also embedded into ChromaDB so that image-based answers can be retrieved.

Design: we batch images in groups of 5 to stay within Claude's context limits
and to keep cost reasonable. Each caption is ~50-100 tokens.
"""

from __future__ import annotations

import asyncio
import base64
import logging
from io import BytesIO
from typing import Any

import httpx
from anthropic import AsyncAnthropic
from PIL import Image

from core.settings import settings

logger = logging.getLogger(__name__)

_client: AsyncAnthropic | None = None


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _client


CAPTION_PROMPT = """You are analysing a screenshot from the Brilliant Directories help center.
Article title: "{title}"

Describe what this screenshot shows in 1-3 sentences. Focus on:
- What UI elements are visible (buttons, menus, fields, toggles)
- What action the screenshot is demonstrating
- Any important settings or values shown

Be specific. A support agent should be able to answer a customer question using only your caption."""


async def _fetch_image_b64(client: httpx.AsyncClient, url: str) -> tuple[str, str] | None:
    """Download an image and return (base64_data, media_type). Returns None on failure."""
    try:
        resp = await client.get(url, timeout=15)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "image/png").split(";")[0].strip()

        # Resize to max 1024px on longest side (saves tokens)
        img = Image.open(BytesIO(resp.content))
        max_dim = 1024
        if max(img.size) > max_dim:
            ratio = max_dim / max(img.size)
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)

        buf = BytesIO()
        fmt = "PNG" if "png" in content_type else "JPEG"
        img.save(buf, format=fmt)
        b64 = base64.standard_b64encode(buf.getvalue()).decode()
        media_type = "image/png" if fmt == "PNG" else "image/jpeg"
        return b64, media_type
    except Exception as exc:
        logger.warning("Could not fetch image %s: %s", url, exc)
        return None


async def caption_images(
    img_urls: list[str],
    article_title: str,
    batch_size: int = 5,
) -> list[dict[str, Any]]:
    """Caption a list of image URLs. Returns list of {image_url, caption}."""
    if not img_urls:
        return []

    results: list[dict[str, Any]] = []
    claude = _get_client()

    async with httpx.AsyncClient(follow_redirects=True,
                                  headers={"User-Agent": "AI-Tech-Consultant-Bot/1.0"}) as client:
        for i in range(0, len(img_urls), batch_size):
            batch = img_urls[i: i + batch_size]
            # Fetch all images in the batch concurrently
            fetched = await asyncio.gather(*[_fetch_image_b64(client, u) for u in batch])

            for url, img_data in zip(batch, fetched):
                if img_data is None:
                    continue
                b64, media_type = img_data

                try:
                    response = await claude.messages.create(
                        model=settings.model_balanced,
                        max_tokens=256,
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "image",
                                        "source": {
                                            "type": "base64",
                                            "media_type": media_type,
                                            "data": b64,
                                        },
                                    },
                                    {
                                        "type": "text",
                                        "text": CAPTION_PROMPT.format(title=article_title),
                                    },
                                ],
                            }
                        ],
                    )
                    caption = response.content[0].text.strip()
                    results.append({"image_url": url, "caption": caption})
                    logger.debug("Captioned %s: %s…", url, caption[:60])
                except Exception as exc:
                    logger.error("Caption failed for %s: %s", url, exc)

    return results
