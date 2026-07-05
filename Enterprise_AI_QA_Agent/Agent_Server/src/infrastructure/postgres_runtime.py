from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

from src.core.config import Settings
from src.infrastructure.sqlalchemy_runtime import (
    dispose_sqlalchemy_engines,
    postgres_database_url as sqlalchemy_postgres_database_url,
    postgres_engine,
    postgres_raw_connection,
    postgres_session,
    postgres_sessionmaker,
)


@dataclass(frozen=True)
class PostgresHealthStatus:
    ok: bool
    error: str | None = None


@contextmanager
def postgres_connect(settings: Settings) -> Iterator[Any]:
    with postgres_raw_connection(settings) as conn:
        yield conn


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
    return sqlalchemy_postgres_database_url(settings)


def reset_postgres_pools() -> None:
    dispose_sqlalchemy_engines("postgres")
