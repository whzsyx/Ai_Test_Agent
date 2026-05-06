from __future__ import annotations

from src.application.model_providers.provider_base import ModelProviderAdapter
from src.schemas.oauth import OAuthStartRequest, OAuthStatusResponse


class TraeCustomProvider(ModelProviderAdapter):
    provider_key = "trae"

    async def start_auth(self, request: OAuthStartRequest):
        raise ValueError("Provider 'trae' requires a custom login adapter and is not implemented yet.")

    async def handle_callback(self, *, code: str, state: str, error: str | None = None) -> None:
        self._flow_store.mark_failed(state, error or "Provider 'trae' callback handling is not implemented yet.")

    def get_flow_status(self, state: str) -> OAuthStatusResponse:
        completed = self._flow_store.get_completed(state)
        if completed is None:
            return OAuthStatusResponse(state=state, status="failed", error="OAuth state not found or already consumed.")
        return OAuthStatusResponse(state=state, status=completed.status, error=completed.error or None)

    async def list_models(self, *, state: str | None = None, base_url: str | None = None) -> list[dict]:
        raise ValueError("Provider 'trae' model listing is not implemented yet.")

    async def get_runtime_token(self, config) -> str:
        raise ValueError("Provider 'trae' runtime token resolution is not implemented yet.")
