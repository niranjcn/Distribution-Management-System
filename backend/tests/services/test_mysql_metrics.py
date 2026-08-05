"""Tests for live MySQL metrics recorded via SQLAlchemy engine event listeners.

The listeners live in app/database_sqlalchemy and are bound to the production
MySQL engine. These tests attach the same handler functions to an in-memory
aiosqlite engine and verify the shared metric counters/histograms are recorded.
"""

import pytest
from prometheus_client import REGISTRY
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.metrics import classify_sql_operation
from app.database_sqlalchemy import (
    _on_after_cursor_execute,
    _on_before_cursor_execute,
    _on_connection_checkin,
    _on_connection_checkout,
    _on_handle_error,
)


def _sample(name, labels):
    value = REGISTRY.get_sample_value(name, labels)
    return value if value is not None else 0.0


@pytest.fixture
async def instrumented_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.execute(text("CREATE TABLE items (id INT PRIMARY KEY, value TEXT NOT NULL)"))

    event.listen(engine.sync_engine, "before_cursor_execute", _on_before_cursor_execute)
    event.listen(engine.sync_engine, "after_cursor_execute", _on_after_cursor_execute)
    event.listen(engine.sync_engine, "handle_error", _on_handle_error)
    event.listen(engine.sync_engine.pool, "checkout", _on_connection_checkout)
    event.listen(engine.sync_engine.pool, "checkin", _on_connection_checkin)
    yield engine
    await engine.dispose()


@pytest.mark.asyncio
async def test_queries_recorded_by_operation(instrumented_engine):
    before_select = _sample("mysql_queries_total", {"operation": "select"})
    before_insert = _sample("mysql_queries_total", {"operation": "insert"})

    async with instrumented_engine.connect() as conn:
        await conn.execute(text("SELECT * FROM items"))
        await conn.execute(text("INSERT INTO items (id, value) VALUES (1, 'x')"))

    assert _sample("mysql_queries_total", {"operation": "select"}) == before_select + 1
    assert _sample("mysql_queries_total", {"operation": "insert"}) == before_insert + 1


@pytest.mark.asyncio
async def test_duration_observed(instrumented_engine):
    async with instrumented_engine.connect() as conn:
        await conn.execute(text("SELECT * FROM items"))
    # Histogram samples populate a `_count` series that is always emitted.
    assert _sample("mysql_query_duration_seconds_count", {"operation": "select"}) >= 1


@pytest.mark.asyncio
async def test_failures_recorded(instrumented_engine):
    before = _sample("mysql_query_failures_total", {"operation": "select"})
    with pytest.raises(Exception):
        async with instrumented_engine.connect() as conn:
            await conn.execute(text("SELECT * FROM missing_table"))
    assert _sample("mysql_query_failures_total", {"operation": "select"}) == before + 1


@pytest.mark.asyncio
async def test_active_connections_tracked(instrumented_engine):
    before = _sample("mysql_active_connections", {})
    async with instrumented_engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
        in_use = _sample("mysql_active_connections", {})
        assert in_use >= before + 1
    assert _sample("mysql_active_connections", {}) == before


@pytest.mark.parametrize(
    "statement,expected",
    [
        ("SELECT * FROM users", "select"),
        ("INSERT INTO users (id) VALUES (1)", "insert"),
        ("UPDATE users SET x = 1", "update"),
        ("DELETE FROM users", "delete"),
        ("  SELECT 1", "select"),
        ("WITH cte AS (SELECT 1) SELECT * FROM cte", "other"),
        ("", "other"),
        (None, "other"),
    ],
)
def test_classify_sql_operation(statement, expected):
    assert classify_sql_operation(statement) == expected
