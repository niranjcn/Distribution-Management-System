import time
from typing import Dict, Any, Callable, Awaitable, Optional

_cache_store: Dict[str, Any] = {}
_cache_expiry: Dict[str, float] = {}
_cache_max_size = 100


async def cached(ttl_seconds: int, key: str, factory: Callable[[], Awaitable[Any]]) -> Any:
    now = time.time()
    if key in _cache_store and now < _cache_expiry.get(key, 0):
        return _cache_store[key]
    if len(_cache_store) >= _cache_max_size:
        _cache_store.clear()
        _cache_expiry.clear()
    value = await factory()
    _cache_store[key] = value
    _cache_expiry[key] = now + ttl_seconds
    return value


def invalidate_cache(key: Optional[str] = None) -> None:
    if key:
        _cache_store.pop(key, None)
        _cache_expiry.pop(key, None)
    else:
        _cache_store.clear()
        _cache_expiry.clear()
