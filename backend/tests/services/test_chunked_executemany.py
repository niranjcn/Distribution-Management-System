import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.services.bulk_upload_service import chunked_executemany


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.execute(text(
            "CREATE TABLE t (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE, extra TEXT)"
        ))
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


async def _count(session) -> int:
    return (await session.execute(text("SELECT COUNT(*) FROM t"))).scalar()


class TestChunkedExecutemany:
    async def test_batch_success_ignores_extra_keys(self, session):
        rows = [
            {"name": "a", "row": 1, "_generated_id": "x1"},
            {"name": "b", "row": 2, "_generated_id": "x2"},
        ]
        created = []

        async def on_batch_success(s, batch):
            created.extend(item["_generated_id"] for item in batch)

        ok = await chunked_executemany(
            session,
            "INSERT INTO t (name) VALUES (:name)",
            rows,
            on_batch_success=on_batch_success,
        )
        assert ok is True
        assert created == ["x1", "x2"]
        assert await _count(session) == 2

    async def test_row_fallback_reports_duplicate_and_keeps_going(self, session):
        await session.execute(text("INSERT INTO t (name) VALUES ('dup')"))
        # Duplicate first so the failed batch inserts nothing before it (aiosqlite
        # executemany inserts row-by-row; MySQL, the app target, is atomic).
        rows = [{"name": "dup"}, {"name": "a"}, {"name": "b"}]
        created = []
        skipped = []

        async def on_batch_success(s, batch):
            created.extend(item["name"] for item in batch)

        async def on_row_duplicate(s, item, err):
            skipped.append(item["name"])

        ok = await chunked_executemany(
            session,
            "INSERT INTO t (name) VALUES (:name)",
            rows,
            chunk_size=2,
            on_batch_success=on_batch_success,
            on_row_duplicate=on_row_duplicate,
        )
        assert ok is True
        assert created == ["a", "b"]
        assert skipped == ["dup"]
        assert await _count(session) == 3

    async def test_abort_on_error_stops_loop(self, session):
        rows = [{"name": "a"}, {"name": "b"}, {"name": "c"}]
        created = []
        errors = []

        async def on_row_error(s, item, err):
            errors.append((item["name"], str(err)))

        # Force every row to fail: the table has an extra NOT NULL-ish path via
        # a bad column name that raises on any insert.
        ok = await chunked_executemany(
            session,
            "INSERT INTO t (name, missing_col) VALUES (:name, :missing_col)",
            rows,
            chunk_size=2,
            on_row_error=on_row_error,
            abort_on_error=True,
        )
        assert ok is False
        # First row of the first chunk fails -> loop aborts immediately.
        assert len(errors) == 1
        assert errors[0][0] == "a"
        assert created == []

    async def test_continue_on_error_processes_all_rows(self, session):
        rows = [{"name": "a"}, {"name": "b"}]
        errors = []

        async def on_row_error(s, item, err):
            errors.append(item["name"])

        ok = await chunked_executemany(
            session,
            "INSERT INTO t (name, missing_col) VALUES (:name, :missing_col)",
            rows,
            chunk_size=1,
            on_row_error=on_row_error,
            abort_on_error=False,
        )
        assert ok is True
        assert errors == ["a", "b"]


class _AtomicSplitSession:
    """Fake session that fails a whole multi-VALUES executemany atomically if
    any row is bad (like MySQL), so the fallback must binary-split to isolate
    the bad row without falling back to one round trip per row."""

    def __init__(self):
        self.executes = []
        self.inserted = []

    async def execute(self, statement, params=None):
        sql = str(statement)
        if isinstance(params, list):
            self.executes.append(("many", len(params)))
            if any(p.get("name") == "bad" for p in params):
                raise Exception("(1062, Duplicate entry 'bad' for key 'name')")
        else:
            self.executes.append(("one", 1))
            if params.get("name") == "bad":
                raise Exception("(1062, Duplicate entry 'bad' for key 'name')")
        rows = params if isinstance(params, list) else [params]
        self.inserted.extend(r["name"] for r in rows if "name" in r)


class TestSplitFallback:
    async def test_single_bad_row_is_isolated_without_row_by_row_retry(self):
        session = _AtomicSplitSession()
        rows = [{"name": f"u{i}"} for i in range(100)]
        rows.insert(50, {"name": "bad"})  # 101 rows, bad at index 50
        created = []
        skipped = []

        async def on_batch_success(s, batch):
            created.extend(item["name"] for item in batch)

        async def on_row_duplicate(s, item, err):
            skipped.append(item["name"])

        ok = await chunked_executemany(
            session,
            "INSERT INTO t (name) VALUES (:name)",
            rows,
            on_batch_success=on_batch_success,
            on_row_duplicate=on_row_duplicate,
        )
        assert ok is True
        assert skipped == ["bad"]
        assert len(created) == 100
        assert len(set(session.inserted)) == 100
        many_calls = [n for kind, n in session.executes if kind == "many"]
        # Binary split: ~16 executemany calls instead of 100+ single-row ones.
        assert len(many_calls) <= 30
        assert max(many_calls) >= 40  # a real multi-row batch was executed
        assert all(n >= 1 for n in many_calls)
