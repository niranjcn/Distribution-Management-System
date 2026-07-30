import asyncio
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.database_sqlalchemy import async_session_factory
from app.services.notification_service import delete_old_notifications
from sqlalchemy import text

logger = logging.getLogger("activity_log_cleanup")

JOB_ID = "activity_log_cleanup"
SCHEDULER: AsyncIOScheduler = None


async def purge_old_activity_logs() -> None:
    """Delete api_activity_logs rows older than ACTIVITY_LOG_RETENTION_DAYS."""
    retention = max(settings.ACTIVITY_LOG_RETENTION_DAYS, 1)
    cutoff = datetime.now().replace(tzinfo=None) - timedelta(days=retention)

    try:
        async with async_session_factory() as session:
            result = await session.execute(
                text("DELETE FROM api_activity_logs WHERE created_at < :cutoff"), {"cutoff": cutoff}
            )
            deleted = result.rowcount
            await session.commit()
        if deleted:
            logger.info("Purged %d activity log rows older than %d days", deleted, retention)
    except Exception:
        logger.exception("Failed to purge old activity logs")


async def purge_old_notifications() -> None:
    """Delete notification rows older than 90 days."""
    try:
        deleted = await delete_old_notifications(days=90)
        if deleted:
            logger.info("Purged %d notification rows older than 90 days", deleted)
    except Exception:
        logger.exception("Failed to purge old notifications")


MANIFEST_RETENTION_DAYS = 90


async def purge_old_manifests() -> None:
    """Delete distribution manifest .xlsx files older than MANIFEST_RETENTION_DAYS."""
    cutoff = datetime.now().replace(tzinfo=None) - timedelta(days=MANIFEST_RETENTION_DAYS)
    manifests_dir = Path(__file__).resolve().parents[2] / "distribution_manifests"
    if not manifests_dir.is_dir():
        return
    try:
        deleted = 0
        for entry in os.scandir(str(manifests_dir)):
            if not entry.name.endswith(".xlsx"):
                continue
            mtime = datetime.fromtimestamp(entry.stat().st_mtime)
            if mtime < cutoff:
                os.remove(entry.path)
                deleted += 1
        if deleted:
            logger.info("Purged %d manifest files older than %d days", deleted, MANIFEST_RETENTION_DAYS)
    except Exception:
        logger.exception("Failed to purge old manifest files")


async def start_activity_log_cleanup_scheduler() -> AsyncIOScheduler:
    global SCHEDULER
    if SCHEDULER and SCHEDULER.running:
        return SCHEDULER

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        purge_old_activity_logs,
        CronTrigger(hour=3, minute=0),
        id=JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        purge_old_notifications,
        CronTrigger(hour=3, minute=5),
        id="notification_cleanup",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        purge_old_manifests,
        CronTrigger(hour=3, minute=10),
        id="manifest_cleanup",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    SCHEDULER = scheduler
    return scheduler


def shutdown_activity_log_cleanup_scheduler() -> None:
    global SCHEDULER
    if SCHEDULER:
        SCHEDULER.shutdown(wait=False)
        SCHEDULER = None
