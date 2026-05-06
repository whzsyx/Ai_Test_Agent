from __future__ import annotations

from src.application.model_providers.adapters import (
    AzureOAuthProvider,
    CodeBuddyPollingProvider,
    CodexOAuthProvider,
    GitHubOAuthProvider,
    GoogleOAuthProvider,
    TraeCustomProvider,
)
from src.application.model_providers.flow_store import OAuthFlowStore
from src.application.model_providers.provider_base import ModelProviderAdapter
from src.core.config import Settings


class ModelProviderRegistry:
    def __init__(self, providers: list[ModelProviderAdapter]) -> None:
        self._providers = {provider.provider_key: provider for provider in providers}

    def resolve(self, provider_key: str) -> ModelProviderAdapter:
        normalized = str(provider_key or "").strip().lower()
        if normalized == "azure":
            normalized = "azure_ad"
        provider = self._providers.get(normalized)
        if provider is None:
            raise ValueError(f"Unknown OAuth provider '{provider_key}'.")
        return provider


def build_default_model_provider_registry(
    *,
    settings: Settings,
    flow_store: OAuthFlowStore,
    request_timeout: float = 30.0,
) -> ModelProviderRegistry:
    providers: list[ModelProviderAdapter] = [
        GoogleOAuthProvider(settings=settings, flow_store=flow_store, request_timeout=request_timeout),
        GitHubOAuthProvider(settings=settings, flow_store=flow_store, request_timeout=request_timeout),
        AzureOAuthProvider(settings=settings, flow_store=flow_store, request_timeout=request_timeout),
        CodexOAuthProvider(settings=settings, flow_store=flow_store, request_timeout=request_timeout),
        TraeCustomProvider(settings=settings, flow_store=flow_store, request_timeout=request_timeout),
        CodeBuddyPollingProvider(settings=settings, flow_store=flow_store, request_timeout=request_timeout),
    ]
    return ModelProviderRegistry(providers)
