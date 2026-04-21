from __future__ import annotations

from src.application.model_adapters.anthropic_messages import AnthropicMessagesAdapter
from src.application.model_adapters.base import ProviderAdapter
from src.application.model_adapters.google_gemini import GoogleGeminiGenerateContentAdapter
from src.application.model_adapters.openai_chat import OpenAIChatCompletionsAdapter
from src.application.model_adapters.provider_profiles import normalize_provider, normalize_transport
from src.schemas.model_config import ModelConfigRecord


class AdapterRegistry:
    def __init__(self, adapters: list[ProviderAdapter]) -> None:
        self._adapters = list(adapters)

    def resolve(self, config: ModelConfigRecord) -> ProviderAdapter:
        resolved = config.model_copy(
            update={
                "provider": normalize_provider(config.provider),
                "transport": normalize_transport(config.transport, provider=config.provider),
            }
        )
        for adapter in self._adapters:
            if adapter.matches(resolved):
                return adapter
        raise ValueError(
            f"No provider adapter matched provider='{resolved.provider}' transport='{resolved.transport}'."
        )


def build_default_adapter_registry() -> AdapterRegistry:
    return AdapterRegistry(
        adapters=[
            AnthropicMessagesAdapter(),
            GoogleGeminiGenerateContentAdapter(),
            OpenAIChatCompletionsAdapter(),
        ]
    )
