"""ChromaDB embedding and retrieval for the Knowledge Brain.

Design decisions:
- Uses ChromaDB's default embedding function (sentence-transformers/all-MiniLM-L6-v2)
  for zero-cost embeddings. Claude is used only at query time for answer synthesis.
- Articles are chunked at ~400 tokens with 50-token overlap to preserve context.
- Image captions are embedded as separate documents so visual answers are retrievable.
- Human-expert answers are also embedded to close knowledge gaps over time.
- The collection name is namespaced so the same ChromaDB can hold multiple products.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from core.settings import settings
from db.models import Article, ArticleChunk, ImageCaption

logger = logging.getLogger(__name__)

COLLECTION_NAME = "brilliant_directories_kb"
CHUNK_SIZE = 400        # target tokens per chunk (approx 1 token ≈ 4 chars)
CHUNK_OVERLAP = 50      # tokens of overlap between consecutive chunks

_chroma_client: chromadb.PersistentClient | None = None
_collection: Any = None


def _get_collection() -> Any:
    global _chroma_client, _collection
    if _collection is None:
        _chroma_client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        _collection = _chroma_client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def get_chroma_stats() -> dict[str, int]:
    col = _get_collection()
    return {"total_chunks": col.count()}


# ─── Text chunking ────────────────────────────────────────────────────────────

def _chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks by approximate word count."""
    words = text.split()
    if not words:
        return []
    
    # Approximate: 1 word ≈ 1.3 tokens
    words_per_chunk = int(chunk_size / 1.3)
    words_overlap = int(overlap / 1.3)
    step = max(1, words_per_chunk - words_overlap)
    
    chunks = []
    for i in range(0, len(words), step):
        chunk = " ".join(words[i: i + words_per_chunk])
        if chunk.strip():
            chunks.append(chunk.strip())
        if i + words_per_chunk >= len(words):
            break
    return chunks


# ─── Upsert ───────────────────────────────────────────────────────────────────

async def upsert_article(
    session: AsyncSession,
    article_data: dict[str, Any],
    image_captions: list[dict[str, Any]],
) -> str:
    """Upsert an article into both Postgres and ChromaDB. Returns article ID."""
    col = _get_collection()

    # Upsert Article row in Postgres
    existing = (await session.execute(
        select(Article).where(Article.url == article_data["url"])
    )).scalar_one_or_none()

    if existing:
        article = existing
        article.title = article_data["title"]
        article.category = article_data.get("category")
        article.folder = article_data.get("folder")
        article.clean_text = article_data.get("clean_text")
        article.content_hash = article_data["content_hash"]
        article.raw_html = article_data.get("raw_html")
        article.last_modified_remote = article_data.get("last_modified_remote")
        article.last_scraped = article_data["last_scraped"]
        article.image_count = len(image_captions)
        article.is_deleted = False
        # Delete old chunks
        for chunk in list(article.chunks):
            await session.delete(chunk)
        # Delete old image captions
        for img in list(article.images):
            await session.delete(img)
    else:
        article = Article(
            url=article_data["url"],
            title=article_data["title"],
            category=article_data.get("category"),
            folder=article_data.get("folder"),
            clean_text=article_data.get("clean_text"),
            content_hash=article_data["content_hash"],
            raw_html=article_data.get("raw_html"),
            last_modified_remote=article_data.get("last_modified_remote"),
            last_scraped=article_data["last_scraped"],
            image_count=len(image_captions),
        )
        session.add(article)

    await session.flush()  # get article.id

    # Remove old ChromaDB entries for this article
    col.delete(where={"article_id": article.id})

    # Chunk and embed text
    text = article_data.get("clean_text") or ""
    chunks = _chunk_text(text)
    chroma_docs = []
    chroma_ids = []
    chroma_metas = []

    for idx, chunk in enumerate(chunks):
        chunk_id = f"{article.id}_chunk_{idx}"
        db_chunk = ArticleChunk(
            article_id=article.id,
            chunk_index=idx,
            text=chunk,
            token_count=int(len(chunk.split()) * 1.3),
        )
        session.add(db_chunk)
        chroma_docs.append(chunk)
        chroma_ids.append(chunk_id)
        chroma_metas.append({
            "article_id": article.id,
            "article_url": article.url,
            "article_title": article.title,
            "category": article.category or "",
            "folder": article.folder or "",
            "chunk_type": "text",
            "chunk_index": idx,
        })

    # Embed image captions
    for img_data in image_captions:
        img_id = f"{article.id}_img_{hash(img_data['image_url']) & 0xFFFFFFFF}"
        caption_text = f"[Screenshot] {img_data['caption']}"
        db_img = ImageCaption(
            article_id=article.id,
            image_url=img_data["image_url"],
            caption=img_data["caption"],
        )
        session.add(db_img)
        chroma_docs.append(caption_text)
        chroma_ids.append(img_id)
        chroma_metas.append({
            "article_id": article.id,
            "article_url": article.url,
            "article_title": article.title,
            "category": article.category or "",
            "folder": article.folder or "",
            "chunk_type": "image_caption",
            "image_url": img_data["image_url"],
        })

    if chroma_docs:
        col.upsert(documents=chroma_docs, ids=chroma_ids, metadatas=chroma_metas)

    logger.info(
        "Upserted '%s' — %d chunks, %d images",
        article.title, len(chunks), len(image_captions)
    )
    return article.id


async def upsert_human_answer(
    task_id: str,
    question: str,
    answer: str,
    source_urls: list[str],
) -> None:
    """Embed a human expert's answer so future queries can find it."""
    col = _get_collection()
    doc_id = f"human_answer_{task_id}"
    col.upsert(
        documents=[f"Q: {question}\nA: {answer}"],
        ids=[doc_id],
        metadatas=[{
            "article_id": task_id,
            "article_url": ", ".join(source_urls),
            "article_title": "Human Expert Answer",
            "category": "human_knowledge",
            "folder": "expert_answers",
            "chunk_type": "human_answer",
            "chunk_index": 0,
        }],
    )
    logger.info("Embedded human answer for task %s", task_id)


async def delete_article(article_id: str) -> None:
    """Remove all ChromaDB entries for a deleted article."""
    col = _get_collection()
    col.delete(where={"article_id": article_id})
    logger.info("Deleted ChromaDB entries for article %s", article_id)


# ─── Retrieval ────────────────────────────────────────────────────────────────

def retrieve_chunks(
    question: str,
    top_k: int = 5,
    include_images: bool = True,
) -> list[dict[str, Any]]:
    """Query ChromaDB and return top-k results with metadata and similarity scores."""
    col = _get_collection()

    where_filter: dict | None = None
    if not include_images:
        where_filter = {"chunk_type": "text"}

    results = col.query(
        query_texts=[question],
        n_results=min(top_k, max(1, col.count())),
        where=where_filter,
        include=["documents", "metadatas", "distances"],
    )

    chunks = []
    documents = results["documents"][0] if results["documents"] else []
    metadatas = results["metadatas"][0] if results["metadatas"] else []
    distances = results["distances"][0] if results["distances"] else []

    for doc, meta, dist in zip(documents, metadatas, distances):
        # ChromaDB cosine distance → similarity score (0..1)
        score = max(0.0, 1.0 - dist)
        chunks.append({
            "text": doc,
            "meta": meta,
            "score": round(score, 4),
        })

    return chunks
