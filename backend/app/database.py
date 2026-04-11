import re
import asyncio
from contextlib import asynccontextmanager
from typing import Any, Iterable, Optional

import aiomysql
import pymysql

from app.config import settings
from app.utils.security import get_password_hash


_pool: Optional[aiomysql.Pool] = None


def _looks_like_bcrypt_hash(value: Optional[str]) -> bool:
    if not value:
        return False
    return value.startswith("$2a$") or value.startswith("$2b$") or value.startswith("$2y$")


def _translate_sql(sql: str) -> str:
    """Translate common SQLite SQL patterns to MySQL-compatible SQL."""
    translated = sql

    translated = re.sub(r"\bINSERT\s+OR\s+IGNORE\b", "INSERT IGNORE", translated, flags=re.IGNORECASE)
    translated = re.sub(r"datetime\('now'\)", "UTC_TIMESTAMP()", translated, flags=re.IGNORECASE)
    translated = re.sub(r"\bCAST\((.*?)\s+AS\s+TEXT\)", r"CAST(\1 AS CHAR)", translated, flags=re.IGNORECASE)

    # Convert qmark placeholders to MySQL %s placeholders while preserving quoted text.
    out = []
    in_single = False
    in_double = False
    i = 0
    while i < len(translated):
        ch = translated[i]
        if ch == "'" and not in_double:
            if in_single and i + 1 < len(translated) and translated[i + 1] == "'":
                out.append("''")
                i += 2
                continue
            in_single = not in_single
            out.append(ch)
            i += 1
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            out.append(ch)
            i += 1
            continue

        if ch == "?" and not in_single and not in_double:
            out.append("%s")
        else:
            out.append(ch)
        i += 1

    return "".join(out)


class CursorWrapper:
    def __init__(self, cursor: aiomysql.Cursor):
        self._cursor = cursor

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    @property
    def lastrowid(self) -> Any:
        return self._cursor.lastrowid

    async def fetchone(self):
        row = await self._cursor.fetchone()
        if row is None:
            return None
        return CompatRow(row)

    async def fetchall(self):
        rows = await self._cursor.fetchall()
        return [CompatRow(row) for row in rows]


class CompatRow(dict):
    """Dict row that also supports positional indexing (row[0]) for legacy code."""

    def __getitem__(self, key):
        if isinstance(key, int):
            values = list(super().values())
            return values[key]
        return super().__getitem__(key)


class MySQLDB:
    def __init__(self, conn: aiomysql.Connection):
        self._conn = conn

    @staticmethod
    def _is_retryable_read_query(sql: str) -> bool:
        prefix = sql.lstrip().upper()
        return (
            prefix.startswith("SELECT")
            or prefix.startswith("SHOW")
            or prefix.startswith("DESCRIBE")
            or prefix.startswith("EXPLAIN")
        )

    async def execute(self, query: str, params: Optional[Iterable[Any]] = None) -> CursorWrapper:
        sql = _translate_sql(query)
        args = tuple(params or ())
        max_attempts = 3 if self._is_retryable_read_query(sql) else 1

        for attempt in range(1, max_attempts + 1):
            cur = await self._conn.cursor(aiomysql.DictCursor)
            try:
                await cur.execute(sql, args)
                return CursorWrapper(cur)
            except pymysql.err.OperationalError as exc:
                # MySQL error 1412 appears transiently after DDL/TRUNCATE metadata changes.
                if exc.args and exc.args[0] == 1412 and attempt < max_attempts:
                    await cur.close()
                    await asyncio.sleep(0.05)
                    continue
                await cur.close()
                raise
            except Exception:
                await cur.close()
                raise

    async def executemany(self, query: str, params: Iterable[Iterable[Any]]) -> CursorWrapper:
        cur = await self._conn.cursor(aiomysql.DictCursor)
        sql = _translate_sql(query)
        await cur.executemany(sql, params)
        return CursorWrapper(cur)

    async def commit(self):
        await self._conn.commit()

    async def rollback(self):
        await self._conn.rollback()

    async def close(self):
        self._conn.close()


