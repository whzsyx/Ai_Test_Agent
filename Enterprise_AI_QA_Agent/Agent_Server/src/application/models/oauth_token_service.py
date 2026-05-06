"""OAuth flow coordinator for model providers.

This service keeps the current public API stable while delegating provider-
specific behavior to lightweight adapters under ``application/model_providers``.
"""
from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from src.application.model_providers.flow_store import OAuthFlowStore
from src.application.model_providers.models import CompletedAuthFlow
from src.application.model_providers.provider_registry import (
    ModelProviderRegistry,
    build_default_model_provider_registry,
)
from src.core.config import Settings
from src.schemas.oauth import OAuthStartRequest, OAuthStartResponse, OAuthStatusResponse

if TYPE_CHECKING:
    from src.schemas.model_config import ModelConfigRecord

_REFRESH_BUFFER_SECONDS = 60


class OAuthTokenService:
    def __init__(
        self,
        settings: Settings,
        request_timeout: float = 30.0,
        *,
        provider_registry: ModelProviderRegistry | None = None,
        flow_store: OAuthFlowStore | None = None,
    ) -> None:
        self._settings = settings
        self._request_timeout = request_timeout
        self._flow_store = flow_store or OAuthFlowStore()
        self._provider_registry = provider_registry or build_default_model_provider_registry(
            settings=settings,
            flow_store=self._flow_store,
            request_timeout=request_timeout,
        )
        self._token_cache: dict[str, tuple[str, float]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    @property
    def _completed(self) -> dict[str, CompletedAuthFlow]:
        return self._flow_store.completed

    async def get_token(self, config: "ModelConfigRecord") -> str:
        lock = self._get_lock(config.name)
        async with lock:
            cached = self._token_cache.get(config.name)
            if cached is not None:
                token, expire_at = cached
                if time.monotonic() < expire_at - _REFRESH_BUFFER_SECONDS:
                    return token

            adapter = self._provider_registry.resolve(str(config.oauth_provider or "").strip())
            token = await adapter.get_runtime_token(config)
            self._token_cache[config.name] = (token, time.monotonic() + 3600)
            return token

    async def fetch_token_once(self, config: "ModelConfigRecord") -> str:
        adapter = self._provider_registry.resolve(str(config.oauth_provider or "").strip())
        return await adapter.get_runtime_token(config)

    def invalidate(self, config: "ModelConfigRecord") -> None:
        self._token_cache.pop(config.name, None)

    async def start_auth_code_flow(self, req: OAuthStartRequest) -> OAuthStartResponse:
        adapter = self._provider_registry.resolve(req.provider)
        result = await adapter.start_auth(req)
        return OAuthStartResponse(
            state=result.state,
            authorization_url=result.authorization_url,
            redirect_uri=result.redirect_uri,
        )

    async def handle_callback(self, code: str, state: str) -> None:
        pending = self._flow_store.get_pending(state)
        if pending is None:
            self._flow_store.mark_failed(
                state,
                "Unknown or expired OAuth state. Please click 'Launch OAuth' again to restart the flow.",
            )
            return

        adapter = self._provider_registry.resolve(pending.provider)
        await adapter.handle_callback(code=code, state=state)

    def mark_failed_flow(self, state: str, error: str) -> None:
        self._flow_store.mark_failed(state, error)

    def get_completed_flow(self, state: str) -> CompletedAuthFlow | None:
        return self._flow_store.get_completed(state)

    async def get_flow_status(self, state: str) -> OAuthStatusResponse:
        self._flow_store.cleanup_expired()
        resolved_adapter = None
        pending = self._flow_store.get_pending(state)
        if pending is not None:
            resolved_adapter = self._provider_registry.resolve(pending.provider)
            await resolved_adapter.poll_auth(state)
            if self._flow_store.get_pending(state) is not None:
                return OAuthStatusResponse(state=state, status="pending")

        completed = self._flow_store.get_completed(state)
        if completed is not None:
            persist_token: str | None = completed.refresh_token or None
            if completed.provider:
                try:
                    adapter = (
                        resolved_adapter
                        if resolved_adapter is not None and completed.provider == resolved_adapter.provider_key
                        else self._provider_registry.resolve(completed.provider)
                    )
                    persist_token = adapter.get_persisted_token(completed)
                except Exception:
                    persist_token = completed.refresh_token or None
            preview = (completed.access_token[:20] + "...") if completed.access_token else None
            return OAuthStatusResponse(
                state=state,
                status=completed.status,
                refresh_token=persist_token or None,
                access_token_preview=preview,
                error=completed.error or None,
            )

        return OAuthStatusResponse(state=state, status="failed", error="OAuth state not found or already consumed.")

    def consume_completed_flow(self, state: str) -> CompletedAuthFlow | None:
        return self._flow_store.pop_completed(state)

    async def list_models(
        self,
        provider: str,
        state: str | None = None,
        base_url: str | None = None,
    ) -> list[dict]:
        adapter = self._provider_registry.resolve(provider)
        return await adapter.list_models(state=state, base_url=base_url)

    def _get_lock(self, key: str) -> asyncio.Lock:
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]
