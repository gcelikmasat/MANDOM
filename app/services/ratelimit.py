"""A small async rate limiter (token bucket).

Keeps us under provider request ceilings (MangaDex: ~5 req/s global). Shared by
the provider client so every API call passes through one polite throttle.
"""

from __future__ import annotations

import asyncio
import time


class RateLimiter:
    """Token-bucket limiter. ``acquire()`` waits until a token is available."""

    def __init__(self, rate_per_second: float, burst: int | None = None) -> None:
        self._rate = max(rate_per_second, 0.1)
        self._capacity = burst if burst is not None else max(1, int(rate_per_second))
        self._tokens = float(self._capacity)
        self._updated = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            while True:
                now = time.monotonic()
                # Refill based on elapsed time.
                self._tokens = min(
                    self._capacity, self._tokens + (now - self._updated) * self._rate
                )
                self._updated = now
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                # Sleep just long enough for the next token to accrue.
                await asyncio.sleep((1.0 - self._tokens) / self._rate)
