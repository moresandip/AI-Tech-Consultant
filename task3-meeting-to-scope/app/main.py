"""Task 3 — Meeting to Scope of Work: FastAPI entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from app.routes import router
    from app.postgres import init_db
except ImportError:
    from routes import router
    from postgres import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="AI Tech Consultant — Meeting to SOW",
    description=(
        "Multi-agent pipeline that turns client meeting transcripts into "
        "a scope of work, hour estimates, and a client-ready proposal."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(router, prefix="/api")


@app.get("/health", tags=["Meta"])
async def health() -> dict:
    return {"status": "ok", "service": "meeting-sow"}
