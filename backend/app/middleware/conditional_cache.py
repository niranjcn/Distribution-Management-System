from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings
from app.core.cache_version import build_etag, etag_matches
from app.core.cache_version_manager import cache_version_manager

# Browser caches the response but must always revalidate with the ETag.
# `no-cache` + `max-age=0` are semantically equivalent: the response is stored
# but immediately stale, forcing a conditional revalidation (If-None-Match)
# before every reuse. `max-age=0` also gives the response an explicit freshness
# lifetime, which helps stricter cache implementations store it at all.
CACHE_CONTROL = "private, no-cache, max-age=0"

# GET paths that must never be served from the browser's HTTP cache:
# - /auth/me and /notifications return user-specific data keyed by URL only,
#   so a shared global ETag would leak one user's data to the next user in the
#   same browser session.
# - /uploads serves file content, whose freshness is not described by the
#   global cache version.
_EXCLUDED_PATH_PREFIXES = (
    f"{settings.API_V1_PREFIX}/auth/me",
    f"{settings.API_V1_PREFIX}/notifications",
    f"{settings.API_V1_PREFIX}/uploads",
)


class ConditionalCacheMiddleware(BaseHTTPMiddleware):
    """Implements HTTP conditional caching (ETag / 304) for GET endpoints.

    Flow per cacheable GET request:
      1. Read the current version from the in-memory CacheVersionManager
         (no MySQL access).
      2. If If-None-Match matches the current ETag -> return 304 immediately.
         The endpoint is never invoked, so no application table is queried and
         no JSON is serialized.
      3. Otherwise run the endpoint and attach ETag + Cache-Control headers to
         the 200 response so the browser can revalidate on the next request.

    Single-worker assumption: the in-memory version is only correct while there
    is one FastAPI instance / one Uvicorn worker and the backend is the only
    database writer. See app/core/cache_version_manager.py for scaling notes.
    """

    async def dispatch(self, request: Request, call_next):
        if request.method not in ("GET", "HEAD"):
            return await call_next(request)

        path = request.url.path
        if not path.startswith(settings.API_V1_PREFIX):
            return await call_next(request)
        if path.startswith(_EXCLUDED_PATH_PREFIXES):
            return await call_next(request)

        etag = build_etag(cache_version_manager.get_version())

        if etag_matches(request.headers.get("if-none-match"), etag):
            return Response(
                status_code=304,
                headers={"ETag": etag, "Cache-Control": CACHE_CONTROL},
            )

        response = await call_next(request)

        # Only cacheable 2xx responses get cache headers; errors and redirects
        # must never be cached.
        if 200 <= response.status_code < 300:
            response.headers.setdefault("ETag", etag)
            response.headers.setdefault("Cache-Control", CACHE_CONTROL)

        return response
