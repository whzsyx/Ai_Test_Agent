from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from datetime import datetime
from uuid import uuid4

from src.core.config import Settings
from src.domain.models import SessionRecord
from src.infrastructure.postgres_runtime import postgres_connect
from src.infrastructure.storage_utils import ensure_utc_datetime, make_json_safe
from src.schemas.session import (
    ChatMessage,
    ExecutionEvent,
    MessageRole,
    RuntimeMode,
    SessionMode,
    SessionSnapshot,
    SessionStatus,
    ToolApprovalRequest,
    ToolApprovalStatus,
)


class PostgresSessionStore:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._queues: dict[str, asyncio.Queue[ExecutionEvent]] = defaultdict(asyncio.Queue)

    async def initialize(self) -> None:
        await asyncio.to_thread(self._initialize_sync)

    async def save_session(self, session: SessionRecord) -> SessionRecord:
        return await asyncio.to_thread(self._save_session_sync, session)

    async def get_session(self, session_id: str) -> SessionRecord | None:
        return await asyncio.to_thread(self._get_session_sync, session_id, True)

    async def list_sessions(self) -> list[SessionRecord]:
        return await asyncio.to_thread(self._list_sessions_sync)

    async def append_event(self, session_id: str, event: ExecutionEvent) -> None:
        await asyncio.to_thread(self._append_event_sync, session_id, event)
        await self._queues[session_id].put(event)

    async def list_events(self, session_id: str) -> list[ExecutionEvent]:
        return await asyncio.to_thread(self._list_events_sync, session_id)

    def get_queue(self, session_id: str) -> asyncio.Queue[ExecutionEvent]:
        return self._queues[session_id]

    async def save_snapshot(self, session_id: str, snapshot: SessionSnapshot) -> None:
        await asyncio.to_thread(self._save_snapshot_sync, session_id, snapshot)

    async def list_snapshots(self, session_id: str) -> list[SessionSnapshot]:
        return await asyncio.to_thread(self._list_snapshots_sync, session_id)

    async def get_latest_snapshot(self, session_id: str) -> SessionSnapshot | None:
        return await asyncio.to_thread(self._get_latest_snapshot_sync, session_id)

    async def save_approval(self, session_id: str, approval: ToolApprovalRequest) -> None:
        await asyncio.to_thread(self._save_approval_sync, session_id, approval)

    async def list_approvals(self, session_id: str) -> list[ToolApprovalRequest]:
        return await asyncio.to_thread(self._list_approvals_sync, session_id)

    async def resolve_approval(
        self,
        session_id: str,
        approval_id: str,
        status: ToolApprovalStatus,
        reason: str | None = None,
    ) -> ToolApprovalRequest:
        return await asyncio.to_thread(
            self._resolve_approval_sync,
            session_id,
            approval_id,
            status,
            reason,
        )

    def _initialize_sync(self) -> None:
        with postgres_connect(self._settings) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self._settings.postgres_session_table} (
                        id TEXT PRIMARY KEY,
                        title TEXT NOT NULL,
                        status TEXT NOT NULL,
                        session_mode TEXT NOT NULL,
                        runtime_mode TEXT NOT NULL,
                        mode_key TEXT NOT NULL DEFAULT 'default',
                        created_at TIMESTAMPTZ NOT NULL,
                        updated_at TIMESTAMPTZ NOT NULL,
                        preferred_model TEXT NULL,
                        selected_agent TEXT NULL,
                        metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                        event_count INTEGER NOT NULL DEFAULT 0,
                        snapshot_count INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self._settings.postgres_message_table} (
                        id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL,
                        metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb
                    )
                    """
                )
                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self._settings.postgres_event_table} (
                        id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        type TEXT NOT NULL,
                        timestamp TIMESTAMPTZ NOT NULL,
                        payload JSONB NOT NULL DEFAULT '{{}}'::jsonb
                    )
                    """
                )
                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self._settings.postgres_snapshot_table} (
                        id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        version INTEGER NOT NULL,
                        stage TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL,
                        graph_state JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                        UNIQUE(session_id, version)
                    )
                    """
                )
                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {self._settings.postgres_approval_table} (
                        id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        tool_key TEXT NOT NULL,
                        tool_name TEXT NOT NULL,
                        reason TEXT NOT NULL,
                        status TEXT NOT NULL,
                        created_at TIMESTAMPTZ NOT NULL,
                        resolved_at TIMESTAMPTZ NULL,
                        decision_note TEXT NULL,
                        metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb
                    )
                    """
                )
                cur.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{self._settings.postgres_session_table}_updated "
                    f"ON {self._settings.postgres_session_table} (updated_at DESC)"
                )
                cur.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{self._settings.postgres_message_table}_session_created "
                    f"ON {self._settings.postgres_message_table} (session_id, created_at ASC)"
                )
                cur.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{self._settings.postgres_event_table}_session_timestamp "
                    f"ON {self._settings.postgres_event_table} (session_id, timestamp ASC)"
                )
                cur.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{self._settings.postgres_snapshot_table}_session_version "
                    f"ON {self._settings.postgres_snapshot_table} (session_id, version DESC)"
                )
                cur.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{self._settings.postgres_approval_table}_session_created "
                    f"ON {self._settings.postgres_approval_table} (session_id, created_at ASC)"
                )

    def _save_session_sync(self, session: SessionRecord) -> SessionRecord:
        now = datetime.utcnow()
        session.updated_at = now
        with postgres_connect(self._settings) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO {self._settings.postgres_session_table} (
                        id, title, status, session_mode, runtime_mode, mode_key,
                        created_at, updated_at, preferred_model, selected_agent,
                        metadata, event_count, snapshot_count
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s::jsonb, %s, %s
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        title = EXCLUDED.title,
                        status = EXCLUDED.status,
                        session_mode = EXCLUDED.session_mode,
                        runtime_mode = EXCLUDED.runtime_mode,
                        mode_key = EXCLUDED.mode_key,
                        updated_at = EXCLUDED.updated_at,
                        preferred_model = EXCLUDED.preferred_model,
                        selected_agent = EXCLUDED.selected_agent,
                        metadata = EXCLUDED.metadata,
                        event_count = GREATEST({self._settings.postgres_session_table}.event_count, EXCLUDED.event_count),
                        snapshot_count = GREATEST({self._settings.postgres_session_table}.snapshot_count, EXCLUDED.snapshot_count)
                    RETURNING event_count, snapshot_count
                    """,
                    (
                        session.id,
                        session.title,
                        session.status.value,
                        session.session_mode.value,
                        session.runtime_mode.value,
                        session.mode_key,
                        session.created_at,
                        now,
                        session.preferred_model,
                        session.selected_agent,
                        json.dumps(make_json_safe(session.metadata), ensure_ascii=False),
                        int(session.event_count),
                        int(session.snapshot_count),
                    ),
                )
                counts = cur.fetchone() or {}
                session.event_count = int(counts.get("event_count") or 0)
                session.snapshot_count = int(counts.get("snapshot_count") or 0)
                for item in session.messages:
                    if not bool(item.metadata.get("persist_transcript", True)):
                        continue
                    cur.execute(
                        f"""
                        INSERT INTO {self._settings.postgres_message_table} (
                            id, session_id, role, content, created_at, metadata
                        ) VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                        ON CONFLICT (id) DO UPDATE SET
                            session_id = EXCLUDED.session_id,
                            role = EXCLUDED.role,
                            content = EXCLUDED.content,
                            created_at = EXCLUDED.created_at,
                            metadata = EXCLUDED.metadata
                        """,
                        (
                            item.id,
                            session.id,
                            item.role.value,
                            item.content,
                            item.created_at,
                            json.dumps(make_json_safe(item.metadata), ensure_ascii=False),
                        ),
                    )
        return session

    def _get_session_sync(self, session_id: str, include_messages: bool) -> SessionRecord | None:
        with postgres_connect(self._settings) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT * FROM {self._settings.postgres_session_table} WHERE id = %s",
                    (session_id,),
                )
                row = cur.fetchone()
                if row is None:
                    return None
                messages: list[ChatMessage] = []
                if include_messages:
                    cur.execute(
                        f"""
                        SELECT * FROM {self._settings.postgres_message_table}
                        WHERE session_id = %s
                        ORDER BY created_at ASC
                        """,
                        (session_id,),
                    )
                    messages = [_message_from_row(item) for item in (cur.fetchall() or [])]
        return _session_from_row(row, messages)

    def _list_sessions_sync(self) -> list[SessionRecord]:
        with postgres_connect(self._settings) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT * FROM {self._settings.postgres_session_table}
                    ORDER BY updated_at DESC
                    """
                )
                rows = cur.fetchall() or []
        return [_session_from_row(item, []) for item in rows]

    def _append_event_sync(self, session_id: str, event: ExecutionEvent) -> None:
        with postgres_connect(self._settings) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO {self._settings.postgres_event_table} (
                        id, session_id, type, timestamp, payload
                    ) VALUES (%s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        str(uuid4()),
                        session_id,
                        event.type,
                        event.timestamp,
                        json.dumps(make_json_safe(event.payload), ensure_ascii=False),
                    ),
                )
                cur.execute(
                    f"""
                    UPDATE {self._settings.postgres_session_table}
                    SET event_count = event_count + 1,
                        updated_at = %s
                    WHERE id = %s
                    """,
                    (datetime.utcnow(), session_id),
                )

    def _list_events_sync(self, session_id: str) -> list[ExecutionEvent]:
        with postgres_connect(self._settings) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT * FROM {self._settings.postgres_event_table}
                    WHERE session_id = %s
                    ORDER BY timestamp ASC
                    """,
                    (session_id,),
                )
                rows = cur.fetchall() or []
        return [
            ExecutionEvent(
                type=row["type"],
                session_id=session_id,
                timestamp=ensure_utc_datetime(row["timestamp"]) or datetime.utcnow(),
                payload=dict(row.get("payload") or {}),
            )
            for row in rows
        ]

    def _save_snapshot_sync(self, session_id: str, snapshot: SessionSnapshot) -> None:
        now = datetime.utcnow()
        with postgres_connect(self._settings) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO {self._settings.postgres_snapshot_table} (
                        id, session_id, version, stage, created_at, graph_state
                    ) VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (id) DO UPDATE SET
                        session_id = EXCLUDED.session_id,
                        version = EXCLUDED.version,
                        stage = EXCLUDED.stage,
                        created_at = EXCLUDED.created_at,
                        graph_state = EXCLUDED.graph_state
                    """,
                    (
                        snapshot.id,
                        session_id,
                        snapshot.version,
                        snapshot.stage,
                        snapshot.created_at,
                        json.dumps(make_json_safe(snapshot.graph_state), ensure_ascii=False),
                    ),
                )
                cur.execute(
                    f"""
                    UPDATE {self._settings.postgres_session_table}
                    SET snapshot_count = GREATEST(snapshot_count, %s),
                        updated_at = %s
                    WHERE id = %s
                    """,
                    (snapshot.version, now, session_id),
                )

    def _list_snapshots_sync(self, session_id: str) -> list[SessionSnapshot]:
        with postgres_connect(self._settings) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT * FROM {self._settings.postgres_snapshot_table}
                    WHERE session_id = %s
                    ORDER BY version ASC
                    """,
                    (session_id,),
                )
                rows = cur.fetchall() or []
        return [_snapshot_from_row(item) for item in rows]

    def _get_latest_snapshot_sync(self, session_id: str) -> SessionSnapshot | None:
        with postgres_connect(self._settings) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT * FROM {self._settings.postgres_snapshot_table}
                    WHERE session_id = %s
                    ORDER BY version DESC
                    LIMIT 1
                    """,
                    (session_id,),
                )
                row = cur.fetchone()
        return _snapshot_from_row(row) if row else None

    def _save_approval_sync(self, session_id: str, approval: ToolApprovalRequest) -> None:
        now = datetime.utcnow()
        with postgres_connect(self._settings) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO {self._settings.postgres_approval_table} (
                        id, session_id, tool_key, tool_name, reason, status,
                        created_at, resolved_at, decision_note, metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (id) DO UPDATE SET
                        session_id = EXCLUDED.session_id,
                        tool_key = EXCLUDED.tool_key,
                        tool_name = EXCLUDED.tool_name,
                        reason = EXCLUDED.reason,
                        status = EXCLUDED.status,
                        created_at = EXCLUDED.created_at,
                        resolved_at = EXCLUDED.resolved_at,
                        decision_note = EXCLUDED.decision_note,
                        metadata = EXCLUDED.metadata
                    """,
                    (
                        approval.id,
                        session_id,
                        approval.tool_key,
                        approval.tool_name,
                        approval.reason,
                        approval.status.value,
                        approval.created_at,
                        approval.resolved_at,
                        approval.decision_note,
                        json.dumps(make_json_safe(approval.metadata), ensure_ascii=False),
                    ),
                )
                cur.execute(
                    f"UPDATE {self._settings.postgres_session_table} SET updated_at = %s WHERE id = %s",
                    (now, session_id),
                )

    def _list_approvals_sync(self, session_id: str) -> list[ToolApprovalRequest]:
        with postgres_connect(self._settings) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT * FROM {self._settings.postgres_approval_table}
                    WHERE session_id = %s
                    ORDER BY created_at ASC
                    """,
                    (session_id,),
                )
                rows = cur.fetchall() or []
        return [_approval_from_row(item) for item in rows]

    def _resolve_approval_sync(
        self,
        session_id: str,
        approval_id: str,
        status: ToolApprovalStatus,
        reason: str | None = None,
    ) -> ToolApprovalRequest:
        resolved_at = datetime.utcnow()
        with postgres_connect(self._settings) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE {self._settings.postgres_approval_table}
                    SET status = %s,
                        decision_note = %s,
                        resolved_at = %s
                    WHERE id = %s AND session_id = %s
                    RETURNING *
                    """,
                    (status.value, reason, resolved_at, approval_id, session_id),
                )
                row = cur.fetchone()
                if row is None:
                    raise KeyError(approval_id)
                cur.execute(
                    f"UPDATE {self._settings.postgres_session_table} SET updated_at = %s WHERE id = %s",
                    (resolved_at, session_id),
                )
        return _approval_from_row(row)


def _session_from_row(row: dict, messages: list[ChatMessage]) -> SessionRecord:
    return SessionRecord(
        id=row["id"],
        title=row["title"],
        status=SessionStatus(row["status"]),
        session_mode=SessionMode(row["session_mode"]),
        runtime_mode=RuntimeMode(row["runtime_mode"]),
        mode_key=str(row.get("mode_key") or "default"),
        created_at=ensure_utc_datetime(row["created_at"]) or datetime.utcnow(),
        updated_at=ensure_utc_datetime(row["updated_at"]) or datetime.utcnow(),
        preferred_model=row.get("preferred_model"),
        selected_agent=row.get("selected_agent"),
        metadata=dict(row.get("metadata") or {}),
        messages=messages,
        event_count=int(row.get("event_count") or 0),
        snapshot_count=int(row.get("snapshot_count") or 0),
    )


def _message_from_row(row: dict) -> ChatMessage:
    return ChatMessage(
        id=row["id"],
        role=MessageRole(row["role"]),
        content=row["content"],
        created_at=ensure_utc_datetime(row["created_at"]) or datetime.utcnow(),
        metadata=dict(row.get("metadata") or {}),
    )


def _snapshot_from_row(row: dict) -> SessionSnapshot:
    return SessionSnapshot(
        id=row["id"],
        session_id=row["session_id"],
        version=int(row["version"]),
        stage=row["stage"],
        created_at=ensure_utc_datetime(row["created_at"]) or datetime.utcnow(),
        graph_state=dict(row.get("graph_state") or {}),
    )


def _approval_from_row(row: dict) -> ToolApprovalRequest:
    return ToolApprovalRequest(
        id=row["id"],
        session_id=row["session_id"],
        tool_key=row["tool_key"],
        tool_name=row["tool_name"],
        reason=row["reason"],
        status=ToolApprovalStatus(row["status"]),
        created_at=ensure_utc_datetime(row["created_at"]) or datetime.utcnow(),
        resolved_at=ensure_utc_datetime(row.get("resolved_at")),
        decision_note=row.get("decision_note"),
        metadata=dict(row.get("metadata") or {}),
    )
