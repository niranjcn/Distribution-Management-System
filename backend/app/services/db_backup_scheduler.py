import asyncio
import calendar
import gzip
import logging
import os
import shutil
from datetime import datetime, time
from pathlib import Path
from typing import Optional, Dict, Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.database import get_db
import pymysql

logger = logging.getLogger(__name__)

BACKUP_ROOT = Path(__file__).resolve().parents[2] / "db_backups"
BACKUP_ROOT.mkdir(parents=True, exist_ok=True)

SCHEDULE_LOCK = asyncio.Lock()
SCHEDULER: Optional[AsyncIOScheduler] = None
JOB_ID = "db_backup_job"


def _parse_time_of_day(value: str) -> time:
    try:
        parts = value.strip().split(":", 1)
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError
        return time(hour=hour, minute=minute)
    except Exception:
        return time(hour=2, minute=0)


def _normalize_time_of_day(value: str) -> str:
    try:
        parts = value.strip().split(":", 1)
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError
        return f"{hour:02d}:{minute:02d}"
    except Exception as exc:
        raise ValueError("time_of_day must be in HH:MM (24h) format") from exc


def _normalize_schedule(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "frequency": row.get("frequency"),
        "day_of_week": row.get("day_of_week"),
        "day_of_month": row.get("day_of_month"),
        "time_of_day": row.get("time_of_day"),
        "last_run_at": row.get("last_run_at"),
        "updated_at": row.get("updated_at"),
    }


async def _ensure_schedule(db) -> Dict[str, Any]:
    try:
        cursor = await db.execute(
            "SELECT frequency, day_of_week, day_of_month, time_of_day, last_run_at, updated_at "
            "FROM backup_schedules LIMIT 1"
        )
        row = await cursor.fetchone()
    except pymysql.err.ProgrammingError as exc:
        if exc.args and exc.args[0] == 1146:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS backup_schedules (
                    id INT PRIMARY KEY,
                    frequency VARCHAR(16) NOT NULL,
                    day_of_week INT NULL,
                    day_of_month INT NULL,
                    time_of_day VARCHAR(5) NOT NULL,
                    last_run_at VARCHAR(64),
                    updated_at VARCHAR(64) NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )
            await db.commit()
            cursor = await db.execute(
                "SELECT frequency, day_of_week, day_of_month, time_of_day, last_run_at, updated_at "
                "FROM backup_schedules LIMIT 1"
            )
            row = await cursor.fetchone()
        else:
            raise
    if row:
        return row

    now = datetime.now().replace(microsecond=0).isoformat()
    await db.execute(
        "INSERT IGNORE INTO backup_schedules "
        "(id, frequency, day_of_week, day_of_month, time_of_day, last_run_at, updated_at) "
        "VALUES (1, ?, ?, ?, ?, ?, ?)",
        ("daily", None, None, settings.DB_BACKUP_TIME, None, now),
    )
    await db.commit()

    cursor = await db.execute(
        "SELECT frequency, day_of_week, day_of_month, time_of_day, last_run_at, updated_at "
        "FROM backup_schedules LIMIT 1"
    )
    row = await cursor.fetchone()
    return row or {
        "frequency": "daily",
        "day_of_week": None,
        "day_of_month": None,
        "time_of_day": settings.DB_BACKUP_TIME,
        "last_run_at": None,
        "updated_at": now,
    }


async def get_db_backup_schedule() -> Dict[str, Any]:
    async with get_db() as db:
        row = await _ensure_schedule(db)
        return _normalize_schedule(row)


async def update_db_backup_schedule(payload: Dict[str, Any]) -> Dict[str, Any]:
    frequency = str(payload.get("frequency") or "").strip().lower()
    if frequency not in {"daily", "weekly", "monthly"}:
        raise ValueError("Invalid frequency")

    day_of_week = payload.get("day_of_week")
    day_of_month = payload.get("day_of_month")
    time_of_day = payload.get("time_of_day")

    async with get_db() as db:
        current = await _ensure_schedule(db)

    if not time_of_day:
        time_of_day = current.get("time_of_day") or settings.DB_BACKUP_TIME

    time_of_day = _normalize_time_of_day(str(time_of_day))

    if frequency == "weekly":
        if day_of_week is None:
            raise ValueError("day_of_week is required for weekly backups")
        day_of_week = int(day_of_week)
        if day_of_week < 0 or day_of_week > 6:
            raise ValueError("day_of_week must be between 0 (Mon) and 6 (Sun)")
        day_of_month = None
    elif frequency == "monthly":
        if day_of_month is None:
            raise ValueError("day_of_month is required for monthly backups")
        day_of_month = int(day_of_month)
        if day_of_month < 1 or day_of_month > 31:
            raise ValueError("day_of_month must be between 1 and 31")
        day_of_week = None
    else:
        day_of_week = None
        day_of_month = None

    now = datetime.now().replace(microsecond=0).isoformat()

    async with get_db() as db:
        await _ensure_schedule(db)
        await db.execute(
            "UPDATE backup_schedules "
            "SET frequency = ?, day_of_week = ?, day_of_month = ?, time_of_day = ?, updated_at = ? "
            "WHERE id = 1",
            (frequency, day_of_week, day_of_month, time_of_day, now),
        )
        await db.commit()

    reschedule_db_backup_job(time_of_day)

    return await get_db_backup_schedule()


def _target_month_day(now: datetime, day_of_month: int) -> int:
    last_day = calendar.monthrange(now.year, now.month)[1]
    return min(day_of_month, last_day)


def _already_ran_today(last_run_at: Optional[str], now: datetime) -> bool:
    if not last_run_at:
        return False
    try:
        last = datetime.fromisoformat(last_run_at)
    except Exception:
        return False
    return last.date() == now.date()


