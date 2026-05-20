from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime
from typing import Protocol

from src.domain.models import SessionRecord
from src.schemas.session import ExecutionEvent, SessionSnapshot, ToolApprovalRequest, ToolApprovalStatus


class SessionStore(Protocol):
    async def initialize(self) -> None: ...
    async def save_session(self, session: SessionRecord) -> SessionRecord: ...
    async def get_session(self, session_id: str) -> SessionRecord | None: ...
    async def list_sessions(
        self,
        limit: int | None = None,
        offset: int = 0,
        mode_key: str | None = None,
    ) -> list[SessionRecord]: ...
    async def append_event(self, session_id: str, event: ExecutionEvent) -> None: ...
    async def list_events(self, session_id: str) -> list[ExecutionEvent]: ...
    def get_queue(self, session_id: str) -> asyncio.Queue[ExecutionEvent]: ...
    async def save_snapshot(self, session_id: str, snapshot: SessionSnapshot) -> None: ...
    async def list_snapshots(self, session_id: str) -> list[SessionSnapshot]: ...
    async def get_latest_snapshot(self, session_id: str) -> SessionSnapshot | None: ...
    async def save_approval(self, session_id: str, approval: ToolApprovalRequest) -> None: ...
    async def list_approvals(self, session_id: str) -> list[ToolApprovalRequest]: ...
    async def resolve_approval(
        self,
        session_id: str,
        approval_id: str,
        status: ToolApprovalStatus,
        reason: str | None = None,
    ) -> ToolApprovalRequest: ...
    async def delete_session(self, session_id: str) -> bool: ...


class InMemorySessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionRecord] = {}
        self._events: dict[str, list[ExecutionEvent]] = defaultdict(list)
        self._queues: dict[str, asyncio.Queue[ExecutionEvent]] = defaultdict(asyncio.Queue)
        self._snapshots: dict[str, list[SessionSnapshot]] = defaultdict(list)
        self._approvals: dict[str, dict[str, ToolApprovalRequest]] = defaultdict(dict)
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        return None

    async def save_session(self, session: SessionRecord) -> SessionRecord:
        async with self._lock:
            session.updated_at = datetime.utcnow()
            self._sessions[session.id] = session
            return session

    async def get_session(self, session_id: str) -> SessionRecord | None:
        return self._sessions.get(session_id)

    async def list_sessions(
        self,
        limit: int | None = None,
        offset: int = 0,
        mode_key: str | None = None,
    ) -> list[SessionRecord]:
        sessions = sorted(self._sessions.values(), key=lambda item: item.updated_at, reverse=True)
        if mode_key:
            sessions = [item for item in sessions if item.mode_key == mode_key]
        start = max(int(offset or 0), 0)
        if limit is None:
            return sessions[start:]
        size = max(int(limit or 0), 0)
        if size <= 0:
            return []
        return sessions[start : start + size]

    async def append_event(self, session_id: str, event: ExecutionEvent) -> None:
        session = self._sessions.get(session_id)
        if session is not None:
            session.event_count += 1
            session.updated_at = datetime.utcnow()
        self._events[session_id].append(event)
        await self._queues[session_id].put(event)

    async def list_events(self, session_id: str) -> list[ExecutionEvent]:
        return list(self._events.get(session_id, []))

    def get_queue(self, session_id: str) -> asyncio.Queue[ExecutionEvent]:
        return self._queues[session_id]

    async def save_snapshot(self, session_id: str, snapshot: SessionSnapshot) -> None:
        session = self._sessions.get(session_id)
        if session is not None:
            session.snapshot_count = max(session.snapshot_count, snapshot.version)
            session.updated_at = datetime.utcnow()
        self._snapshots[session_id].append(snapshot)

    async def list_snapshots(self, session_id: str) -> list[SessionSnapshot]:
        return list(self._snapshots.get(session_id, []))

    async def get_latest_snapshot(self, session_id: str) -> SessionSnapshot | None:
        snapshots = self._snapshots.get(session_id, [])
        return snapshots[-1] if snapshots else None

    async def save_approval(self, session_id: str, approval: ToolApprovalRequest) -> None:
        self._approvals[session_id][approval.id] = approval
        session = self._sessions.get(session_id)
        if session is not None:
            session.updated_at = datetime.utcnow()

    async def list_approvals(self, session_id: str) -> list[ToolApprovalRequest]:
        return sorted(self._approvals.get(session_id, {}).values(), key=lambda item: item.created_at)

    async def resolve_approval(
        self,
        session_id: str,
        approval_id: str,
        status: ToolApprovalStatus,
        reason: str | None = None,
    ) -> ToolApprovalRequest:
        if session_id not in self._approvals or approval_id not in self._approvals[session_id]:
            raise KeyError(approval_id)
        approval = self._approvals[session_id][approval_id]
        approval.status = status
        approval.decision_note = reason
        approval.resolved_at = datetime.utcnow()
        return approval

    async def delete_session(self, session_id: str) -> bool:
        async with self._lock:
            if session_id not in self._sessions:
                return False
            del self._sessions[session_id]
            self._events.pop(session_id, None)
            self._queues.pop(session_id, None)
            self._snapshots.pop(session_id, None)
            self._approvals.pop(session_id, None)
            return True
