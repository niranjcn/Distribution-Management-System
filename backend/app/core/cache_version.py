"""Reusable helpers for the cache_version-based HTTP conditional cache.

`cache_version` (single row, id=1) is the single source of truth for whether
any application data changed. Write paths MUST call `bump_cache_version(session)`
inside the same database transaction as the data change so the bump commits or
rolls back together with the change. The in-memory `CacheVersionManager` (see
cache_version_manager.py) mirrors the committed version so cacheable GET
requests can generate ETags without touching MySQL.
"""

from typing import Optional

from sqlalchemy import text

# The cache_version table must contain exactly one row, always with id = 1.
CACHE_VERSION_ID = 1

# Session.info key set by bump_cache_version so CacheAwareAsyncSession.commit()
# can re-sync the in-memory CacheVersionManager after a successful commit.
CACHE_VERSION_BUMP_FLAG = "_cache_version_bumped"

_SELECT_VERSION_SQL = text(
    "SELECT version FROM cache_version WHERE id = :cid"
)
_BUMP_VERSION_SQL = text(
    "UPDATE cache_version SET version = version + 1 WHERE id = :cid"
)
_ENSURE_ROW_SQL = text(
    "INSERT IGNORE INTO cache_version (id, version) VALUES (:cid, 1)"
)


async def get_cache_version(session) -> Optional[int]:
    """Read the current global cache version from the caller's session.

    Returns None if the single row is missing so startup can fail loudly
    instead of serving an arbitrary ETag.
    """
    result = await session.execute(
        _SELECT_VERSION_SQL, {"cid": CACHE_VERSION_ID}
    )
    row = result.first()
    return int(row[0]) if row else None


async def ensure_cache_version_row(session) -> None:
    """Create the single (id=1, version=1) row if it does not exist yet.

    Must be called from init_db so the row exists before the app serves traffic.
    """
    await session.execute(
        _ENSURE_ROW_SQL, {"cid": CACHE_VERSION_ID}
    )


async def bump_cache_version(session) -> None:
    """Increment the global cache version inside the caller's transaction.

    IMPORTANT: call this immediately before `session.commit()` on every
    transaction that modifies application data. Because it runs in the same
    session/transaction, the bump is committed or rolled back together with the
    data change, so a rolled-back write never invalidates caches.

    Also flags the session so that, once the transaction commits successfully,
    CacheAwareAsyncSession.commit() re-syncs the in-memory CacheVersionManager
    with the newly committed database version.
    """
    await session.execute(
        _BUMP_VERSION_SQL, {"cid": CACHE_VERSION_ID}
    )
    session.info[CACHE_VERSION_BUMP_FLAG] = True


def build_etag(version: int) -> str:
    """Build the quoted HTTP ETag value for a given cache version."""
    return f'"v{version}"'


def etag_matches(if_none_match: Optional[str], etag: str) -> bool:
    """Return True if If-None-Match permits a 304 for `etag`.

    Supports `*`, a single tag, and comma-separated lists. Weak comparison tags
    (`W/"..."`) are treated as equal because we only need to know whether the
    cached representation is still current.
    """
    if not if_none_match:
        return False

    normalized = etag
    if normalized.startswith("W/"):
        normalized = normalized[2:]

    for candidate in (part.strip() for part in if_none_match.split(",")):
        if candidate == "*":
            return True
        if candidate.startswith("W/"):
            candidate = candidate[2:]
        if candidate == normalized:
            return True
    return False
