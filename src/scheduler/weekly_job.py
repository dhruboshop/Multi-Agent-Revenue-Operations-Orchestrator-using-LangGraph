"""
APScheduler Weekly Cron Job for Autonomous RevOps Runs.

Features:
- Configurable via SCHEDULER_WEEKLY_CRON
- Uses Redis checkpointing so interrupted runs can resume
- Writes a top-level orchestrator log entry
- Can be triggered manually via API as well
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config.settings import get_settings
from src.graph.orchestrator import invoke_graph
from src.graph.state import create_initial_state

logger = logging.getLogger(__name__)
settings = get_settings()

_scheduler: AsyncIOScheduler | None = None


def _run_weekly_cycle() -> None:
    """The actual job that APScheduler will execute."""
    run_id = str(uuid.uuid4())
    logger.info(f"⏰ Scheduled weekly RevOps run starting — run_id={run_id}")

    try:
        state = create_initial_state(run_id=run_id)
        final_state = invoke_graph(
            initial_state=state,
            thread_id=f"weekly-{run_id}",
            resume=True,  # Will use Redis if available
        )

        duration = final_state.get("run_metadata", {}).get("total_duration_ms", 0)
        logger.info(f"✅ Weekly run {run_id} completed in {duration}ms")

    except Exception as e:
        logger.exception(f"❌ Weekly scheduled run {run_id} failed: {e}")


def start_scheduler() -> None:
    """Start the background APScheduler (idempotent)."""
    global _scheduler

    if _scheduler is not None:
        return

    _scheduler = AsyncIOScheduler(timezone=settings.scheduler_timezone)

    trigger = CronTrigger.from_crontab(
        settings.scheduler_weekly_cron,
        timezone=settings.scheduler_timezone,
    )

    _scheduler.add_job(
        _run_weekly_cycle,
        trigger=trigger,
        id="weekly_revops_briefing",
        name="Weekly Revenue Intelligence Briefing",
        replace_existing=True,
        max_instances=1,
    )

    _scheduler.start()
    logger.info(
        f"APScheduler started — weekly job scheduled with cron '{settings.scheduler_weekly_cron}' "
        f"in timezone {settings.scheduler_timezone}"
    )


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("APScheduler stopped")
