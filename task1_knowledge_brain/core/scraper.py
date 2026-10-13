"""Polite web scraper for the Brilliant Directories help center.

Design decisions:
- Reads sitemap.xml to discover ALL pages (categories, folders, articles).
- Batches requests with a configurable delay so we never hammer the server.
- Stores a SHA-256 hash of each page's content. On incremental sync we only
  re-process pages whose hash changed or whose lastmod in the sitemap moved.
- Handles HTTP errors and rate-limit responses with exponential backoff (tenacity).
- Articles removed from the sitemap are soft-deleted in the DB and purged from ChromaDB.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from core.embedder import upsert_article, delete_article
from core.settings import settings
from core.vision import caption_images
from db.models import Article, ScrapeMeta
from db.postgres import AsyncSessionLocal

logger = logging.getLogger(__name__)

ARTICLE_URL_PATTERN = re.compile(
    r"support\.brilliantdirectories\.com/support/solutions/articles/\d+"
)
HEADERS = {
    "User-Agent": (
        "AI-Tech-Consultant-Bot/1.0 "
        "(capstone project; contact: student@example.com)"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml",
}


# ─── Sitemap parsing ──────────────────────────────────────────────────────────

async def fetch_sitemap() -> dict[str, datetime | None]:
    """Return {url: lastmod} for every URL in the sitemap."""
    async with httpx.AsyncClient(timeout=30, headers=HEADERS) as client:
        resp = await client.get(settings.sitemap_url)
        resp.raise_for_status()

    NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    root = ET.fromstring(resp.text)
    pages: dict[str, datetime | None] = {}

    for url_el in root.findall("sm:url", NS):
        loc = url_el.findtext("sm:loc", namespaces=NS)
        lastmod_str = url_el.findtext("sm:lastmod", namespaces=NS)
        if not loc:
            continue
        lastmod = None
        if lastmod_str:
            try:
                lastmod = datetime.fromisoformat(lastmod_str)
            except ValueError:
                pass
        pages[loc] = lastmod

    logger.info("Sitemap: %d URLs found", len(pages))
    return pages


def _is_article(url: str) -> bool:
    return bool(ARTICLE_URL_PATTERN.search(url))


# ─── HTTP fetch with retry ────────────────────────────────────────────────────

@retry(
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    stop=stop_after_attempt(4),
    reraise=True,
)
async def _fetch(client: httpx.AsyncClient, url: str) -> httpx.Response:
    resp = await client.get(url)
    if resp.status_code == 429:
        retry_after = int(resp.headers.get("Retry-After", "10"))
        logger.warning("Rate-limited on %s; sleeping %ds", url, retry_after)
        await asyncio.sleep(retry_after)
        resp.raise_for_status()
    resp.raise_for_status()
    return resp


# ─── HTML parsing ─────────────────────────────────────────────────────────────

def _parse_article(html: str, url: str) -> dict[str, Any]:
    """Extract title, clean text, and image URLs from an article page."""
    soup = BeautifulSoup(html, "lxml")

    # Title
    title_el = soup.find("h1") or soup.find("title")
    title = title_el.get_text(strip=True) if title_el else "Untitled"

    # Breadcrumbs → category / folder
    crumbs = [a.get_text(strip=True) for a in soup.select(".breadcrumb a")]
    category = crumbs[1] if len(crumbs) > 1 else None
    folder = crumbs[2] if len(crumbs) > 2 else None

    # Main content
    content_el = (
        soup.select_one(".article-body")
        or soup.select_one(".solution-article-body")
        or soup.select_one("article")
        or soup.find("main")
    )
    clean_text = content_el.get_text(separator="\n", strip=True) if content_el else \
        soup.get_text(separator="\n", strip=True)

    # Images
    img_urls: list[str] = []
    if content_el:
        for img in content_el.find_all("img"):
            src = img.get("src") or img.get("data-src")
            if src:
                img_urls.append(urljoin(url, src))

    return {
        "title": title,
        "category": category,
        "folder": folder,
        "clean_text": clean_text,
        "img_urls": img_urls,
    }


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# ─── Core scrape logic ────────────────────────────────────────────────────────

async def _scrape_one(
    client: httpx.AsyncClient,
    url: str,
    lastmod: datetime | None,
    existing_hash: str | None,
) -> dict[str, Any] | None:
    """Fetch a single article. Returns None if content has not changed."""
    try:
        resp = await _fetch(client, url)
    except Exception as exc:
        logger.error("Failed to fetch %s: %s", url, exc)
        return None

    html = resp.text
    content_hash = _sha256(html)

    if existing_hash and content_hash == existing_hash:
        return None  # unchanged

    parsed = _parse_article(html, url)
    parsed["url"] = url
    parsed["content_hash"] = content_hash
    parsed["raw_html"] = html
    parsed["last_modified_remote"] = lastmod
    parsed["last_scraped"] = datetime.now(tz=timezone.utc)
    return parsed


async def _process_batch(
    client: httpx.AsyncClient,
    batch: list[tuple[str, datetime | None, str | None]],
    job_id: str,
    status_dict: dict,
) -> tuple[int, int, int]:
    """Process a batch of (url, lastmod, existing_hash). Returns (scraped, updated, failed)."""
    scraped = updated = failed = 0
    tasks = [_scrape_one(client, url, lastmod, existing_hash)
             for url, lastmod, existing_hash in batch]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    async with AsyncSessionLocal() as session:
        for (url, lastmod, existing_hash), result in zip(batch, results):
            if isinstance(result, Exception):
                logger.error("Exception scraping %s: %s", url, result)
                failed += 1
                continue
            if result is None:
                scraped += 1
                continue  # unchanged

            scraped += 1
            updated += 1

            # Caption images with Claude (multimodal)
            image_captions = []
            if result["img_urls"]:
                image_captions = await caption_images(result["img_urls"], result["title"])

            # Upsert into ChromaDB + Postgres
            await upsert_article(session, result, image_captions)

        await session.commit()

    return scraped, updated, failed


# ─── Public entry points ──────────────────────────────────────────────────────

async def run_full_scrape(job_id: str, status_dict: dict) -> None:
    """Full scrape: re-processes every article page in the sitemap."""
    _update_status(status_dict, job_id, status="running",
                   started_at=datetime.now(tz=timezone.utc).isoformat())

    sitemap = await fetch_sitemap()
    article_urls = [(u, lm) for u, lm in sitemap.items() if _is_article(u)]
    _update_status(status_dict, job_id, pages_found=len(article_urls))
    logger.info("Full scrape: %d article URLs", len(article_urls))

    total_scraped = total_updated = total_failed = 0
    batch_size = settings.scrape_batch_size

    async with httpx.AsyncClient(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        for i in range(0, len(article_urls), batch_size):
            batch_raw = article_urls[i: i + batch_size]
            batch = [(u, lm, None) for u, lm in batch_raw]  # no existing hash → force refresh
            s, u, f = await _process_batch(client, batch, job_id, status_dict)
            total_scraped += s; total_updated += u; total_failed += f
            _update_status(status_dict, job_id,
                           pages_scraped=total_scraped,
                           pages_updated=total_updated,
                           pages_failed=total_failed)
            await asyncio.sleep(settings.scrape_delay_seconds)

    _finish(status_dict, job_id, total_scraped, total_updated, total_failed)
    await _log_scrape("full", len(article_urls), total_scraped, total_updated, total_failed)


async def run_incremental_scrape(job_id: str, status_dict: dict) -> None:
    """Incremental sync: only processes new or changed pages; soft-deletes removed ones."""
    _update_status(status_dict, job_id, status="running",
                   started_at=datetime.now(tz=timezone.utc).isoformat())

    sitemap = await fetch_sitemap()
    sitemap_article_urls = {u for u in sitemap if _is_article(u)}

    # Load existing articles from DB
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Article.url, Article.content_hash, Article.last_modified_remote)
            .where(Article.is_deleted.is_(False))
        )
        existing: dict[str, tuple[str | None, datetime | None]] = {
            row.url: (row.content_hash, row.last_modified_remote) for row in result
        }

    # Soft-delete removed articles
    removed = set(existing.keys()) - sitemap_article_urls
    if removed:
        async with AsyncSessionLocal() as session:
            for url in removed:
                row = (await session.execute(select(Article).where(Article.url == url))
                       ).scalar_one_or_none()
                if row:
                    row.is_deleted = True
                    await delete_article(str(row.id))
            await session.commit()
        logger.info("Soft-deleted %d removed articles", len(removed))

    # Build list of articles that need re-scraping
    to_scrape: list[tuple[str, datetime | None, str | None]] = []
    for url in sitemap_article_urls:
        lm = sitemap.get(url)
        existing_hash, existing_lm = existing.get(url, (None, None))
        if existing_hash is None:
            to_scrape.append((url, lm, None))  # new article
        elif lm and existing_lm and lm > existing_lm:
            to_scrape.append((url, lm, existing_hash))  # updated
        else:
            to_scrape.append((url, lm, existing_hash))  # check hash anyway

    _update_status(status_dict, job_id, pages_found=len(to_scrape))
    logger.info("Incremental: %d articles to check", len(to_scrape))

    total_scraped = total_updated = total_failed = 0
    async with httpx.AsyncClient(timeout=30, headers=HEADERS, follow_redirects=True) as client:
        for i in range(0, len(to_scrape), settings.scrape_batch_size):
            batch = to_scrape[i: i + settings.scrape_batch_size]
            s, u, f = await _process_batch(client, batch, job_id, status_dict)
            total_scraped += s; total_updated += u; total_failed += f
            _update_status(status_dict, job_id,
                           pages_scraped=total_scraped,
                           pages_updated=total_updated,
                           pages_failed=total_failed)
            await asyncio.sleep(settings.scrape_delay_seconds)

    _finish(status_dict, job_id, total_scraped, total_updated, total_failed)
    await _log_scrape("incremental", len(to_scrape), total_scraped, total_updated, total_failed)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _update_status(d: dict, job_id: str, **kwargs) -> None:
    for k, v in kwargs.items():
        setattr(d[job_id], k, v)


def _finish(d: dict, job_id: str, scraped: int, updated: int, failed: int) -> None:
    s = d[job_id]
    s.status = "done" if failed == 0 else "partial"
    s.pages_scraped = scraped
    s.pages_updated = updated
    s.pages_failed = failed
    s.finished_at = datetime.now(tz=timezone.utc).isoformat()
    logger.info("Scrape %s done. scraped=%d updated=%d failed=%d",
                job_id, scraped, updated, failed)


async def _log_scrape(mode: str, found: int, scraped: int, updated: int, failed: int) -> None:
    async with AsyncSessionLocal() as session:
        session.add(ScrapeMeta(
            mode=mode,
            pages_found=found,
            pages_scraped=scraped,
            pages_updated=updated,
            pages_failed=failed,
            started_at=datetime.now(tz=timezone.utc),
            finished_at=datetime.now(tz=timezone.utc),
        ))
        await session.commit()
