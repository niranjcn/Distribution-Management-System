"""Startup database initialization using SQLAlchemy async sessions + Alembic."""

from typing import Optional

from sqlalchemy import text

from app.database_sqlalchemy import async_session_factory, run_alembic_migrations
from app.config import settings
from app.utils.security import get_password_hash
from app.core.cache_version import bump_cache_version, ensure_cache_version_row


def _looks_like_bcrypt_hash(value: Optional[str]) -> bool:
    if not value:
        return False
    return value.startswith("$2a$") or value.startswith("$2b$") or value.startswith("$2y$")


async def init_db():
    """Initialize database schema (Alembic) and apply startup data migrations."""
    await run_alembic_migrations()

    async with async_session_factory() as session:
        # Ensure the cache_version single-row marker exists for HTTP caching.
        await ensure_cache_version_row(session)

        for stmt in [
            "UPDATE devices SET serial_number = NULL WHERE device_type = 'Set-top box'",
            "UPDATE devices SET mac_address = NULL WHERE device_type = 'Set-top box'",
            "UPDATE devices SET nuid = NULL WHERE device_type <> 'Set-top box'",
            "UPDATE devices SET current_location = 'PDIC' WHERE current_location = 'NOC' OR current_location IS NULL",
            "UPDATE devices SET current_holder_name = 'PDIC (Distribution)' WHERE current_holder_type = 'noc' AND (current_holder_name IS NULL OR current_holder_name = 'NOC')",
            "UPDATE defects SET report_target = 'manager_admin' WHERE report_target IS NULL OR report_target = ''",
            "UPDATE defects SET forwarded_to_management = COALESCE(forwarded_to_management, 0)",
            "UPDATE defects SET payment_confirmed = COALESCE(payment_confirmed, 0)",
            "UPDATE defects SET payment_due_user_id = COALESCE(NULLIF(payment_due_user_id, ''), reported_by)",
            "UPDATE defects SET payment_due_user_name = COALESCE(NULLIF(payment_due_user_name, ''), reported_by_name)",
            "UPDATE users SET force_email_change = COALESCE(force_email_change, 0)",
            "UPDATE users SET force_password_change = COALESCE(force_password_change, 0)",
            "UPDATE users SET role = 'super_admin' WHERE role = 'super_admin'",
            "UPDATE users SET role = 'pdic_staff' WHERE role = 'pdic_staff'",
        ]:
            await session.execute(text(stmt))

        result = await session.execute(
            text("SELECT id, new_password FROM change_requests WHERE new_password IS NOT NULL AND new_password != ''")
        )
        for row in result.fetchall():
            password_value = row.new_password
            if _looks_like_bcrypt_hash(password_value):
                continue
            await session.execute(
                text("UPDATE change_requests SET new_password = :pw WHERE id = :id"),
                {"pw": get_password_hash(password_value), "id": row.id},
            )

        # These startup fixes modify application data, so bump the cache version
        # in the same transaction to keep any previously cached responses current.
        await bump_cache_version(session)
        await session.commit()

    print(
        f"MySQL database initialized at {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
    )
