from slowapi import Limiter
from slowapi.util import get_remote_address


# Shared limiter instance for route decorators and app state.
limiter = Limiter(key_func=get_remote_address)
