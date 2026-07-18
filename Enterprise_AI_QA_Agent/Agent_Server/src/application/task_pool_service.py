from __future__ import annotations

from src.runtime.store import SessionStore
from src.schemas.task_pool import TaskPoolPage


class TaskPoolService:
    def __init__(self, *, store: SessionStore) -> None:
        self._store = store

    async def list_tasks_page(
        self,
        limit: int = 24,
        offset: int = 0,
    ) -> TaskPoolPage:
        normalized_limit = max(1, min(int(limit or 24), 100))
        normalized_offset = max(int(offset or 0), 0)
        sessions = await self._store.list_task_pool_sessions(
            limit=normalized_limit + 1,
            offset=normalized_offset,
        )
        return TaskPoolPage(
            items=sessions[:normalized_limit],
            limit=normalized_limit,
            offset=normalized_offset,
            has_more=len(sessions) > normalized_limit,
        )
