"""Simple rate limit per client address, kept in memory.

Enough for a single API process behind the reverse proxy. The client address
comes from the proxy headers (uvicorn --proxy-headers).
"""

import math
import threading
import time
from collections import deque

from fastapi import Request

from app.core.config import get_settings
from app.core.errors import AppError

_MAX_KEYS = 10_000
_lock = threading.Lock()
_hits: dict[tuple[str, str], deque[float]] = {}


class RateLimitError(AppError):
    status_code = 429
    code = "rate_limited"

    def __init__(self, retry_after: int):
        super().__init__("Too many requests, try again later")
        self.retry_after = retry_after

    @property
    def headers(self) -> dict[str, str]:
        return {"Retry-After": str(self.retry_after)}


def reset() -> None:
    with _lock:
        _hits.clear()


def rate_limit(name: str, limit: int, window_seconds: int = 60):
    """Dependency that allows `limit` requests per window and client for the group `name`."""

    def dependency(request: Request) -> None:
        if not get_settings().rate_limit_enabled:
            return
        client = request.client.host if request.client else "unknown"
        now = time.monotonic()
        with _lock:
            if len(_hits) > _MAX_KEYS:
                for key in [key for key, hits in _hits.items() if hits[-1] <= now - window_seconds]:
                    del _hits[key]
            hits = _hits.setdefault((name, client), deque())
            while hits and hits[0] <= now - window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                raise RateLimitError(math.ceil(hits[0] + window_seconds - now))
            hits.append(now)

    return dependency
