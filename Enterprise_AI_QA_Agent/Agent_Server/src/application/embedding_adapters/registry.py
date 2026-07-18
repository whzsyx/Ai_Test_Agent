from __future__ import annotations

from src.application.embedding_adapters.google import GoogleEmbeddingAdapter
from src.application.embedding_adapters.openai_compatible import (
    OpenAICompatibleEmbeddingAdapter,
)
from src.schemas.model_config import ModelConfigRecord


class EmbeddingAdapterRegistry:
    def __init__(self) -> None:
        self._google = GoogleEmbeddingAdapter()
        self._openai_compatible = OpenAICompatibleEmbeddingAdapter()

    def resolve(self, config: ModelConfigRecord):
        provider = str(config.provider or "").strip().lower()
        if provider in {"google", "gemini"}:
            return self._google
        if provider == "anthropic":
            raise ValueError(
                "Anthropic does not expose an embeddings API. Configure a dedicated "
                "embedding model from OpenAI, Qwen/DashScope, Google, or another "
                "OpenAI-compatible provider."
            )
        return self._openai_compatible
