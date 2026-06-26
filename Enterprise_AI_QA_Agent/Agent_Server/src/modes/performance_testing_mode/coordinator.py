"""Performance testing subagent coordinator.

Coordinates dependency-aware worker dispatch for planner/script/runner/analyst
tasks and emits progress events for streaming clients.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from src.modes.performance_testing_mode.contracts import TASK_FAILED
from src.modes.performance_testing_mode.task_pool import PerfTask, PerfTaskPool

logger = logging.getLogger(__name__)


class PerfCoordinator:
    """Coordinates subagent dispatch and progress events for performance testing."""

    def __init__(self, coordinator_runtime_service=None):
        self._coordinator_runtime_service = coordinator_runtime_service

    def set_coordinator_runtime_service(self, svc) -> None:
        self._coordinator_runtime_service = svc

    async def dispatch_worker(
        self,
        agent_key: str,
        prompt: str,
        description: str = "",
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Dispatch a single worker agent and await result."""
        if not self._coordinator_runtime_service:
            logger.warning("No coordinator runtime service available for dispatch")
            return {"status": "error", "summary": "coordinator service unavailable"}

        try:
            result = await self._coordinator_runtime_service.dispatch_worker(
                agent_key=agent_key,
                prompt=prompt,
                description=description,
                context=context or {},
            )
            return result if isinstance(result, dict) else {"status": "ok", "result": result}
        except Exception as e:
            logger.warning(f"Worker dispatch failed: {e}")
            return {"status": "error", "summary": str(e)}

    async def emit_progress(
        self,
        phase: str,
        message: str,
        session_id: str = "",
        data: dict[str, Any] | None = None,
    ) -> None:
        """Emit a progress event for SSE streaming."""
        if self._coordinator_runtime_service and hasattr(
            self._coordinator_runtime_service, "emit_event"
        ):
            try:
                await self._coordinator_runtime_service.emit_event(
                    event_type="performance_testing_progress",
                    session_id=session_id,
                    data={
                        "phase": phase,
                        "message": message,
                        **(data or {}),
                    },
                )
            except Exception:
                pass


class PerfSubagentCoordinator(PerfCoordinator):
    """Execute performance tasks through worker agents.

    This keeps the state machine in ``runtime.py`` small while allowing script
    generation, execution, analysis, and failure diagnosis to run as explicit
    worker tasks.
    """

    def __init__(
        self,
        pool: PerfTaskPool,
        coordinator_runtime_service=None,
        *,
        session_id: str = "",
        max_workers: int = 2,
        poll_interval_seconds: float = 0.2,
    ):
        super().__init__(coordinator_runtime_service)
        self._pool = pool
        self._session_id = session_id
        self._max_workers = max(1, max_workers)
        self._poll_interval_seconds = max(0.05, poll_interval_seconds)

    async def run_all(self) -> list[PerfTask]:
        """Run all tasks in dependency order and retry eligible failures."""
        await self._run_pass()
        await self._retry_failed()
        return self._pool.all()

    async def _run_pass(self) -> None:
        while not self._pool.is_complete:
            self._pool.resolve_blocked()
            batch = self._pool.ready(limit=self._max_workers)
            if not batch:
                if self._pool.has_running:
                    await asyncio.sleep(self._poll_interval_seconds)
                    continue
                break
            await asyncio.gather(*(self._dispatch_task(task) for task in batch))

    async def _retry_failed(self) -> None:
        for task in self._pool.all():
            if task.status == TASK_FAILED and task.retryable:
                self._pool.reset_for_retry(task)
        if any(task.status != TASK_FAILED for task in self._pool.all()):
            await self._run_pass()

    async def _dispatch_task(self, task: PerfTask) -> None:
        self._pool.mark_running(task)
        await self.emit_progress(
            phase=task.task_type,
            message=f"开始执行性能测试子任务: {task.task_id}",
            session_id=self._session_id,
            data={"task_id": task.task_id, "agent_key": task.agent_key},
        )

        try:
            result = await self.dispatch_worker(
                agent_key=task.agent_key,
                prompt=self._build_worker_prompt(task),
                description=f"perf-{task.task_type}-{task.task_id}",
                context={"task_id": task.task_id, "task_type": task.task_type, **task.payload},
            )
        except Exception as exc:
            self._pool.mark_failed(task, str(exc))
            return

        ok = bool(result.get("ok", result.get("status") in {"ok", "completed"}))
        if ok:
            self._pool.mark_completed(task, result)
            await self.emit_progress(
                phase=task.task_type,
                message=f"性能测试子任务完成: {task.task_id}",
                session_id=self._session_id,
                data={"task_id": task.task_id, "agent_key": task.agent_key},
            )
            return

        self._pool.mark_failed(task, str(result.get("summary") or result.get("error") or "worker failed"), result)

    def _build_worker_prompt(self, task: PerfTask) -> str:
        return (
            f"你是性能测试子任务执行智能体。\n"
            f"任务ID: {task.task_id}\n"
            f"任务类型: {task.task_type}\n"
            f"请基于上下文 payload 执行对应工具，并返回结构化 JSON，至少包含 ok/status/summary。\n"
            f"payload: {task.payload}"
        )
