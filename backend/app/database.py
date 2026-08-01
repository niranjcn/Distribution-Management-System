"""Startup database initialization using SQLAlchemy async sessions + Alembic."""

from typing import Optional

from sqlalchemy import text

from app.database_sqlalchemy import async_session_factory, run_alembic_migrations
from app.config import settings
from app.utils.security import get_password_hash


def _looks_like_bcrypt_hash(value: Optional[str]) -> bool:
    if not value:
        return False
    return value.startswith("$2a$") or value.startswith("$2b$") or value.startswith("$2y$")


async def init_db():
    """Initialize database schema (Alembic) and apply startup data migrations."""
    await run_alembic_migrations()

    async with async_session_factory() as session:
        for stmt in [
            "UPDATE external_inventory_items SET item_id = inventory_id WHERE item_id IS NULL OR item_id = ''",
            "UPDATE external_inventory_items SET serial_number = '' WHERE serial_number IS NULL",
            "UPDATE external_inventory_items SET mac_id = '' WHERE mac_id IS NULL",
            "UPDATE external_inventory_items SET identifier_type = COALESCE(identifier_type, '')",
            "UPDATE external_inventory_items SET identifier = COALESCE(identifier, '')",
            "UPDATE external_inventory_items SET device_type = COALESCE(category, 'device') WHERE device_type IS NULL OR device_type = ''",
            "UPDATE external_inventory_items SET price = COALESCE(price, unit_cost, 0)",
            "UPDATE external_inventory_items SET sku = COALESCE(NULLIF(item_id, ''), sku)",
            "UPDATE external_inventory_items SET category = COALESCE(NULLIF(device_type, ''), category)",
            "UPDATE external_inventory_items SET unit_cost = COALESCE(price, unit_cost, 0)",
            "UPDATE external_inventory_items SET identifier_type = 'MAC ID', identifier = mac_id WHERE (identifier_type IS NULL OR identifier_type = '') AND (identifier IS NULL OR identifier = '') AND COALESCE(mac_id, '') != '' AND LOWER(REPLACE(REPLACE(REPLACE(device_type, '-', ''), '_', ''), ' ', '')) NOT IN ('olt', 'adapter')",
            "UPDATE external_inventory_items SET identifier_type = NULL, identifier = NULL WHERE LOWER(REPLACE(REPLACE(REPLACE(device_type, '-', ''), '_', ''), ' ', '')) IN ('olt', 'adapter')",

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

        await session.commit()

    print(
        f"MySQL database initialized at {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
    )
