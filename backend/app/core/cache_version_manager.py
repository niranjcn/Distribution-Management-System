"""In-memory cache of the current cache_version (single-worker optimization).

Only the current `cache_version.version` integer lives in memory here. ETags,
database rows, query results and API responses are NEVER cached.

ASSUMPTION / SCALING NOTE
-------------------------
This optimization avoids a MySQL read on every cacheable GET by mirroring the
committed cache_version.version in process memory. It is only correct because:

  - there is exactly ONE FastAPI instance and ONE Uvicorn worker, and
  - the backend is the ONLY component that writes to the database.

If the application is later scaled to multiple workers or multiple backend
instances, replace this in-memory manager with either:
  - reading cache_version from MySQL on every request, or
  - a shared invalidation mechanism (e.g. Redis pub/sub or a shared cache).
"""

import logging
import threading

from sqlalchemy import text

from app.core.cache_version import CACHE_VERSION_ID, get_cache_version
from app.database_sqlalchemy import async_session_factory

logger = logging.getLogger(__name__)


class CacheVersionManager:
    """Thread-safe holder of the current cache_version.version integer.

    Reads (`get_version`) never touch MySQL, so ETag generation on GET requests
    stays lightweight. Writes (`update`) are synchronized with the committed
    database value by the caller (see `refresh_from_db`).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._version = 0
        self._initialized = False

    @property
    def initialized(self) -> bool:
        """Whether the manager has been loaded from MySQL at startup."""
        with self._lock:
            return self._initialized

    def get_version(self) -> int:
        """Return the current cached version (never touches MySQL)."""
        with self._lock:
            return self._version

    def update(self, version: int) -> None:
        """Thread-safely replace the cached version with a committed value."""
        with self._lock:
            self._version = int(version)

    async def load_from_db(self) -> None:
        """Load the version from MySQL at startup.

        Raises RuntimeError if the single cache_version row is missing so
        startup fails rather than silently serving from an arbitrary version.
        """
        async with async_session_factory() as session:
            version = await get_cache_version(session)
        if version is None:
            raise RuntimeError(
                "cache_version row (id=1) is missing. Run Alembic migrations "
                "or ensure init_db ran before starting the server."
            )
        self.update(version)
        with self._lock:
            self._initialized = True
        logger.info("cache_version loaded into memory: %d", version)

    async def refresh_from_db(self) -> None:
        """Re-sync the in-memory version with the committed MySQL value.

        Called after every successful data-modifying commit so the in-memory
        value can never drift from what is actually committed in the database.
        Best-effort: a failure is logged and the last known version is kept so
        a completed write request is never broken.
        """
        try:
            async with async_session_factory() as session:
                version = await get_cache_version(session)
        except Exception:
            logger.exception("Failed to refresh cache_version from MySQL")
            return
        if version is not None:
            self.update(version)
            logger.debug("cache_version refreshed: %d", version)


cache_version_manager = CacheVersionManager()
