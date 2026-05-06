from __future__ import annotations

import time

from src.application.model_providers.models import CompletedAuthFlow, PendingAuthFlow


class OAuthFlowStore:
    def __init__(self, ttl_seconds: int = 600) -> None:
        self._ttl_seconds = ttl_seconds
        self._pending: dict[str, PendingAuthFlow] = {}
        self._completed: dict[str, CompletedAuthFlow] = {}

    @property
    def pending(self) -> dict[str, PendingAuthFlow]:
        return self._pending

    @property
    def completed(self) -> dict[str, CompletedAuthFlow]:
        return self._completed

    def set_pending(self, state: str, flow: PendingAuthFlow) -> None:
        self.cleanup_expired()
        self._pending[state] = flow

    def get_pending(self, state: str) -> PendingAuthFlow | None:
        self.cleanup_expired()
        return self._pending.get(state)

    def pop_pending(self, state: str) -> PendingAuthFlow | None:
        self.cleanup_expired()
        return self._pending.pop(state, None)

    def set_completed(self, state: str, flow: CompletedAuthFlow) -> None:
        self.cleanup_expired()
        self._completed[state] = flow

    def get_completed(self, state: str) -> CompletedAuthFlow | None:
        self.cleanup_expired()
        return self._completed.get(state)

    def pop_completed(self, state: str) -> CompletedAuthFlow | None:
        self.cleanup_expired()
        return self._completed.pop(state, None)

    def mark_failed(self, state: str, error: str) -> None:
        self.set_completed(state, CompletedAuthFlow(status="failed", error=error))

    def cleanup_expired(self) -> None:
        now = time.monotonic()
        expired_pending = [
            state for state, flow in self._pending.items() if now - flow.created_at > self._ttl_seconds
        ]
        for state in expired_pending:
            del self._pending[state]

        expired_completed = [
            state for state, flow in self._completed.items() if now - flow.completed_at > self._ttl_seconds
        ]
        for state in expired_completed:
            del self._completed[state]