def _is_backup_due(schedule: Dict[str, Any], now: datetime) -> bool:
    if _already_ran_today(schedule.get("last_run_at"), now):
        return False

    schedule_time = _parse_time_of_day(schedule.get("time_of_day") or settings.DB_BACKUP_TIME)
    if now.hour != schedule_time.hour or now.minute != schedule_time.minute:
        return False

    frequency = (schedule.get("frequency") or "").lower()
    if frequency == "daily":
        return True
    if frequency == "weekly":
        return schedule.get("day_of_week") == now.weekday()
    if frequency == "monthly":
        target_day = _target_month_day(now, int(schedule.get("day_of_month") or 1))
        return now.day == target_day
    return False


async def _run_mysqldump(target_path: Path, timeout: int = 300) -> None:
    env = os.environ.copy()
    env["MYSQL_PWD"] = settings.DB_PASSWORD

    process = await asyncio.create_subprocess_exec(
        "mysqldump",
        "--single-transaction",
        "--quick",
        "-h",
        settings.DB_HOST,
        "-P",
        str(settings.DB_PORT),
        "-u",
        settings.DB_USER,
        settings.DB_NAME,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )

    assert process.stdout is not None
    assert process.stderr is not None

    async def _dump() -> None:
        with gzip.open(target_path, "wb") as gzip_file:
            while True:
                chunk = await process.stdout.read(1024 * 1024)
                if not chunk:
                    break
                gzip_file.write(chunk)

        stderr = await process.stderr.read()
        return_code = await process.wait()
        if return_code != 0:
            raise RuntimeError(f"mysqldump failed: {stderr.decode().strip()}")

    try:
        await asyncio.wait_for(_dump(), timeout=timeout)
    except asyncio.TimeoutError:
        process.kill()
        try:
            target_path.unlink(missing_ok=True)
        except Exception:
            pass
        raise RuntimeError(f"mysqldump timed out after {timeout}s")


async def _run_rclone(target_path: Path, timeout: int = 300) -> None:
    remote = settings.RCLONE_REMOTE
    destination_dir = settings.RCLONE_DEST_DIR
    destination = f"{remote}:{destination_dir}" if destination_dir else f"{remote}:"

    config_path = Path(settings.RCLONE_CONFIG)
    seed_path = Path(settings.RCLONE_CONFIG_SEED)
    if seed_path.exists():
        config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(seed_path, config_path)
        except Exception:
            pass

    env = os.environ.copy()
    env.pop("RCLONE_BACKUP_DIR", None)

    process = await asyncio.create_subprocess_exec(
        "rclone",
        "copy",
        str(target_path),
        destination,
        "--config",
        str(config_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=timeout
        )
    except asyncio.TimeoutError:
        process.kill()
        raise RuntimeError(f"rclone upload timed out after {timeout}s")

    if process.returncode != 0:
        output = stderr.decode().strip() or stdout.decode().strip()
        raise RuntimeError(f"rclone upload failed: {output}")


async def run_db_backup_once() -> Dict[str, Any]:
    now = datetime.now().replace(microsecond=0)
    stamp = now.strftime("%Y%m%d-%H%M%S")
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    target_path = BACKUP_ROOT / f"mysql-backup-{stamp}.sql.gz"

    await _run_mysqldump(target_path)
    await _run_rclone(target_path)
    try:
        if target_path.exists():
            target_path.unlink()
    except Exception as exc:
        logger.warning("Failed to delete local backup %s: %s", target_path, exc)

    return {
        "path": str(target_path),
        "created_at": now.isoformat(),
    }


async def run_db_backup_if_due() -> Optional[Dict[str, Any]]:
    now = datetime.now().replace(microsecond=0)

    async with get_db() as db:
        schedule = await _ensure_schedule(db)
        schedule_dict = _normalize_schedule(schedule)
        if not _is_backup_due(schedule_dict, now):
            return None

    result = await run_db_backup_once()

    async with get_db() as db:
        await db.execute(
            "UPDATE backup_schedules SET last_run_at = ? WHERE id = 1",
            (now.isoformat(),),
        )
        await db.commit()

    return result


async def run_scheduled_db_backup() -> None:
    async with SCHEDULE_LOCK:
        try:
            await run_db_backup_if_due()
        except Exception as exc:
            logger.exception("Scheduled DB backup failed: %s", exc)


def _build_trigger(time_of_day: str) -> CronTrigger:
    schedule_time = _parse_time_of_day(time_of_day)
    return CronTrigger(hour=schedule_time.hour, minute=schedule_time.minute)


def reschedule_db_backup_job(time_of_day: str) -> None:
    if not SCHEDULER or not SCHEDULER.running:
        return
    trigger = _build_trigger(time_of_day)
    try:
        SCHEDULER.reschedule_job(JOB_ID, trigger=trigger)
    except Exception:
        SCHEDULER.add_job(
            run_scheduled_db_backup,
            trigger,
            id=JOB_ID,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )


async def start_db_backup_scheduler() -> AsyncIOScheduler:
    global SCHEDULER
    if SCHEDULER and SCHEDULER.running:
        return SCHEDULER

    async with get_db() as db:
        schedule = await _ensure_schedule(db)
        time_of_day = schedule.get("time_of_day") or settings.DB_BACKUP_TIME

    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_scheduled_db_backup,
        _build_trigger(time_of_day),
        id=JOB_ID,
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    SCHEDULER = scheduler
    return scheduler


def shutdown_db_backup_scheduler() -> None:
    global SCHEDULER
    if SCHEDULER:
        SCHEDULER.shutdown(wait=False)
        SCHEDULER = None
