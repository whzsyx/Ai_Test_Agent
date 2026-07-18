from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from src.schemas.model_config import ModelConfigRecord


@dataclass(frozen=True)
class EmbeddingHttpRequest:
    url: str
    headers: dict[str, str]
    payload: dict[str, Any]


class EmbeddingProviderAdapter(Protocol):
    key: str

    def build_request(
        self,
        config: ModelConfigRecord,
        api_key: str,
        texts: list[str],
    ) -> EmbeddingHttpRequest: ...

    def parse_response(self, payload: dict[str, Any]) -> list[list[float]]: ...
