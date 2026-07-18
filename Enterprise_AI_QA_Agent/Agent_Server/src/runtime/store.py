from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime
from typing import Protocol

from src.domain.models import SessionRecord
from src.schemas.session import (
    ExecutionEvent,
    SessionMode,
    SessionSnapshot,
    ToolApprovalRequest,
    ToolApprovalStatus,
)
from src.schemas.task_pool import TaskPoolSessionSummary


class SessionStore(Protocol):
    async def initialize(self) -> None: ...
    async def save_session(self, session: SessionRecord) -> SessionRecord: ...
    async def get_session(self, session_id: str) -> SessionRecord | None: ...
    async def list_sessions(
        self,
        limit: int | None = None,
        offset: int = 0,
        mode_key: str | None = None,
        cursor_before: datetime | None = None,
    ) -> list[SessionRecord]: ...
    async def list_task_pool_sessions(
        self,
        limit: int = 24,
        offset: int = 0,
    ) -> list[TaskPoolSessionSummary]: ...
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
    async def count_sessions(self, before: datetime | None = None, after: datetime | None = None) -> int: ...
    async def count_sessions_by_status(self) -> dict[str, int]: ...
    async def delete_sessions_before(self, cutoff: datetime | None = None) -> int: ...
    async def get_session_date_range(self) -> dict[str, datetime | None]: ...
    async def bulk_export(self, progress_fn: object = None) -> list[dict]: ...


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
        cursor_before: datetime | None = None,
    ) -> list[SessionRecord]:
        sessions = sorted(self._sessions.values(), key=lambda item: item.updated_at, reverse=True)
        if mode_key:
            sessions = [item for item in sessions if item.mode_key == mode_key]
        if cursor_before is not None:
            sessions = [s for s in sessions if s.updated_at < cursor_before]
        start = max(int(offset or 0), 0)
        if limit is None:
            return sessions[start:]
        size = max(int(limit or 0), 0)
        if size <= 0:
            return []
        return sessions[start : start + size]

    async def list_task_pool_sessions(
        self,
        limit: int = 24,
        offset: int = 0,
    ) -> list[TaskPoolSessionSummary]:
        sessions = sorted(
            (
                item
                for item in self._sessions.values()
                if item.mode_key == "code_review"
                or item.session_mode == SessionMode.background_task
            ),
            key=lambda item: item.updated_at,
            reverse=True,
        )
        start = max(int(offset or 0), 0)
        size = max(int(limit or 0), 0)
        visible = sessions[start : start + size]
        rows = []
        for session in visible:
            metadata = session.metadata if isinstance(session.metadata, dict) else {}
            workers = [
                dict(item)
                for item in metadata.get("worker_dispatches", [])
                if isinstance(item, dict)
            ]
            rows.append(
                TaskPoolSessionSummary(
                    id=session.id,
                    title=session.title,
                    status=session.status,
                    session_mode=session.session_mode,
                    runtime_mode=session.runtime_mode,
                    mode_key=session.mode_key,
                    created_at=session.created_at,
                    updated_at=session.updated_at,
                    selected_agent=session.selected_agent,
                    worker_dispatches=workers,
                    parent_session_id=str(
                        metadata.get("parent_session_id") or ""
                    ).strip(),
                )
            )
        return rows

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

    async def count_sessions(self, before: datetime | None = None, after: datetime | None = None) -> int:
        if before is None and after is None:
            return len(self._sessions)
        count = 0
        for s in self._sessions.values():
            t = s.updated_at or s.created_at
            if after and t < after:
                continue
            if before and t >= before:
                continue
            count += 1
        return count

    async def count_sessions_by_status(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for s in self._sessions.values():
            key = s.status.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    async def delete_sessions_before(self, cutoff: datetime | None = None) -> int:
        async with self._lock:
            if cutoff is None:
                ids = list(self._sessions.keys())
            else:
                ids = [sid for sid, s in self._sessions.items() if (s.updated_at or s.created_at) < cutoff]
            for sid in ids:
                del self._sessions[sid]
                self._events.pop(sid, None)
                self._queues.pop(sid, None)
                self._snapshots.pop(sid, None)
                self._approvals.pop(sid, None)
            return len(ids)

    async def get_session_date_range(self) -> dict[str, datetime | None]:
        if not self._sessions:
            return {"oldest": None, "newest": None}
        dates = [s.updated_at or s.created_at for s in self._sessions.values()]
        return {"oldest": min(dates), "newest": max(dates)}

    async def bulk_export(self, progress_fn=None) -> list[dict]:
        sessions = sorted(self._sessions.values(), key=lambda s: s.updated_at, reverse=True)
        bundle: list[dict] = []
        for s in sessions:
            def _iso(v: object) -> str | None:
                return v.isoformat() if hasattr(v, "isoformat") else None
            sid = s.id
            bundle.append({
                "id": sid,
                "title": s.title,
                "status": s.status.value if hasattr(s.status, "value") else str(s.status),
                "session_mode": s.session_mode.value if hasattr(s.session_mode, "value") else str(s.session_mode),
                "runtime_mode": s.runtime_mode.value if hasattr(s.runtime_mode, "value") else str(s.runtime_mode),
                "mode_key": s.mode_key,
                "created_at": _iso(s.created_at),
                "updated_at": _iso(s.updated_at),
                "preferred_model": s.preferred_model,
                "selected_agent": s.selected_agent,
                "metadata": s.metadata,
                "event_count": s.event_count,
                "snapshot_count": s.snapshot_count,
                "messages": [
                    {"id": m.id, "role": m.role.value if hasattr(m.role, "value") else str(m.role),
                     "content": m.content, "created_at": _iso(m.created_at), "metadata": m.metadata}
                    for m in (s.messages or [])
                ],
                "events": [
                    {"type": e.type, "session_id": sid, "timestamp": _iso(e.timestamp), "payload": e.payload}
                    for e in self._events.get(sid, [])
                ],
                "snapshots": [
                    {"id": sn.id, "session_id": sid, "version": sn.version, "stage": sn.stage,
                     "created_at": _iso(sn.created_at), "graph_state": sn.graph_state}
                    for sn in self._snapshots.get(sid, [])
                ],
                "approvals": [
                    {"id": a.id, "session_id": sid, "tool_key": a.tool_key, "tool_name": a.tool_name,
                     "reason": a.reason, "status": a.status.value if hasattr(a.status, "value") else str(a.status),
                     "created_at": _iso(a.created_at), "resolved_at": _iso(a.resolved_at),
                     "decision_note": a.decision_note, "metadata": a.metadata}
                    for a in sorted(self._approvals.get(sid, {}).values(), key=lambda x: x.created_at)
                ],
            })
        return bundle
