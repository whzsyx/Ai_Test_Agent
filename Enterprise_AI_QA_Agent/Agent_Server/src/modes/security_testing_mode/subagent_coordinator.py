"""Dispatch security testing tasks to worker sessions via ``subagent-dispatch``."""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from src.modes.security_testing_mode.agent import SURFACE_WORKER_MAP, SECURITY_RECON_WORKER_KEY
from src.modes.security_testing_mode.campaign_state import (
    AgentActivityRecord,
    SecurityTask,
)
from src.modes.security_testing_mode.contracts import (
    MAX_CONCURRENT_WORKERS,
    TASK_COMPLETED,
    TASK_FAILED,
    TASK_RUNNING,
    TOOL_EXEC_TIMEOUT_SECONDS,
)
from src.modes.security_testing_mode.task_pool import SecurityTaskPool

logger = logging.getLogger(__name__)


class SecuritySubagentCoordinator:
    """Orchestrate security task execution through background worker sessions."""

    def __init__(
        self,
        *,
        pool: SecurityTaskPool,
        coordinator_runtime_service: Any,
        session_store: Any,
        parent_context: dict[str, Any],
        max_workers: int = MAX_CONCURRENT_WORKERS,
        worker_model_key: str | None = None,
        poll_interval_seconds: float = 0.5,
    ) -> None:
        self._pool = pool
        self._coordinator_runtime_service = coordinator_runtime_service
        self._session_store = session_store
        self._parent_context = parent_context
        self._max_workers = max(1, max_workers)
        self._worker_model_key = worker_model_key
        self._poll_interval_seconds = max(0.1, poll_interval_seconds)
        self._activities: list[AgentActivityRecord] = []
        self._active_resource_locks: set[str] = set()

    @property
    def activities(self) -> list[AgentActivityRecord]:
        return list(self._activities)

    async def run_all(self) -> list[SecurityTask]:
        """Execute all tasks in the pool, respecting dependencies and concurrency."""
        while not self._pool.is_complete:
            self._pool.resolve_blocked()
            batch = self._select_batch()
            if not batch:
                if self._pool.has_running:
                    await asyncio.sleep(self._poll_interval_seconds)
                    continue
                break
            await self._dispatch_batch(batch)
            self._pool.resolve_blocked()

        # Retry failed tasks
        await self._retry_failed()

        return self._pool.all_tasks

    async def _retry_failed(self) -> None:
        """Retry tasks that are eligible for retry."""
        retryable = self._pool.retryable_tasks()
        if not retryable:
            return

        for task in retryable:
            self._pool.reset_for_retry(task.task_id)

        # Run another pass
        while not self._pool.is_complete:
            self._pool.resolve_blocked()
            batch = self._select_batch()
            if not batch:
                if self._pool.has_running:
                    await asyncio.sleep(self._poll_interval_seconds)
                    continue
                break
            await self._dispatch_batch(batch)
            self._pool.resolve_blocked()

    def _select_batch(self) -> list[SecurityTask]:
        """Select the next batch of tasks to dispatch."""
        ready = self._pool.ready_tasks()
        if not ready:
            return []

        # Sort by priority: tasks with fewer dependencies first, lower risk first
        ready.sort(key=lambda t: (len(t.depends_on), t.risk_level != "info"))

        batch: list[SecurityTask] = []
        running_count = len(self._pool.running_tasks())
        available_slots = self._max_workers - running_count

        for task in ready:
            if len(batch) >= available_slots:
                break
            if self._has_resource_conflict(task, batch):
                continue
            # High-risk tasks run alone
            if task.requires_approval:
                if not batch:
                    batch.append(task)
                break
            batch.append(task)

        return batch

    def _has_resource_conflict(self, task: SecurityTask, batch: list[SecurityTask]) -> bool:
        """Check if a task conflicts with active or batched resource locks."""
        if not task.resource_locks:
            return False
        task_locks = set(task.resource_locks)
        if task_locks & self._active_resource_locks:
            return True
        for other in batch:
            if set(other.resource_locks) & task_locks:
                return True
        return False

    async def _dispatch_batch(self, batch: list[SecurityTask]) -> None:
        """Dispatch a batch of tasks to worker agents."""
        launched_tasks: list[SecurityTask] = []
        try:
            for task in batch:
                self._pool.mark_running(task.task_id)
                task.worker_status = "dispatching"
                for lock in task.resource_locks:
                    self._active_resource_locks.add(lock)
                launched_tasks.append(task)

            # Build worker specs
            workers = [self._build_worker_spec(task) for task in launched_tasks]

            # Dispatch via coordinator runtime service
            dispatch_result = await self._coordinator_runtime_service.dispatch(
                payload={"workers": workers},
                context=self._parent_context,
            )

            worker_records = {
                str(item.get("task_id") or ""): item
                for item in dispatch_result.get("workers", [])
                if isinstance(item, dict)
            }

            # Collect child session IDs
            child_session_ids = [
                str(record.get("child_session_id") or "")
                for record in worker_records.values()
                if str(record.get("status") or "") == "running"
                and str(record.get("child_session_id") or "")
            ]

            # Wait for all sessions to complete
            settled_sessions = await self._wait_for_sessions(child_session_ids)
            settled_map = {session.id: session for session in settled_sessions}

            # Process results
            for task in launched_tasks:
                record = worker_records.get(task.task_id)
                if not record:
                    self._fail_task(task, "worker_dispatch_missing")
                    continue

                child_session_id = str(record.get("child_session_id") or "")
                task.worker_session_id = child_session_id

                session = settled_map.get(child_session_id)
                if session is None:
                    self._fail_task(task, "worker_session_not_found")
                    continue

                task.worker_status = session.status.value
                tool_output = self._extract_runner_output(session.messages)
                assistant_summary = self._extract_assistant_summary(session.messages)

                if tool_output:
                    self._apply_worker_output(task, tool_output)
                elif assistant_summary:
                    # Worker completed but no structured output
                    task.result_summary = assistant_summary
                    self._pool.mark_completed(task.task_id, assistant_summary)
                else:
                    self._fail_task(task, f"Worker finished without runner output ({session.status.value})")

                # Record activity
                self._record_activity(task, assistant_summary)

        except Exception as e:
            logger.error(f"Batch dispatch failed: {e}")
            for task in launched_tasks:
                if task.status == TASK_RUNNING:
                    self._fail_task(task, f"dispatch_error: {e}")
        finally:
            for task in launched_tasks:
                for lock in task.resource_locks:
                    self._active_resource_locks.discard(lock)

    def _build_worker_spec(self, task: SecurityTask) -> dict[str, Any]:
        """Build a worker dispatch specification for a task."""
        # Determine worker agent
        agent_key = task.worker_agent_key or SURFACE_WORKER_MAP.get(
            task.surface_type, SECURITY_RECON_WORKER_KEY
        )

        runner_args: dict[str, Any] = {
            "worker_action": "execute_security_task",
            "task": task.model_dump(mode="json"),
        }

        prompt = (
            f"执行安全测试任务: {task.name}\n\n"
            f"目标: {task.target}\n"
            f"工具族: {task.tool_family}\n"
            f"命令 Profile: {task.command_profile}\n\n"
            f"请调用对应的 runner 工具执行此任务，工具参数:\n"
            f"{json.dumps(runner_args, ensure_ascii=False, indent=2)}\n\n"
            "执行完成后，返回结构化结果摘要。"
        )

        return {
            "task_id": task.task_id,
            "description": f"[{task.surface_type}] {task.name} -> {task.target}",
            "prompt": prompt,
            "agent_key": agent_key,
            "model_key": self._worker_model_key,
            "context": {
                "dispatch_role": "security_testing_worker",
                "security_task_id": task.task_id,
                "surface_type": task.surface_type,
                "tool_family": task.tool_family,
                "command_profile": task.command_profile,
            },
        }

    async def _wait_for_sessions(self, child_session_ids: list[str]) -> list[Any]:
        """Wait for all child sessions to reach a terminal state."""
        from src.schemas.session import SessionStatus

        pending = {sid for sid in child_session_ids if sid}
        settled: dict[str, Any] = {}

        while pending:
            completed_ids: list[str] = []
            for session_id in list(pending):
                session = await self._session_store.get_session(session_id)
                if session is None:
                    completed_ids.append(session_id)
                    continue
                if session.status in {
                    SessionStatus.completed,
                    SessionStatus.failed,
                    SessionStatus.interrupted,
                    SessionStatus.waiting_approval,
                }:
                    settled[session_id] = session
                    completed_ids.append(session_id)
            for sid in completed_ids:
                pending.discard(sid)
            if pending:
                await asyncio.sleep(self._poll_interval_seconds)

        return list(settled.values())

    def _apply_worker_output(self, task: SecurityTask, tool_output: dict[str, Any]) -> None:
        """Apply structured worker output to the task."""
        task.result_summary = str(tool_output.get("summary") or "")
        task.raw_output = str(tool_output.get("raw_output") or "")[:10000]
        task.parsed_result = tool_output.get("parsed_result") or {}

        # Check if worker reported success
        success = tool_output.get("success", False)
        if success:
            self._pool.mark_completed(task.task_id, task.result_summary)
        else:
            error = tool_output.get("error") or task.result_summary or "execution_failed"
            self._fail_task(task, error)

        # Collect findings
        findings = tool_output.get("findings") or []
        if findings:
            task.finding_refs = [f.get("finding_id", "") for f in findings if isinstance(f, dict)]

        # Collect artifacts
        artifacts = tool_output.get("artifacts") or []
        if artifacts:
            task.artifacts = [a.get("artifact_id", "") for a in artifacts if isinstance(a, dict)]

    def _fail_task(self, task: SecurityTask, error: str) -> None:
        """Mark a task as failed."""
        task.last_error = str(error or "execution_failed")
        self._pool.mark_failed(task.task_id, task.last_error)

    def _record_activity(self, task: SecurityTask, summary: str = "") -> None:
        """Record an agent activity for this task."""
        agent_key = task.worker_agent_key or SURFACE_WORKER_MAP.get(
            task.surface_type, SECURITY_RECON_WORKER_KEY
        )
        action = "completed" if task.status == TASK_COMPLETED else "failed"
        duration = 0.0
        if task.started_at and task.completed_at:
            try:
                start = datetime.fromisoformat(task.started_at)
                end = datetime.fromisoformat(task.completed_at)
                duration = (end - start).total_seconds()
            except (ValueError, TypeError):
                pass

        self._activities.append(AgentActivityRecord(
            activity_id=f"act_{task.task_id}",
            agent_key=agent_key,
            agent_name=agent_key,
            task_id=task.task_id,
            action=action,
            summary=summary or task.result_summary or task.last_error or "",
            started_at=task.started_at,
            completed_at=task.completed_at or datetime.now(timezone.utc).isoformat(),
            duration_seconds=duration,
        ))

    def _extract_runner_output(self, messages: list[Any]) -> dict[str, Any] | None:
        """Extract the security runner tool output from session messages."""
        from src.schemas.session import MessageRole

        runner_keys = {
            "security-scan-runner",
            "network-recon-runner",
            "web-scan-runner",
            "service-audit-runner",
            "credential-attack-runner",
            "traffic-analysis-runner",
            "exploit-workbench-runner",
        }

        for message in reversed(messages):
            if message.role != MessageRole.tool:
                continue
            tool_key = str(message.metadata.get("tool_key") or "")
            if tool_key not in runner_keys:
                continue
            parsed = self._parse_tool_payload(str(message.content or ""))
            if isinstance(parsed, dict):
                return parsed
        return None

    def _parse_tool_payload(self, content: str) -> dict[str, Any] | None:
        """Parse JSON payload from tool message content."""
        if not content:
            return None
        # Try to find JSON in the content
        payload_text = content.split("\n\n", 1)[1] if "\n\n" in content else content
        try:
            parsed = json.loads(payload_text)
        except json.JSONDecodeError:
            # Try the whole content
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                return None
        return parsed if isinstance(parsed, dict) else None

    def _extract_assistant_summary(self, messages: list[Any]) -> str:
        """Extract the last assistant message as summary."""
        from src.schemas.session import MessageRole

        for message in reversed(messages):
            if message.role == MessageRole.assistant:
                return str(message.content or "").strip()
        return ""


__all__ = ["SecuritySubagentCoordinator"]
