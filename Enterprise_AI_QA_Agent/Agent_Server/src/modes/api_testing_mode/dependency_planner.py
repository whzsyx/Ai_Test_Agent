"""Build a dependency graph across API test tasks.

Rules:
- Auth/login tasks run first (all other tasks depend on them).
- Write tasks that produce resource IDs are dependencies for tasks that
  consume those IDs via path parameters.
- Read-only tasks with no path-parameter dependencies are independent.
- Tasks sharing the same resource lock are serialized.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.modes.api_testing_mode.campaign_state import ApiTestTask, EndpointCandidate
from src.modes.api_testing_mode.capability_mapper import (
    CAP_LOGIN,
    CAP_REFRESH_TOKEN,
    MappedEndpoint,
)
from src.modes.api_testing_mode.contracts import (
    EXECUTION_MODE_AUTH,
    EXECUTION_MODE_READ,
    EXECUTION_MODE_WRITE,
    TASK_PENDING,
    TASK_BLOCKED,
    TASK_READY,
)
from src.modes.api_testing_mode.precondition_resolver import PreconditionAnalysis


@dataclass
class DependencyGraph:
    """Ordered task list with dependency edges resolved."""

    tasks: list[ApiTestTask] = field(default_factory=list)
    auth_task_ids: list[str] = field(default_factory=list)
    independent_read_ids: list[str] = field(default_factory=list)
    serial_write_ids: list[str] = field(default_factory=list)


class DependencyPlanner:
    """Convert selected endpoints + preconditions into an ordered task graph."""

    def plan(
        self,
        *,
        mapped_endpoints: list[MappedEndpoint],
        preconditions: PreconditionAnalysis,
        credential_session_id: str = "",
        base_url: str = "",
    ) -> DependencyGraph:
        graph = DependencyGraph()
        auth_task_ids: list[str] = []
        write_task_ids: list[str] = []
        read_task_ids: list[str] = []

        for index, mapped in enumerate(mapped_endpoints):
            endpoint = mapped.endpoint
            task_id = f"task_{index:03d}_{endpoint.endpoint_id[:8]}"
            execution_mode = self._resolve_execution_mode(mapped)
            full_url = self._resolve_full_url(endpoint, base_url)

            task = ApiTestTask(
                task_id=task_id,
                name=f"{endpoint.method} {endpoint.path}",
                method=endpoint.method,
                path=endpoint.path,
                full_url=full_url,
                capability=mapped.capability,
                execution_mode=execution_mode,
                auth_ref=credential_session_id,
                assertions=self._default_assertions(endpoint),
                resource_locks=self._resource_locks(endpoint),
                timeout_seconds=30.0,
                status=TASK_PENDING,
            )

            if execution_mode == EXECUTION_MODE_AUTH:
                task.status = TASK_READY
                auth_task_ids.append(task_id)
            elif execution_mode == EXECUTION_MODE_WRITE:
                write_task_ids.append(task_id)
            else:
                read_task_ids.append(task_id)

            graph.tasks.append(task)

        # Resolve dependencies:
        # 1. All non-auth tasks depend on auth tasks.
        for task in graph.tasks:
            if task.execution_mode == EXECUTION_MODE_AUTH:
                continue
            task.depends_on = list(auth_task_ids)
            # If blocked by auth, mark as blocked; otherwise ready.
            if auth_task_ids:
                task.status = TASK_BLOCKED
            else:
                task.status = TASK_READY

        # 2. Write tasks are serialized among themselves (order preserved).
        for i, task_id in enumerate(write_task_ids):
            if i > 0:
                task = self._find_task(graph.tasks, task_id)
                if task is not None:
                    prev_write = write_task_ids[i - 1]
                    if prev_write not in task.depends_on:
                        task.depends_on.append(prev_write)
                    task.status = TASK_BLOCKED

        # 3. Read tasks with path parameters that match a write task's resource
        #    depend on that write task.
        path_param_deps = preconditions.path_parameter_dependencies
        for task in graph.tasks:
            if task.task_id not in path_param_deps:
                continue
            params = path_param_deps[task.task_id]
            producer = self._find_producer(graph.tasks, params, task.task_id)
            if producer and producer not in task.depends_on:
                task.depends_on.append(producer)
                task.status = TASK_BLOCKED

        graph.auth_task_ids = auth_task_ids
        graph.independent_read_ids = [
            task.task_id
            for task in graph.tasks
            if task.execution_mode == EXECUTION_MODE_READ
            and task.status == TASK_READY
        ]
        graph.serial_write_ids = write_task_ids
        return graph

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_execution_mode(self, mapped: MappedEndpoint) -> str:
        if mapped.is_auth:
            return EXECUTION_MODE_AUTH
        if mapped.is_write:
            return EXECUTION_MODE_WRITE
        return EXECUTION_MODE_READ

    def _resolve_full_url(self, endpoint: EndpointCandidate, base_url: str) -> str:
        if endpoint.full_url:
            return endpoint.full_url
        if base_url:
            path = endpoint.path if endpoint.path.startswith("/") else f"/{endpoint.path}"
            return f"{base_url.rstrip('/')}{path}"
        return endpoint.path

    def _default_assertions(self, endpoint: EndpointCandidate) -> list[dict[str, Any]]:
        """Generate baseline assertions for any endpoint."""
        return [
            {
                "kind": "status_code_range",
                "expected": [200, 201, 204],
                "description": f"Expect success status for {endpoint.method} {endpoint.path}",
            }
        ]

    def _resource_locks(self, endpoint: EndpointCandidate) -> list[str]:
        segments = [seg for seg in endpoint.path.split("/") if seg and "{" not in seg and ":" not in seg]
        if segments:
            return [segments[-1]]
        return []

    def _find_task(self, tasks: list[ApiTestTask], task_id: str) -> ApiTestTask | None:
        for task in tasks:
            if task.task_id == task_id:
                return task
        return None

    def _find_producer(
        self,
        tasks: list[ApiTestTask],
        params: list[str],
        exclude_task_id: str,
    ) -> str | None:
        """Find a POST task that likely produces the resource IDs needed."""
        for task in tasks:
            if task.task_id == exclude_task_id:
                continue
            if task.method.upper() != "POST":
                continue
            task_segments = [seg for seg in task.path.split("/") if seg and "{" not in seg]
            for param in params:
                param_lower = param.lower()
                for seg in task_segments:
                    if param_lower in seg.lower() or seg.lower() in param_lower:
                        return task.task_id
        return None


__all__ = ["DependencyPlanner", "DependencyGraph"]
