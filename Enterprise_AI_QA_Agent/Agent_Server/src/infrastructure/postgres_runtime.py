from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from queue import Empty, Full, LifoQueue
from threading import Lock
from typing import Iterator

import psycopg
from psycopg.rows import dict_row

from src.core.config import Settings


@dataclass(frozen=True)
class PostgresHealthStatus:
    ok: bool
    error: str | None = None


class _ConnectionPool:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._available: LifoQueue[psycopg.Connection] = LifoQueue(maxsize=settings.postgres_pool_size)

    def acquire(self) -> psycopg.Connection:
        while True:
            try:
                conn = self._available.get_nowait()
            except Empty:
                return self._create_connection()

            if _is_connection_usable(conn):
                return conn

            _close_quietly(conn)

    def release(self, conn: psycopg.Connection) -> None:
        if not _is_connection_usable(conn):
            _close_quietly(conn)
            return

        try:
            self._available.put_nowait(conn)
        except Full:
            _close_quietly(conn)

    def close_all(self) -> None:
        while True:
            try:
                conn = self._available.get_nowait()
            except Empty:
                return
            _close_quietly(conn)

    def _create_connection(self) -> psycopg.Connection:
        return psycopg.connect(
            host=self._settings.postgres_host,
            port=self._settings.postgres_port,
            user=self._settings.postgres_user,
            password=self._settings.postgres_password,
            dbname=self._settings.postgres_database,
            autocommit=True,
            row_factory=dict_row,
            connect_timeout=self._settings.postgres_connect_timeout_seconds,
        )


_POOL_LOCK = Lock()
_POOLS: dict[tuple[str, int, str, str, str, int, float], _ConnectionPool] = {}


def _pool_key(settings: Settings) -> tuple[str, int, str, str, str, int, float]:
    return (
        settings.postgres_host,
        settings.postgres_port,
        settings.postgres_user,
        settings.postgres_password,
        settings.postgres_database,
        settings.postgres_pool_size,
        settings.postgres_connect_timeout_seconds,
    )


def _get_pool(settings: Settings) -> _ConnectionPool:
    key = _pool_key(settings)
    with _POOL_LOCK:
        pool = _POOLS.get(key)
        if pool is None:
            pool = _ConnectionPool(settings)
            _POOLS[key] = pool
        return pool


def _is_connection_usable(conn: psycopg.Connection | None) -> bool:
    return conn is not None and not conn.closed and not conn.broken


def _close_quietly(conn: psycopg.Connection | None) -> None:
    if conn is None:
        return
    try:
        conn.close()
    except Exception:
        pass


@contextmanager
def postgres_connect(settings: Settings) -> Iterator[psycopg.Connection]:
    pool = _get_pool(settings)
    conn = pool.acquire()
    try:
        yield conn
    finally:
        pool.release(conn)


def postgres_healthcheck(settings: Settings) -> PostgresHealthStatus:
    try:
        with postgres_connect(settings) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
    except Exception as exc:
        return PostgresHealthStatus(ok=False, error=str(exc))
    return PostgresHealthStatus(ok=True)


def postgres_database_url(settings: Settings) -> str:
    return (
        f"postgresql://{settings.postgres_user}:***@"
        f"{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_database}"
    )


def reset_postgres_pools() -> None:
    with _POOL_LOCK:
        pools = list(_POOLS.values())
        _POOLS.clear()

    for pool in pools:
        pool.close_all()
