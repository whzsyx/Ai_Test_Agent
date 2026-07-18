from __future__ import annotations

import pytest

from src.application.embedding_adapters.google import GoogleEmbeddingAdapter
from src.application.embedding_adapters.openai_compatible import (
    OpenAICompatibleEmbeddingAdapter,
)
from src.application.embedding_adapters.registry import EmbeddingAdapterRegistry
from src.schemas.model_config import ModelConfigRecord
from src.schemas.settings import ModelConfigUpdateRequest


def _config(**updates) -> ModelConfigRecord:
    values = {
        "key": "embedding-model",
        "name": "text-embedding-3-small",
        "provider": "openai",
        "transport": "openai_chat_completions",
        "model_id": "text-embedding-3-small",
        "api_base_url": "https://api.openai.com/v1",
        "applications": ["embedding_retrieval"],
    }
    values.update(updates)
    return ModelConfigRecord(**values)


def test_model_application_defaults_and_requires_single_selection() -> None:
    default_request = ModelConfigUpdateRequest(
        model_name="gpt-test",
        provider="openai",
        base_url="https://example.test/v1",
    )
    assert default_request.applications == ["task_execution"]

    with pytest.raises(ValueError, match="Exactly one model application"):
        ModelConfigUpdateRequest(
            model_name="dual-purpose",
            provider="openai",
            base_url="https://example.test/v1",
            applications=["embedding_retrieval", "task_execution"],
        )


def test_openai_compatible_embedding_request() -> None:
    request = OpenAICompatibleEmbeddingAdapter().build_request(
        _config(),
        "secret",
        ["first", "second"],
    )

    assert request.url == "https://api.openai.com/v1/embeddings"
    assert request.headers["Authorization"] == "Bearer secret"
    assert request.payload == {
        "model": "text-embedding-3-small",
        "input": ["first", "second"],
        "encoding_format": "float",
    }


def test_google_embedding_request_supports_api_key_and_versioned_base_url() -> None:
    config = _config(
        provider="google",
        name="gemini-embedding-001",
        model_id="gemini-embedding-001",
        api_base_url="https://generativelanguage.googleapis.com/v1beta",
    )
    request = GoogleEmbeddingAdapter().build_request(config, "secret", ["hello"])

    assert request.url == (
        "https://generativelanguage.googleapis.com/v1beta/"
        "models/gemini-embedding-001:batchEmbedContents"
    )
    assert request.headers["x-goog-api-key"] == "secret"
    assert request.payload["requests"][0]["content"]["parts"] == [
        {"text": "hello"}
    ]


def test_embedding_registry_rejects_anthropic() -> None:
    with pytest.raises(ValueError, match="does not expose an embeddings API"):
        EmbeddingAdapterRegistry().resolve(_config(provider="anthropic"))
