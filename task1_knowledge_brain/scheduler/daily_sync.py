"""APScheduler-based daily sync scheduler for the Knowledge Brain.

Runs an incremental sync every day at 02:00 UTC so the KB stays fresh
without any manual intervention. Falls back gracefully if the scrape fails.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from core.scraper import run_incremental_scrape

logger = logging.getLogger(__name__)

# Shared status dict — same one used by the /scrape routes
_status_dict: dict = {}


def _run_daily_sync() -> None:
    """Called by APScheduler in a thread; bridges into the async scraper."""
    job_id = str(uuid.uuid4())
    from api.schemas import ScrapeStatus
    _status_dict[job_id] = ScrapeStatus(
        job_id=job_id, status="queued",
        pages_found=0, pages_scraped=0, pages_updated=0,
        pages_failed=0, started_at=None, finished_at=None,
        message="Scheduled daily sync",
    )
    logger.info("Daily sync started (job_id=%s)", job_id)
    try:
        asyncio.run(run_incremental_scrape(job_id, _status_dict))
        logger.info("Daily sync complete (job_id=%s)", job_id)
    except Exception as exc:
        logger.error("Daily sync failed: %s", exc)


def start_scheduler() -> BackgroundScheduler:
    """Create and start the APScheduler instance. Returns the scheduler for shutdown."""
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        _run_daily_sync,
        trigger=CronTrigger(hour=2, minute=0),   # 02:00 UTC daily
        id="daily_kb_sync",
        name="Daily Knowledge Brain Sync",
        replace_existing=True,
        misfire_grace_time=3600,  # allow up to 1h late start
    )
    scheduler.start()
    logger.info("Scheduler started — daily sync at 02:00 UTC")
    return scheduler
