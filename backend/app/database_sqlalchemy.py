"""Async SQLAlchemy engine and session factory, plus Alembic migration runner."""

import asyncio
import os
import time
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.config import settings
from app.core.cache_version import CACHE_VERSION_BUMP_FLAG
from app.core.metrics import (
    classify_sql_operation,
    mysql_queries_total,
    mysql_query_duration_seconds,
    mysql_query_failures_total,
    mysql_active_connections,
)


# Startup DB-connection retry: how many attempts and the delay between them
# (total wait = _DB_STARTUP_RETRIES * _DB_STARTUP_RETRY_DELAY before failing).
_DB_STARTUP_RETRIES = 10
_DB_STARTUP_RETRY_DELAY = 3

ASYNC_DB_URL = (
    f"mysql+aiomysql://{settings.DB_USER}:{settings.DB_PASSWORD}"
    f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
)

engine = create_async_engine(
    ASYNC_DB_URL,
    pool_size=10,
    max_overflow=20,
    pool_recycle=21600,
    echo=False,
)


# ---------------------------------------------------------------------------
# Live MySQL performance metrics (recorded via engine event listeners).
# ---------------------------------------------------------------------------

def _on_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info["_dms_query_start"] = time.perf_counter()
    conn.info["_dms_query_op"] = classify_sql_operation(statement)


def _on_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    start = conn.info.pop("_dms_query_start", None)
    op = conn.info.pop("_dms_query_op", "other")
    if start is None:
        return
    mysql_queries_total.labels(operation=op).inc()
    mysql_query_duration_seconds.labels(operation=op).observe(time.perf_counter() - start)


def _on_handle_error(context):
    op = "other"
    conn = context.connection
    if conn is not None:
        op = conn.info.pop("_dms_query_op", "other")
        conn.info.pop("_dms_query_start", None)
    if op == "other" and context.statement:
        op = classify_sql_operation(context.statement)
    mysql_query_failures_total.labels(operation=op).inc()


def _on_connection_checkout(dbapi_connection, connection_record, connection_proxy):
    mysql_active_connections.inc()


def _on_connection_checkin(dbapi_connection, connection_record):
    mysql_active_connections.dec()


event.listen(engine.sync_engine, "before_cursor_execute", _on_before_cursor_execute)
event.listen(engine.sync_engine, "after_cursor_execute", _on_after_cursor_execute)
event.listen(engine.sync_engine, "handle_error", _on_handle_error)
event.listen(engine.sync_engine.pool, "checkout", _on_connection_checkout)
event.listen(engine.sync_engine.pool, "checkin", _on_connection_checkin)


class CacheAwareAsyncSession(AsyncSession):
    """AsyncSession that keeps the in-memory CacheVersionManager in sync.

    When a transaction that bumped cache_version (flagged by
    `bump_cache_version`) commits successfully, re-read the newly committed
    version from MySQL and update the in-memory manager. Reading the committed
    value back (rather than doing `version += 1`) guarantees the in-memory
    value can never drift from the database, even with interleaved writers.
    """

    async def commit(self) -> None:
        await super().commit()
        if self.info.get(CACHE_VERSION_BUMP_FLAG):
            self.info[CACHE_VERSION_BUMP_FLAG] = False
            # Lazy import breaks the module cycle: cache_version_manager
            # imports async_session_factory from this module.
            from app.core.cache_version_manager import cache_version_manager
            await cache_version_manager.refresh_from_db()


async_session_factory = async_sessionmaker(
    engine, class_=CacheAwareAsyncSession, expire_on_commit=False
)


async def get_async_session():
    """Yield an async SQLAlchemy session."""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def run_alembic_migrations():
    """Run pending Alembic migrations synchronously in a thread pool.

    On first boot MySQL may still be initialising when the app starts; retry
    transient connection failures (with backoff) before giving up, instead of
    letting the app crash and relying on the Docker restart policy.

    In the Docker image this is normally a no-op: the container entrypoint runs
    `alembic upgrade head` at startup with the privileged migration credentials
    and then removes them from the environment, so the long-running app process
    never holds the MySQL root password. We only run migrations here when the
    migration credentials are still present (local development, or a container
    started without the entrypoint).
    """
    # No migration credentials -- schema work was already performed by the
    # entrypoint at container start. Do NOT fall back to the runtime user:
    # dms_user has DML-only privileges and cannot run Alembic DDL.
    if not os.environ.get("MIGRATION_DB_PASSWORD"):
        return

    from alembic.config import Config
    from alembic import command
    from sqlalchemy.exc import OperationalError

    backend_dir = Path(__file__).resolve().parent.parent
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    alembic_cfg.attributes['configure_logger'] = False

    def _upgrade():
        command.upgrade(alembic_cfg, "head")

    loop = asyncio.get_running_loop()
    last_error = None
    for attempt in range(1, _DB_STARTUP_RETRIES + 1):
        try:
            await loop.run_in_executor(None, _upgrade)
            return
        except OperationalError as exc:
            last_error = exc
            if attempt == _DB_STARTUP_RETRIES:
                break
            await asyncio.sleep(_DB_STARTUP_RETRY_DELAY)
    raise last_error
