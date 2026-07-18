from __future__ import annotations

from typing import Any

from src.application.embedding_adapters.base import EmbeddingHttpRequest
from src.schemas.model_config import ModelConfigRecord


class OpenAICompatibleEmbeddingAdapter:
    key = "openai_compatible_embeddings"

    def build_request(
        self,
        config: ModelConfigRecord,
        api_key: str,
        texts: list[str],
    ) -> EmbeddingHttpRequest:
        base_url = config.api_base_url.rstrip("/")
        url = base_url if base_url.endswith("/embeddings") else f"{base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            **config.extra_headers,
        }
        return EmbeddingHttpRequest(
            url=url,
            headers=headers,
            payload={
                "model": config.model_id,
                "input": texts,
                "encoding_format": "float",
            },
        )

    def parse_response(self, payload: dict[str, Any]) -> list[list[float]]:
        items = payload.get("data")
        if not isinstance(items, list):
            raise ValueError("Embedding response does not contain a data array.")
        ordered = sorted(
            (item for item in items if isinstance(item, dict)),
            key=lambda item: int(item.get("index") or 0),
        )
        vectors = [item.get("embedding") for item in ordered]
        if not vectors or not all(isinstance(item, list) for item in vectors):
            raise ValueError("Embedding response does not contain valid vectors.")
        return [[float(value) for value in vector] for vector in vectors]
