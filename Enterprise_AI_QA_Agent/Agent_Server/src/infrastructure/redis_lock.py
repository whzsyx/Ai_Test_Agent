"""Small synchronous Redis lock wrapper for cross-worker critical sections."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from redis import Redis
from redis.exceptions import LockError, RedisError


class RedisLockManager:
    """Owns Redis connections and exposes fail-closed distributed locks."""

    def __init__(
        self,
        redis_url: str,
        *,
        ttl_seconds: int = 600,
        wait_seconds: float = 30.0,
        client: Redis | None = None,
    ) -> None:
        self._redis_url = str(redis_url or "").strip()
        self._ttl_seconds = max(5, int(ttl_seconds))
        self._wait_seconds = max(0.0, float(wait_seconds))
        self._client = client

    def _get_client(self) -> Redis:
        if self._client is None:
            if not self._redis_url:
                raise RuntimeError("Redis URL is required for the Agent Mail authentication lock.")
            self._client = Redis.from_url(
                self._redis_url,
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
            )
        return self._client

    @contextmanager
    def acquire(self, key: str) -> Iterator[None]:
        """Acquire one ownership-safe Redis lock or fail without running the caller."""

        try:
            lock = self._get_client().lock(
                key,
                timeout=self._ttl_seconds,
                blocking_timeout=self._wait_seconds,
                thread_local=False,
            )
            acquired = lock.acquire(blocking=True)
        except RedisError as exc:
            raise RuntimeError(f"Redis Agent Mail auth lock is unavailable: {exc}") from exc

        if not acquired:
            raise RuntimeError(
                f"Timed out waiting for Agent Mail auth lock '{key}' "
                f"after {self._wait_seconds:g}s."
            )

        try:
            yield
        finally:
            try:
                lock.release()
            except (LockError, RedisError):
                # The TTL may have elapsed after a stalled CLI process. Never delete a
                # lock now owned by another worker; redis-py already enforces ownership.
                pass
