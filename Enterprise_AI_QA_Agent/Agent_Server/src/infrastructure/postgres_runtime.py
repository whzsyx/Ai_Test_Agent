from __future__ import annotations

import psycopg
from psycopg.rows import dict_row

from src.core.config import Settings


def postgres_connect(settings: Settings):
    return psycopg.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        dbname=settings.postgres_database,
        autocommit=True,
        row_factory=dict_row,
    )


def postgres_database_url(settings: Settings) -> str:
    return (
        f"postgresql://{settings.postgres_user}:***@"
        f"{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_database}"
    )
