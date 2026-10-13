"""Application settings loaded from environment / .env file."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Anthropic
    anthropic_api_key: str = ""

    # PostgreSQL
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ai_tech_consultant"

    # ChromaDB
    chroma_persist_dir: str = "./chroma_data"

    # Auth
    task1_api_key: str = "dev-secret-task1"

    # Scraper
    scrape_delay_seconds: float = 1.5
    scrape_batch_size: int = 5
    sitemap_url: str = "https://support.brilliantdirectories.com/support/sitemap.xml"

    # Model selection
    model_fast: str = "claude-haiku-4-5"
    model_balanced: str = "claude-sonnet-4-5"
    model_best: str = "claude-opus-4-5"

    # RAG confidence threshold — below this we escalate to human
    confidence_threshold: float = 0.40


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
