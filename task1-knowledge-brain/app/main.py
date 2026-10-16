"""Task 1 — Knowledge Brain: FastAPI application entry point."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from contextlib import asynccontextmanager

# Ensure root of task is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import router
from app.postgres import init_db
from ingestion.daily_sync import start_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start DB + scheduler on boot; clean up on shutdown."""
    logger.info("Initialising database …")
    await init_db()
    logger.info("Starting daily-sync scheduler …")
    scheduler = start_scheduler()
    yield
    scheduler.shutdown(wait=False)
    logger.info("Knowledge Brain shut down.")


app = FastAPI(
    title="AI Tech Consultant — Knowledge Brain",
    description=(
        "RAG-powered knowledge base built from the Brilliant Directories help center. "
        "Answers product questions, cites sources, and exposes a clean API for the "
        "Inbox Agent (Task 2) and Meeting→SOW (Task 3)."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/health", tags=["Meta"])
async def health() -> dict:
    return {"status": "ok", "service": "knowledge-brain"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=True)
