from __future__ import annotations

from contextlib import contextmanager
from threading import Lock
from typing import Any, Iterator, Literal

from sqlalchemy import URL, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import ResourceClosedError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from src.core.config import Settings


DatabaseKind = Literal["mysql", "postgres"]


class OrmBase(DeclarativeBase):
    """Base class for future SQLAlchemy ORM models."""


_ENGINE_LOCK = Lock()
_ENGINES: dict[tuple[Any, ...], Engine] = {}
_SESSION_FACTORY_LOCK = Lock()
_SESSION_FACTORIES: dict[tuple[Any, ...], sessionmaker[Session]] = {}


def mysql_url(settings: Settings) -> URL:
    return URL.create(
        "mysql+pymysql",
        username=settings.mysql_user,
        password=settings.mysql_password,
        host=settings.mysql_host,
        port=settings.mysql_port,
        database=settings.mysql_database,
    )


def postgres_url(settings: Settings) -> URL:
    return URL.create(
        "postgresql+psycopg",
        username=settings.postgres_user,
        password=settings.postgres_password,
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=settings.postgres_database,
    )


def mysql_database_url(settings: Settings) -> str:
    return mysql_url(settings).render_as_string(hide_password=True)


def postgres_database_url(settings: Settings) -> str:
    return postgres_url(settings).render_as_string(hide_password=True)


def mysql_engine(settings: Settings) -> Engine:
    key = _mysql_engine_key(settings)
    return _get_or_create_engine(
        key,
        lambda: create_engine(
            mysql_url(settings),
            pool_pre_ping=True,
            connect_args={
                "charset": settings.mysql_charset,
            },
        ),
    )


def postgres_engine(settings: Settings) -> Engine:
    key = _postgres_engine_key(settings)
    return _get_or_create_engine(
        key,
        lambda: create_engine(
            postgres_url(settings),
            pool_pre_ping=True,
            pool_size=settings.postgres_pool_size,
            max_overflow=0,
            connect_args={
                "connect_timeout": settings.postgres_connect_timeout_seconds,
            },
        ),
    )


def mysql_sessionmaker(settings: Settings) -> sessionmaker[Session]:
    return _get_or_create_session_factory(_mysql_engine_key(settings), mysql_engine(settings))


def postgres_sessionmaker(settings: Settings) -> sessionmaker[Session]:
    return _get_or_create_session_factory(_postgres_engine_key(settings), postgres_engine(settings))


@contextmanager
def mysql_session(settings: Settings) -> Iterator[Session]:
    with _session_scope(mysql_sessionmaker(settings)) as session:
        yield session


@contextmanager
def postgres_session(settings: Settings) -> Iterator[Session]:
    with _session_scope(postgres_sessionmaker(settings)) as session:
        yield session


@contextmanager
def mysql_raw_connection(settings: Settings) -> Iterator[SQLAlchemyCursorConnection]:
    with _cursor_connection(mysql_engine(settings)) as conn:
        yield conn


@contextmanager
def postgres_raw_connection(settings: Settings) -> Iterator[SQLAlchemyCursorConnection]:
    with _cursor_connection(postgres_engine(settings)) as conn:
        yield conn


class SQLAlchemyCursorConnection:
    def __init__(self, connection) -> None:
        self._connection = connection

    def cursor(self) -> SQLAlchemyCursor:
        return SQLAlchemyCursor(self._connection)

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()


class SQLAlchemyCursor:
    def __init__(self, connection) -> None:
        self._connection = connection
        self._result = None
        self.lastrowid: int | None = None
        self.rowcount: int = -1

    def __enter__(self) -> SQLAlchemyCursor:
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def execute(self, statement: str, parameters: Any = None) -> SQLAlchemyCursor:
        if parameters is None:
            result = self._connection.exec_driver_sql(statement)
        else:
            result = self._connection.exec_driver_sql(statement, parameters)
        self._set_result(result)
        return self

    def executemany(self, statement: str, seq_of_parameters: Any) -> SQLAlchemyCursor:
        result = self._connection.exec_driver_sql(statement, seq_of_parameters)
        self._set_result(result)
        return self

    def fetchone(self):
        if self._result is None:
            return None
        try:
            return self._result.mappings().fetchone()
        except ResourceClosedError:
            return None

    def fetchall(self):
        if self._result is None:
            return []
        try:
            return self._result.mappings().fetchall()
        except ResourceClosedError:
            return []

    def close(self) -> None:
        if self._result is not None:
            self._result.close()
            self._result = None

    def _set_result(self, result) -> None:
        self._result = result
        self.rowcount = result.rowcount
        self.lastrowid = getattr(result, "lastrowid", None)


def dispose_sqlalchemy_engines(database: DatabaseKind | None = None) -> None:
    with _ENGINE_LOCK:
        items = list(_ENGINES.items())
        if database is None:
            _ENGINES.clear()
        else:
            _ENGINES.clear()
            _ENGINES.update({key: engine for key, engine in items if key[0] != database})

    with _SESSION_FACTORY_LOCK:
        if database is None:
            _SESSION_FACTORIES.clear()
        else:
            keep = {key: factory for key, factory in _SESSION_FACTORIES.items() if key[0] != database}
            _SESSION_FACTORIES.clear()
            _SESSION_FACTORIES.update(keep)

    for key, engine in items:
        if database is None or key[0] == database:
            engine.dispose()


def _get_or_create_engine(key: tuple[Any, ...], factory) -> Engine:
    with _ENGINE_LOCK:
        engine = _ENGINES.get(key)
        if engine is None:
            engine = factory()
            _ENGINES[key] = engine
        return engine


def _get_or_create_session_factory(
    key: tuple[Any, ...],
    engine: Engine,
) -> sessionmaker[Session]:
    with _SESSION_FACTORY_LOCK:
        factory = _SESSION_FACTORIES.get(key)
        if factory is None:
            factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
            _SESSION_FACTORIES[key] = factory
        return factory


@contextmanager
def _session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def _cursor_connection(engine: Engine) -> Iterator[SQLAlchemyCursorConnection]:
    conn = engine.connect()
    try:
        yield SQLAlchemyCursorConnection(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _mysql_engine_key(settings: Settings) -> tuple[Any, ...]:
    return (
        "mysql",
        settings.mysql_host,
        settings.mysql_port,
        settings.mysql_user,
        settings.mysql_password,
        settings.mysql_database,
        settings.mysql_charset,
    )


def _postgres_engine_key(settings: Settings) -> tuple[Any, ...]:
    return (
        "postgres",
        settings.postgres_host,
        settings.postgres_port,
        settings.postgres_user,
        settings.postgres_password,
        settings.postgres_database,
        settings.postgres_pool_size,
        settings.postgres_connect_timeout_seconds,
    )