async def _ensure_pool() -> aiomysql.Pool:
    global _pool
    if _pool is None:
        _pool = await aiomysql.create_pool(
            host=settings.DB_HOST,
            port=settings.DB_PORT,
            user=settings.DB_USER,
            password=settings.DB_PASSWORD,
            db=settings.DB_NAME,
            autocommit=False,
            minsize=1,
            maxsize=10,
            charset="utf8mb4",
        )
    return _pool


@asynccontextmanager
async def get_db():
    """Get an async MySQL database connection."""
    pool = await _ensure_pool()
    conn = await pool.acquire()
    db = MySQLDB(conn)
    try:
        yield db
    finally:
        pool.release(conn)


async def close_pool():
    global _pool
    if _pool is not None:
        _pool.close()
        await _pool.wait_closed()
        _pool = None


CREATE_TABLE_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        email VARCHAR(255) UNIQUE NOT NULL,
        name VARCHAR(255) NOT NULL,
        password_hash TEXT NOT NULL,
        role VARCHAR(64) NOT NULL,
        digital_id VARCHAR(128),
        broadband_id VARCHAR(128),
        force_email_change TINYINT(1) DEFAULT 0,
        force_password_change TINYINT(1) DEFAULT 0,
        phone VARCHAR(64),
        department VARCHAR(255),
        location VARCHAR(255),
        status VARCHAR(32) DEFAULT 'active',
        parent_id INT NULL,
        permissions LONGTEXT,
        theme VARCHAR(32) DEFAULT 'light',
        compact_mode TINYINT(1) DEFAULT 0,
        email_notifications TINYINT(1) DEFAULT 1,
        push_notifications TINYINT(1) DEFAULT 1,
        is_verified TINYINT(1) DEFAULT 0,
        created_at VARCHAR(64) NOT NULL,
        updated_at VARCHAR(64) NOT NULL,
        last_login VARCHAR(64),
        failed_login_attempts INT DEFAULT 0,
        locked_until VARCHAR(64),
        created_by INT NULL,
        INDEX idx_users_parent_id(parent_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS devices (
        id INT AUTO_INCREMENT PRIMARY KEY,
        device_id VARCHAR(128) UNIQUE NOT NULL,
        device_type VARCHAR(128) NOT NULL,
        model VARCHAR(255) NOT NULL,
        serial_number VARCHAR(255) UNIQUE,
        mac_address VARCHAR(255) UNIQUE,
        manufacturer VARCHAR(255) NOT NULL,
        band_type VARCHAR(64),
        nuid VARCHAR(255) UNIQUE,
        status VARCHAR(64) DEFAULT 'available',
        current_location VARCHAR(255),
        current_holder_id VARCHAR(64),
        current_holder_name VARCHAR(255),
        registered_by_name VARCHAR(255),
        current_holder_type VARCHAR(64),
        purchase_date VARCHAR(64),
        warranty_expiry VARCHAR(64),
        metadata LONGTEXT,
        created_at VARCHAR(64) NOT NULL,
        updated_at VARCHAR(64) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS device_history (
        id INT AUTO_INCREMENT PRIMARY KEY,
        device_id VARCHAR(64) NOT NULL,
        action VARCHAR(128) NOT NULL,
        from_user_id VARCHAR(64),
        from_user_name VARCHAR(255),
        to_user_id VARCHAR(64),
        to_user_name VARCHAR(255),
        status_before VARCHAR(64),
        status_after VARCHAR(64),
        location VARCHAR(255),
        notes LONGTEXT,
        performed_by VARCHAR(64),
        performed_by_name VARCHAR(255),
        timestamp VARCHAR(64) NOT NULL,
        INDEX idx_device_history_device_id(device_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS distributions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        distribution_id VARCHAR(128) UNIQUE NOT NULL,
        device_ids LONGTEXT NOT NULL,
        device_count INT DEFAULT 0,
        from_user_id VARCHAR(64) NOT NULL,
        from_user_name VARCHAR(255),
        from_user_type VARCHAR(64),
        to_user_id VARCHAR(64) NOT NULL,
        to_user_name VARCHAR(255),
        to_user_type VARCHAR(64),
        status VARCHAR(64) DEFAULT 'pending',
        request_date VARCHAR(64) NOT NULL,
        approval_date VARCHAR(64),
        delivery_date VARCHAR(64),
        notes LONGTEXT,
        manifest_file VARCHAR(255),
        approved_by VARCHAR(64),
        approved_by_name VARCHAR(255),
        created_by VARCHAR(64) NOT NULL,
        created_at VARCHAR(64) NOT NULL,
        updated_at VARCHAR(64) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS defects (
        id INT AUTO_INCREMENT PRIMARY KEY,
        report_id VARCHAR(128) UNIQUE NOT NULL,
        device_id VARCHAR(64) NOT NULL,
        device_serial VARCHAR(255),
        device_type VARCHAR(128),
        reported_by VARCHAR(64) NOT NULL,
        reported_by_name VARCHAR(255),
        defect_type VARCHAR(64) NOT NULL,
        severity VARCHAR(64) NOT NULL,
        description LONGTEXT NOT NULL,
        symptoms LONGTEXT,
        report_target VARCHAR(64) DEFAULT 'manager_admin',
        forwarded_to_management TINYINT(1) DEFAULT 0,
        forwarded_to_management_at VARCHAR(64),
        forwarded_to_management_by VARCHAR(64),
        forwarded_to_management_by_name VARCHAR(255),
        operator_id VARCHAR(64),
        sub_distributor_id VARCHAR(64),
        status VARCHAR(64) DEFAULT 'reported',
        resolution LONGTEXT,
        resolved_by VARCHAR(64),
        resolved_by_name VARCHAR(255),
        resolved_at VARCHAR(64),
        replacement_requested_at VARCHAR(64),
        replacement_confirmed_at VARCHAR(64),
        replacement_confirmed_by VARCHAR(64),
        replacement_confirmed_by_name VARCHAR(255),
        return_amount DOUBLE DEFAULT 0,
        service_charge DOUBLE DEFAULT 0,
        payment_bill_url VARCHAR(255),
        payment_confirmed TINYINT(1) DEFAULT 0,
        payment_confirmed_at VARCHAR(64),
        payment_confirmed_by VARCHAR(64),
        payment_confirmed_by_name VARCHAR(255),
        payment_due_user_id VARCHAR(64),
        payment_due_user_name VARCHAR(255),
        images LONGTEXT,
        created_at VARCHAR(64) NOT NULL,
        updated_at VARCHAR(64) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS returns (
        id INT AUTO_INCREMENT PRIMARY KEY,
        return_id VARCHAR(128) UNIQUE NOT NULL,
        device_id VARCHAR(64) NOT NULL,
        device_serial VARCHAR(255),
        device_type VARCHAR(128),
        requested_by VARCHAR(64) NOT NULL,
        requested_by_name VARCHAR(255),
        return_to VARCHAR(64),
        return_to_name VARCHAR(255),
        reason VARCHAR(64) NOT NULL,
        description LONGTEXT,
        status VARCHAR(64) DEFAULT 'pending',
        request_date VARCHAR(64) NOT NULL,
        approval_date VARCHAR(64),
        received_date VARCHAR(64),
        approved_by VARCHAR(64),
        approved_by_name VARCHAR(255),
        defect_id VARCHAR(64),
        mac_address VARCHAR(255),
        created_at VARCHAR(64) NOT NULL,
        updated_at VARCHAR(64) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS approvals (
        id INT AUTO_INCREMENT PRIMARY KEY,
        approval_type VARCHAR(64) NOT NULL,
        entity_id VARCHAR(64) NOT NULL,
        entity_type VARCHAR(64) NOT NULL,
        requested_by VARCHAR(64) NOT NULL,
        requested_by_name VARCHAR(255),
        status VARCHAR(64) DEFAULT 'pending',
        priority VARCHAR(32) DEFAULT 'medium',
        request_date VARCHAR(64) NOT NULL,
        approved_by VARCHAR(64),
        approved_by_name VARCHAR(255),
        approval_date VARCHAR(64),
        rejection_reason LONGTEXT,
        notes LONGTEXT,
        created_at VARCHAR(64) NOT NULL,
        updated_at VARCHAR(64) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS operators (
        id INT AUTO_INCREMENT PRIMARY KEY,
        operator_id VARCHAR(128) UNIQUE NOT NULL,
        name VARCHAR(255) NOT NULL,
        phone VARCHAR(64) NOT NULL,
        email VARCHAR(255),
        address VARCHAR(255),
        area VARCHAR(255),
        city VARCHAR(255),
        assigned_to VARCHAR(64) NOT NULL,
        assigned_to_name VARCHAR(255),
        status VARCHAR(32) DEFAULT 'active',
        device_count INT DEFAULT 0,
        connection_type VARCHAR(64),
        created_at VARCHAR(64) NOT NULL,
        updated_at VARCHAR(64) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS notifications (
        id INT AUTO_INCREMENT PRIMARY KEY,
        user_id VARCHAR(64) NOT NULL,
        title VARCHAR(255) NOT NULL,
        message LONGTEXT NOT NULL,
        type VARCHAR(64) DEFAULT 'info',
        category VARCHAR(64) NOT NULL,
        is_read TINYINT(1) DEFAULT 0,
        link VARCHAR(255),
        metadata LONGTEXT,
        created_at VARCHAR(64) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS change_requests (
        id INT AUTO_INCREMENT PRIMARY KEY,
        request_id VARCHAR(128) UNIQUE NOT NULL,
        requested_by INT NOT NULL,
        requested_by_name VARCHAR(255) NOT NULL,
        requested_by_role VARCHAR(64) NOT NULL,
        request_type VARCHAR(128) NOT NULL,
        new_email VARCHAR(255),
        new_password VARCHAR(255),
        device_id VARCHAR(64),
        requested_status VARCHAR(64),
        reason LONGTEXT,
        status VARCHAR(32) DEFAULT 'pending',
        reviewed_by INT,
        reviewed_by_name VARCHAR(255),
        review_note LONGTEXT,
        created_at VARCHAR(64) NOT NULL,
        updated_at VARCHAR(64) NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS external_inventory_items (
        id INT AUTO_INCREMENT PRIMARY KEY,
        inventory_id VARCHAR(128) UNIQUE NOT NULL,
        item_id VARCHAR(128) NOT NULL,
        name VARCHAR(255) NOT NULL,
        serial_number VARCHAR(255),
        mac_id VARCHAR(255),
        identifier_type VARCHAR(128),
        identifier VARCHAR(255),
        device_type VARCHAR(128) NOT NULL,
        price DOUBLE DEFAULT 0,
        sku VARCHAR(128),
        category VARCHAR(128),
        unit VARCHAR(32) DEFAULT 'pcs',
        quantity_on_hand INT DEFAULT 0,
        reorder_level INT DEFAULT 0,
        unit_cost DOUBLE DEFAULT 0,
        supplier_name VARCHAR(255),
        location VARCHAR(255),
        status VARCHAR(32) DEFAULT 'active',
        notes LONGTEXT,
        image_url VARCHAR(255),
        created_by VARCHAR(64),
        created_at VARCHAR(64) NOT NULL,
        updated_at VARCHAR(64) NOT NULL,
        INDEX idx_external_inventory_items_item_id(item_id),
        INDEX idx_external_inventory_items_serial_number(serial_number),
        INDEX idx_external_inventory_items_mac_id(mac_id),
        INDEX idx_external_inventory_items_device_type(device_type),
        INDEX idx_external_inventory_items_status(status),
        INDEX idx_external_inventory_items_sku(sku)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS inventory_purchase_orders (
        id INT AUTO_INCREMENT PRIMARY KEY,
        po_id VARCHAR(128) UNIQUE NOT NULL,
        supplier_name VARCHAR(255) NOT NULL,
        status VARCHAR(32) DEFAULT 'draft',
        expected_date VARCHAR(64),
        ordered_by VARCHAR(64) NOT NULL,
        ordered_by_name VARCHAR(255),
        total_amount DOUBLE DEFAULT 0,
        notes LONGTEXT,
        created_at VARCHAR(64) NOT NULL,
        updated_at VARCHAR(64) NOT NULL,
        INDEX idx_inventory_purchase_orders_status(status)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS inventory_po_lines (
        id INT AUTO_INCREMENT PRIMARY KEY,
        po_id VARCHAR(128) NOT NULL,
        item_inventory_id VARCHAR(128) NOT NULL,
        item_sku VARCHAR(128),
        item_name VARCHAR(255),
        quantity_ordered INT NOT NULL,
        unit_cost DOUBLE DEFAULT 0,
        line_total DOUBLE DEFAULT 0,
        created_at VARCHAR(64) NOT NULL,
        INDEX idx_inventory_po_lines_po_id(po_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS inventory_receipts (
        id INT AUTO_INCREMENT PRIMARY KEY,
        receipt_id VARCHAR(128) UNIQUE NOT NULL,
        po_id VARCHAR(128) NOT NULL,
        supplier_name VARCHAR(255),
        received_by VARCHAR(64) NOT NULL,
        received_by_name VARCHAR(255),
        notes LONGTEXT,
        created_at VARCHAR(64) NOT NULL,
        INDEX idx_inventory_receipts_po_id(po_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS inventory_receipt_lines (
        id INT AUTO_INCREMENT PRIMARY KEY,
        receipt_id VARCHAR(128) NOT NULL,
        item_inventory_id VARCHAR(128) NOT NULL,
        item_sku VARCHAR(128),
        item_name VARCHAR(255),
        quantity_received INT NOT NULL,
        unit_cost DOUBLE DEFAULT 0,
        line_total DOUBLE DEFAULT 0,
        INDEX idx_inventory_receipt_lines_receipt_id(receipt_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS inventory_stock_movements (
        id INT AUTO_INCREMENT PRIMARY KEY,
        movement_id VARCHAR(128) UNIQUE NOT NULL,
        item_inventory_id VARCHAR(128) NOT NULL,
        item_sku VARCHAR(128),
        item_name VARCHAR(255),
        movement_type VARCHAR(64) NOT NULL,
        quantity INT NOT NULL,
        reference_type VARCHAR(64),
        reference_id VARCHAR(128),
        notes LONGTEXT,
        performed_by VARCHAR(64),
        performed_by_name VARCHAR(255),
        created_at VARCHAR(64) NOT NULL,
        INDEX idx_inventory_stock_movements_item_id(item_inventory_id),
        INDEX idx_inventory_stock_movements_created_at(created_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS api_activity_logs (
        id INT AUTO_INCREMENT PRIMARY KEY,
        actor_id VARCHAR(64),
        actor_name VARCHAR(255),
        actor_role VARCHAR(64),
        method VARCHAR(16) NOT NULL,
        path VARCHAR(255) NOT NULL,
        status_code INT,
        description LONGTEXT,
        ip_address VARCHAR(64),
        created_at VARCHAR(64) NOT NULL,
        INDEX idx_api_activity_logs_created_at(created_at),
        INDEX idx_api_activity_logs_actor_name(actor_name),
        INDEX idx_api_activity_logs_path(path)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS approval_role_routing (
        id INT AUTO_INCREMENT PRIMARY KEY,
        approval_type VARCHAR(64) UNIQUE NOT NULL,
        admin_enabled TINYINT(1) DEFAULT 1,
        manager_enabled TINYINT(1) DEFAULT 1,
        staff_enabled TINYINT(1) DEFAULT 1,
        updated_by VARCHAR(64),
        updated_at VARCHAR(64) NOT NULL,
        INDEX idx_approval_role_routing_type(approval_type)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE IF NOT EXISTS token_blacklist (
        token_hash VARCHAR(255) PRIMARY KEY,
        expires_at VARCHAR(64) NOT NULL,
        created_at VARCHAR(64) NOT NULL,
        INDEX idx_token_blacklist_expires_at(expires_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
]


async def init_db():
    """Initialize MySQL tables and apply lightweight migrations."""
    pool = await _ensure_pool()
    conn = await pool.acquire()
    db = MySQLDB(conn)

    try:
        for stmt in CREATE_TABLE_STATEMENTS:
            await db.execute(stmt)

        # Lightweight migrations for existing deployments.
        for stmt in [
            "ALTER TABLE change_requests ADD COLUMN device_id VARCHAR(64)",
            "ALTER TABLE change_requests ADD COLUMN requested_status VARCHAR(64)",
            "ALTER TABLE devices ADD COLUMN registered_by_name VARCHAR(255)",
            "ALTER TABLE returns ADD COLUMN defect_id VARCHAR(64)",
            "ALTER TABLE defects ADD COLUMN auto_return_id VARCHAR(64)",
            "ALTER TABLE defects ADD COLUMN replacement_device_id VARCHAR(64)",
            "ALTER TABLE defects ADD COLUMN replacement_requested_at VARCHAR(64)",
            "ALTER TABLE defects ADD COLUMN replacement_confirmed_at VARCHAR(64)",
            "ALTER TABLE defects ADD COLUMN replacement_confirmed_by VARCHAR(64)",
            "ALTER TABLE defects ADD COLUMN replacement_confirmed_by_name VARCHAR(255)",
            "ALTER TABLE defects ADD COLUMN return_amount DOUBLE DEFAULT 0",
            "ALTER TABLE defects ADD COLUMN service_charge DOUBLE DEFAULT 0",
            "ALTER TABLE defects ADD COLUMN payment_bill_url VARCHAR(255)",
            "ALTER TABLE defects ADD COLUMN payment_confirmed TINYINT(1) DEFAULT 0",
            "ALTER TABLE defects ADD COLUMN payment_confirmed_at VARCHAR(64)",
            "ALTER TABLE defects ADD COLUMN payment_confirmed_by VARCHAR(64)",
            "ALTER TABLE defects ADD COLUMN payment_confirmed_by_name VARCHAR(255)",
            "ALTER TABLE defects ADD COLUMN payment_due_user_id VARCHAR(64)",
            "ALTER TABLE defects ADD COLUMN payment_due_user_name VARCHAR(255)",
            "ALTER TABLE defects ADD COLUMN report_target VARCHAR(64) DEFAULT 'manager_admin'",
            "ALTER TABLE defects ADD COLUMN forwarded_to_management TINYINT(1) DEFAULT 0",
            "ALTER TABLE defects ADD COLUMN forwarded_to_management_at VARCHAR(64)",
            "ALTER TABLE defects ADD COLUMN forwarded_to_management_by VARCHAR(64)",
            "ALTER TABLE defects ADD COLUMN forwarded_to_management_by_name VARCHAR(255)",
            "ALTER TABLE defects ADD COLUMN operator_id VARCHAR(64)",
            "ALTER TABLE defects ADD COLUMN sub_distributor_id VARCHAR(64)",
            "ALTER TABLE returns ADD COLUMN mac_address VARCHAR(255)",
            "ALTER TABLE devices ADD COLUMN band_type VARCHAR(64)",
            "ALTER TABLE devices ADD COLUMN nuid VARCHAR(255)",
            "ALTER TABLE devices ADD UNIQUE INDEX uq_devices_nuid (nuid)",
            "ALTER TABLE devices MODIFY COLUMN serial_number VARCHAR(255) NULL",
            "ALTER TABLE devices MODIFY COLUMN mac_address VARCHAR(255) NULL",
            "ALTER TABLE external_inventory_items ADD COLUMN item_id VARCHAR(128)",
            "ALTER TABLE external_inventory_items ADD COLUMN serial_number VARCHAR(255)",
            "ALTER TABLE external_inventory_items ADD COLUMN mac_id VARCHAR(255)",
            "ALTER TABLE external_inventory_items ADD COLUMN identifier_type VARCHAR(128)",
            "ALTER TABLE external_inventory_items ADD COLUMN identifier VARCHAR(255)",
            "ALTER TABLE external_inventory_items ADD COLUMN device_type VARCHAR(128)",
            "ALTER TABLE external_inventory_items ADD COLUMN price DOUBLE DEFAULT 0",
            "ALTER TABLE external_inventory_items ADD COLUMN image_url VARCHAR(255)",
            "ALTER TABLE approval_role_routing ADD COLUMN staff_enabled TINYINT(1) DEFAULT 1",
            "ALTER TABLE users ADD COLUMN failed_login_attempts INT DEFAULT 0",
            "ALTER TABLE users ADD COLUMN locked_until VARCHAR(64)",
            "ALTER TABLE users ADD COLUMN force_email_change TINYINT(1) DEFAULT 0",
            "ALTER TABLE users ADD COLUMN force_password_change TINYINT(1) DEFAULT 0",
            "ALTER TABLE users ADD COLUMN digital_id VARCHAR(128)",
            "ALTER TABLE users ADD COLUMN broadband_id VARCHAR(128)",
        ]:
            try:
                await db.execute(stmt)
            except Exception:
                pass

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
            "UPDATE approval_role_routing SET staff_enabled = COALESCE(staff_enabled, 1)",
            "UPDATE devices SET serial_number = NULL WHERE device_type = 'Set-top box'",
            "UPDATE devices SET mac_address = NULL WHERE device_type = 'Set-top box'",
            "UPDATE devices SET nuid = NULL WHERE device_type <> 'Set-top box'",
            "UPDATE devices SET current_location = 'PDIC' WHERE current_location = 'NOC' OR current_location IS NULL",
            "UPDATE devices SET current_holder_name = 'PDIC (Distribution)' WHERE current_holder_type = 'noc' AND (current_holder_name IS NULL OR current_holder_name = 'NOC')",
            "UPDATE defects SET report_target = 'manager_admin' WHERE report_target IS NULL OR report_target = ''",
            "UPDATE defects SET forwarded_to_management = COALESCE(forwarded_to_management, 0)",
            "UPDATE defects SET return_amount = COALESCE(return_amount, 0)",
            "UPDATE defects SET payment_confirmed = COALESCE(payment_confirmed, 0)",
            "UPDATE defects SET payment_due_user_id = COALESCE(NULLIF(payment_due_user_id, ''), reported_by)",
            "UPDATE defects SET payment_due_user_name = COALESCE(NULLIF(payment_due_user_name, ''), reported_by_name)",
            "UPDATE users SET force_email_change = COALESCE(force_email_change, 0)",
            "UPDATE users SET force_password_change = COALESCE(force_password_change, 0)",
            "UPDATE users SET role = 'super_admin' WHERE role = 'super_admin'",
            "UPDATE users SET role = 'pdic_staff' WHERE role = 'pdic_staff'",
        ]:
            await db.execute(stmt)

        await db.execute(
            """
            INSERT IGNORE INTO approval_role_routing
            (approval_type, admin_enabled, manager_enabled, staff_enabled, updated_by, updated_at)
            VALUES ('distribution', 1, 1, 1, 'system', UTC_TIMESTAMP())
            """
        )
        await db.execute(
            """
            INSERT IGNORE INTO approval_role_routing
            (approval_type, admin_enabled, manager_enabled, staff_enabled, updated_by, updated_at)
            VALUES ('return', 1, 1, 1, 'system', UTC_TIMESTAMP())
            """
        )
        await db.execute(
            """
            INSERT IGNORE INTO approval_role_routing
            (approval_type, admin_enabled, manager_enabled, staff_enabled, updated_by, updated_at)
            VALUES ('defect', 1, 1, 1, 'system', UTC_TIMESTAMP())
            """
        )

        # Security migration: hash any legacy plaintext values in change_requests.new_password.
        cursor = await db.execute(
            """
            SELECT id, new_password
            FROM change_requests
            WHERE new_password IS NOT NULL AND new_password != ''
            """
        )
        for row in await cursor.fetchall():
            password_value = row.get("new_password")
            if _looks_like_bcrypt_hash(password_value):
                continue
            await db.execute(
                "UPDATE change_requests SET new_password = ? WHERE id = ?",
                (get_password_hash(password_value), row["id"]),
            )

        await db.commit()
    finally:
        pool.release(conn)

    print(
        f"✅ MySQL database initialized at {settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
    )


def row_to_dict(row):
    """Convert a DB row mapping to standardized dict with string id fields."""
    if row is None:
        return None

    d = dict(row)
    if "id" in d and d["id"] is not None:
        d["_id"] = str(d["id"])
        d["id"] = str(d["id"])

    for key in ["compact_mode", "email_notifications", "push_notifications", "is_verified", "is_read"]:
        if key in d and d[key] is not None:
            d[key] = bool(d[key])

    return d


def rows_to_list(rows):
    """Convert list of rows to standardized dict list."""
    return [row_to_dict(r) for r in rows if r is not None]

