"""Task pool for performance testing multi-agent orchestration."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from src.modes.performance_testing_mode.contracts import (
    TASK_BLOCKED,
    TASK_COMPLETED,
    TASK_FAILED,
    TASK_PENDING,
    TASK_READY,
    TASK_RUNNING,
    TaskStatus,
)

PerfTaskType = Literal[
    "plan",
    "script_generation",
    "smoke_check",
    "execution",
    "analysis",
    "failure_analysis",
]


@dataclass
class PerfTask:
    """A unit of work that can be dispatched to a performance worker agent."""

    task_id: str
    task_type: PerfTaskType
    agent_key: str
    payload: dict[str, Any] = field(default_factory=dict)
    depends_on: list[str] = field(default_factory=list)
    status: TaskStatus = TASK_PENDING
    result: dict[str, Any] | None = None
    error: str = ""
    retries: int = 0
    max_retries: int = 2

    @property
    def retryable(self) -> bool:
        return self.retries < self.max_retries


class PerfTaskPool:
    """Dependency-aware task pool for perf worker dispatch."""

    def __init__(self) -> None:
        self._tasks: dict[str, PerfTask] = {}

    def add_task(self, task: PerfTask) -> None:
        if task.task_id in self._tasks:
            raise ValueError(f"duplicate perf task id: {task.task_id}")
        task.status = TASK_BLOCKED if task.depends_on else TASK_READY
        self._tasks[task.task_id] = task

    def get(self, task_id: str) -> PerfTask | None:
        return self._tasks.get(task_id)

    def all(self) -> list[PerfTask]:
        return list(self._tasks.values())

    def resolve_blocked(self) -> None:
        completed = {
            task.task_id for task in self._tasks.values()
            if task.status == TASK_COMPLETED
        }
        for task in self._tasks.values():
            if task.status == TASK_BLOCKED and set(task.depends_on).issubset(completed):
                task.status = TASK_READY

    def ready(self, limit: int | None = None) -> list[PerfTask]:
        tasks = [task for task in self._tasks.values() if task.status == TASK_READY]
        return tasks[:limit] if limit else tasks

    def mark_running(self, task: PerfTask) -> None:
        task.status = TASK_RUNNING

    def mark_completed(self, task: PerfTask, result: dict[str, Any]) -> None:
        task.status = TASK_COMPLETED
        task.result = result
        task.error = ""

    def mark_failed(self, task: PerfTask, error: str, result: dict[str, Any] | None = None) -> None:
        task.status = TASK_FAILED
        task.error = error
        task.result = result

    def reset_for_retry(self, task: PerfTask, payload: dict[str, Any] | None = None) -> bool:
        if not task.retryable:
            return False
        task.retries += 1
        if payload is not None:
            task.payload = payload
        task.status = TASK_READY if not task.depends_on else TASK_BLOCKED
        task.error = ""
        task.result = None
        return True

    @property
    def has_running(self) -> bool:
        return any(task.status == TASK_RUNNING for task in self._tasks.values())

    @property
    def is_complete(self) -> bool:
        terminal = {TASK_COMPLETED, TASK_FAILED}
        return bool(self._tasks) and all(task.status in terminal for task in self._tasks.values())

    def results(self) -> dict[str, dict[str, Any]]:
        return {
            task.task_id: task.result or {}
            for task in self._tasks.values()
            if task.status == TASK_COMPLETED
        }
