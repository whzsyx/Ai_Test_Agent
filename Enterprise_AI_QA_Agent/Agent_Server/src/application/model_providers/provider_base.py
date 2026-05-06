from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from src.application.model_providers.flow_store import OAuthFlowStore
from src.application.model_providers.models import AuthStartResult, CompletedAuthFlow
from src.core.config import Settings
from src.schemas.oauth import OAuthStartRequest, OAuthStatusResponse

if TYPE_CHECKING:
    from src.schemas.model_config import ModelConfigRecord


class ModelProviderAdapter(ABC):
    provider_key: str

    def __init__(
        self,
        *,
        settings: Settings,
        flow_store: OAuthFlowStore,
        request_timeout: float = 30.0,
    ) -> None:
        self._settings = settings
        self._flow_store = flow_store
        self._request_timeout = request_timeout

    @abstractmethod
    async def start_auth(self, request: OAuthStartRequest) -> AuthStartResult:
        raise NotImplementedError

    async def poll_auth(self, state: str) -> None:
        return None

    def get_persisted_token(self, completed: CompletedAuthFlow) -> str | None:
        return completed.refresh_token or None

    @abstractmethod
    async def handle_callback(
        self,
        *,
        code: str,
        state: str,
        error: str | None = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    def get_flow_status(self, state: str) -> OAuthStatusResponse:
        raise NotImplementedError

    @abstractmethod
    async def list_models(
        self,
        *,
        state: str | None = None,
        base_url: str | None = None,
    ) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    async def get_runtime_token(self, config: "ModelConfigRecord") -> str:
        raise NotImplementedError
