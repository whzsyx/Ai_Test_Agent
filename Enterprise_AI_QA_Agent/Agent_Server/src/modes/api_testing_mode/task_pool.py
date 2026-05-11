"""Task pool: lifecycle management for API test tasks.

Maintains the state machine for each task and provides queries for the
coordinator to pick the next batch of ready tasks.
"""
from __future__ import annotations

from src.modes.api_testing_mode.campaign_state import ApiTestTask
from src.modes.api_testing_mode.contracts import (
    TASK_BLOCKED,
    TASK_COMPLETED,
    TASK_FAILED,
    TASK_PENDING,
    TASK_READY,
    TASK_RUNNING,
    TASK_SKIPPED,
)


class ApiTaskPool:
    """In-memory task pool for one campaign."""

    def __init__(self, tasks: list[ApiTestTask] | None = None) -> None:
        self._tasks: dict[str, ApiTestTask] = {}
        for task in tasks or []:
            self._tasks[task.task_id] = task

    @property
    def all_tasks(self) -> list[ApiTestTask]:
        return list(self._tasks.values())

    @property
    def is_complete(self) -> bool:
        return all(
            task.status in {TASK_COMPLETED, TASK_FAILED, TASK_SKIPPED}
            for task in self._tasks.values()
        )

    @property
    def has_running(self) -> bool:
        return any(task.status == TASK_RUNNING for task in self._tasks.values())

    def ready_tasks(self) -> list[ApiTestTask]:
        return [task for task in self._tasks.values() if task.status == TASK_READY]

    def blocked_tasks(self) -> list[ApiTestTask]:
        return [task for task in self._tasks.values() if task.status == TASK_BLOCKED]

    def running_tasks(self) -> list[ApiTestTask]:
        return [task for task in self._tasks.values() if task.status == TASK_RUNNING]

    def completed_tasks(self) -> list[ApiTestTask]:
        return [task for task in self._tasks.values() if task.status == TASK_COMPLETED]

    def failed_tasks(self) -> list[ApiTestTask]:
        return [task for task in self._tasks.values() if task.status == TASK_FAILED]

    def get(self, task_id: str) -> ApiTestTask | None:
        return self._tasks.get(task_id)

    def mark_running(self, task_id: str) -> None:
        task = self._tasks.get(task_id)
        if task is not None:
            task.status = TASK_RUNNING

    def mark_completed(self, task_id: str) -> None:
        task = self._tasks.get(task_id)
        if task is not None:
            task.status = TASK_COMPLETED
            self._release_dependents(task_id)

    def mark_failed(self, task_id: str, error: str = "") -> None:
        task = self._tasks.get(task_id)
        if task is not None:
            task.status = TASK_FAILED
            task.last_error = error
            self._skip_dependents(task_id)

    def mark_skipped(self, task_id: str, reason: str = "") -> None:
        task = self._tasks.get(task_id)
        if task is not None:
            task.status = TASK_SKIPPED
            task.last_error = reason
            self._skip_dependents(task_id)

    def resolve_blocked(self) -> int:
        """Promote blocked tasks to ready if all their dependencies are satisfied."""
        promoted = 0
        for task in list(self._tasks.values()):
            if task.status != TASK_BLOCKED:
                continue
            if self._dependencies_satisfied(task):
                task.status = TASK_READY
                promoted += 1
        return promoted

    def summary(self) -> dict[str, int]:
        counts: dict[str, int] = {
            TASK_PENDING: 0,
            TASK_BLOCKED: 0,
            TASK_READY: 0,
            TASK_RUNNING: 0,
            TASK_COMPLETED: 0,
            TASK_FAILED: 0,
            TASK_SKIPPED: 0,
        }
        for task in self._tasks.values():
            counts[task.status] = counts.get(task.status, 0) + 1
        return counts

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _dependencies_satisfied(self, task: ApiTestTask) -> bool:
        for dep_id in task.depends_on:
            dep = self._tasks.get(dep_id)
            if dep is None:
                continue
            if dep.status != TASK_COMPLETED:
                return False
        return True

    def _release_dependents(self, completed_task_id: str) -> None:
        for task in self._tasks.values():
            if task.status != TASK_BLOCKED:
                continue
            if completed_task_id in task.depends_on:
                if self._dependencies_satisfied(task):
                    task.status = TASK_READY

    def _skip_dependents(self, failed_task_id: str) -> None:
        for task in self._tasks.values():
            if task.status in {TASK_BLOCKED, TASK_PENDING}:
                if failed_task_id in task.depends_on:
                    task.status = TASK_SKIPPED
                    task.last_error = f"Skipped because dependency {failed_task_id} failed."
                    self._skip_dependents(task.task_id)


__all__ = ["ApiTaskPool"]
