"""Tiny in-memory sliding-window rate limiter (per client IP).

Protects the LLM API key when the app is public. Single-process only: with several
workers each keeps its own counts. Behind a proxy set TRUST_PROXY=1 so the real
client address is read from X-Forwarded-For.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from . import config


class RateLimiter:
    def __init__(self, limit: int, window: float = 60.0) -> None:
        self.limit, self.window = limit, window
        self.hits: dict[str, deque[float]] = defaultdict(deque)
        self.lock = threading.Lock()

    def check(self, key: str, now: float | None = None) -> float:
        """Return 0 if allowed, otherwise seconds until the next request is allowed."""
        now = time.monotonic() if now is None else now
        with self.lock:
            q = self.hits[key]
            while q and now - q[0] >= self.window:
                q.popleft()
            if len(q) >= self.limit:
                return self.window - (now - q[0])
            q.append(now)
            if len(self.hits) > 5000:  # drop idle clients
                for k in [k for k, v in self.hits.items() if not v or now - v[-1] >= self.window]:
                    del self.hits[k]
            return 0.0


limiter = RateLimiter(config.RATE_LIMIT_PER_MIN)


def client_key(request: Request) -> str:
    if config.TRUST_PROXY:
        fwd = request.headers.get("x-forwarded-for", "")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def rate_limit(request: Request) -> None:
    if config.RATE_LIMIT_PER_MIN <= 0:
        return
    wait = limiter.check(client_key(request))
    if wait:
        raise HTTPException(
            status_code=429,
            detail="Too many questions. Please wait a moment and try again.",
            headers={"Retry-After": str(int(wait) + 1)},
        )
