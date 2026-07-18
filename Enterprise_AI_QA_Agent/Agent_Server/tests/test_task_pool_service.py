from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from src.application.task_pool_service import TaskPoolService
from src.schemas.session import RuntimeMode, SessionMode, SessionStatus
from src.schemas.task_pool import TaskPoolSessionSummary


class _Store:
    def __init__(self, sessions: list[TaskPoolSessionSummary]) -> None:
        self.sessions = sessions
        self.calls: list[dict] = []

    async def list_task_pool_sessions(self, **kwargs):
        self.calls.append(kwargs)
        return self.sessions


def _task(session_id: str, updated_at: datetime) -> TaskPoolSessionSummary:
    return TaskPoolSessionSummary(
        id=session_id,
        title=f"Task {session_id}",
        status=SessionStatus.completed,
        session_mode=SessionMode.background_task,
        runtime_mode=RuntimeMode.background,
        mode_key="performance_testing",
        created_at=updated_at - timedelta(minutes=1),
        updated_at=updated_at,
        selected_agent="performance-testing-agent",
        worker_dispatches=[{"task_id": session_id, "status": "completed"}],
        parent_session_id="parent",
    )


def test_task_pool_page_limits_lightweight_rows_and_reports_more():
    now = datetime.utcnow()
    store = _Store([_task("first", now), _task("second", now - timedelta(minutes=1))])
    service = TaskPoolService(store=store)  # type: ignore[arg-type]

    page = asyncio.run(service.list_tasks_page(limit=1, offset=3))

    assert store.calls == [{"limit": 2, "offset": 3}]
    assert page.has_more is True
    assert page.limit == 1
    assert page.offset == 3
    assert [item.id for item in page.items] == ["first"]
    assert page.items[0].worker_dispatches == [
        {"task_id": "first", "status": "completed"}
    ]
