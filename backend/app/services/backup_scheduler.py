import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import logging

from app.services import report_service


logger = logging.getLogger(__name__)


def _monthly_backup_root() -> Path:
    root = Path(__file__).resolve().parents[2] / "monthly_backups"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _month_key(now: Optional[datetime] = None) -> str:
    ref = now or datetime.now()
    return ref.strftime("%Y-%m")


def _marker_path() -> Path:
    return _monthly_backup_root() / ".last_monthly_backup"


def _last_completed_month() -> str:
    marker = _marker_path()
    if not marker.exists():
        return ""
    return marker.read_text(encoding="utf-8").strip()


def _set_last_completed_month(month_key: str) -> None:
    _marker_path().write_text(month_key, encoding="utf-8")


async def generate_monthly_backups(month_key: Optional[str] = None) -> dict:
    """Generate monthly XLSX backups for devices and returns/defects."""
    key = month_key or _month_key()
    target_dir = _monthly_backup_root() / key
    target_dir.mkdir(parents=True, exist_ok=True)

    device_export = await report_service.get_device_backup_export(file_format="xlsx")
    tracking_export = await report_service.get_returns_defects_backup_export(file_format="xlsx")

    device_path = target_dir / f"device-backup-{key}.xlsx"
    tracking_path = target_dir / f"returns-defects-backup-{key}.xlsx"

    device_path.write_bytes(device_export["content"])
    tracking_path.write_bytes(tracking_export["content"])

    _set_last_completed_month(key)

    return {
        "month": key,
        "device_backup": str(device_path),
        "returns_defects_backup": str(tracking_path),
    }


async def run_monthly_backup_if_due() -> Optional[dict]:
    """Run backup once for the current month if not already completed."""
    key = _month_key()
    if _last_completed_month() == key:
        return None
    return await generate_monthly_backups(month_key=key)


def _next_month_run_time(now: Optional[datetime] = None) -> datetime:
    ref = now or datetime.now()
    next_month = (ref.replace(day=28) + timedelta(days=4)).replace(day=1)
    return next_month.replace(hour=0, minute=5, second=0, microsecond=0)


async def monthly_backup_scheduler_loop() -> None:
    """Continuously schedule monthly backups while the app is running."""
    try:
        await run_monthly_backup_if_due()
    except Exception as exc:
        logger.exception("Monthly backup run failed: %s", exc)

    while True:
        now = datetime.now()
        next_run = _next_month_run_time(now)
        sleep_seconds = max(1, int((next_run - now).total_seconds()))
        await asyncio.sleep(sleep_seconds)
        try:
            await run_monthly_backup_if_due()
        except Exception as exc:
            logger.exception("Monthly backup run failed: %s", exc)
