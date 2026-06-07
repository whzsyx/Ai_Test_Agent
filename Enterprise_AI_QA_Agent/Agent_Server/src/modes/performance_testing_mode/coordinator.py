"""Performance testing coordinator.

Lightweight abstraction for subagent dispatch and SSE event reporting.
The performance mode is primarily sequential (unlike security mode's parallel tasks),
so the coordinator mainly handles progress reporting and dispatch abstraction.
"""
from __future__ import annotations

import logging
from typing import Any

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
