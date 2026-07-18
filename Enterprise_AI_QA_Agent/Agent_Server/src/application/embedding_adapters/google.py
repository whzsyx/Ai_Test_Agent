from __future__ import annotations

from typing import Any

from src.application.embedding_adapters.base import EmbeddingHttpRequest
from src.schemas.model_config import ModelConfigRecord


class GoogleEmbeddingAdapter:
    key = "google_embeddings"

    def build_request(
        self,
        config: ModelConfigRecord,
        api_key: str,
        texts: list[str],
    ) -> EmbeddingHttpRequest:
        base_url = config.api_base_url.rstrip("/")
        model_name = config.model_id
        if not model_name.startswith("models/"):
            model_name = f"models/{model_name}"
        api_root = base_url if base_url.endswith("/v1beta") else f"{base_url}/v1beta"
        headers = {
            "Content-Type": "application/json",
            **config.extra_headers,
        }
        if config.auth_type == "oauth2":
            headers["Authorization"] = f"Bearer {api_key}"
        else:
            headers["x-goog-api-key"] = api_key
        return EmbeddingHttpRequest(
            url=f"{api_root}/{model_name}:batchEmbedContents",
            headers=headers,
            payload={
                "requests": [
                    {
                        "model": model_name,
                        "content": {"parts": [{"text": text}]},
                    }
                    for text in texts
                ]
            },
        )

    def parse_response(self, payload: dict[str, Any]) -> list[list[float]]:
        items = payload.get("embeddings")
        if not isinstance(items, list):
            raise ValueError("Google embedding response does not contain embeddings.")
        vectors = [item.get("values") for item in items if isinstance(item, dict)]
        if not vectors or not all(isinstance(item, list) for item in vectors):
            raise ValueError("Google embedding response does not contain valid vectors.")
        return [[float(value) for value in vector] for vector in vectors]
