from __future__ import annotations

from time import perf_counter

import httpx

from src.application.model_adapters import AdapterRegistry, build_default_adapter_registry
from src.application.models.model_compatibility import ModelCompatibilityLayer
from src.application.models.oauth_token_service import OAuthTokenService
from src.core.config import Settings
from src.infrastructure.email_config_store import AGENT_MAIL_PROVIDERS, MySQLEmailConfigStore
from src.infrastructure.model_config_store import MySQLModelConfigStore
from src.schemas.email_config import (
    EmailConfigActionResponse,
    EmailConfigCreateRequest,
    EmailConfigPublic,
    EmailConfigUpdateRequest,
)
from src.schemas.model_config import ModelInvocationRequest
from src.schemas.settings import (
    ModelConfigActionResponse,
    ModelConfigConnectionTestResponse,
    ModelConfigUpdateRequest,
)


class SettingsService:
    def __init__(
        self,
        settings: Settings,
        model_config_store: MySQLModelConfigStore,
        email_config_store: MySQLEmailConfigStore,
        adapter_registry: AdapterRegistry | None = None,
        oauth_token_service: OAuthTokenService | None = None,
    ) -> None:
        self._settings = settings
        self._model_config_store = model_config_store
        self._email_config_store = email_config_store
        self._adapter_registry = adapter_registry or build_default_adapter_registry()
        self._compatibility = ModelCompatibilityLayer(adapter_registry=self._adapter_registry)
        self._oauth_token_service = oauth_token_service or OAuthTokenService(
            settings=settings,
            request_timeout=settings.llm_request_timeout_seconds,
        )

    def list_model_configs(self):
        return [self._model_config_store.to_public(item) for item in self._model_config_store.list_all()]

    def update_model_config(self, payload: ModelConfigUpdateRequest):
        return self._model_config_store.upsert(payload)

    def edit_model_config(self, original_model_name: str, payload: ModelConfigUpdateRequest):
        return self._model_config_store.update_existing(original_model_name, payload)

    def activate_model_config(self, model_name: str):
        item = self._model_config_store.activate(model_name)
        return ModelConfigActionResponse(
            ok=True,
            message=f"Model '{item.name}' is now active.",
            item=item,
        )

    def delete_model_config(self, model_name: str):
        deleted, replacement = self._model_config_store.delete(model_name)
        message = f"Model '{deleted.name}' was deleted."
        if replacement is not None:
            message += f" '{replacement.name}' is now active."
        return ModelConfigActionResponse(
            ok=True,
            message=message,
            item=self._model_config_store.to_public(replacement) if replacement else None,
        )

    async def test_model_config_connection(self, model_name: str):
        record = self._model_config_store.get_by_name(model_name)
        public_item = self._model_config_store.to_public(record)
        if record.auth_type == "oauth2":
            return await self._test_oauth_connection(record, public_item)
        if not record.api_key:
            return ModelConfigConnectionTestResponse(
                ok=False,
                message=f"Model '{record.name}' has no API key configured.",
                item=public_item,
                provider=record.provider,
                api_base_url=record.api_base_url,
            )
        return self._test_api_key_connection(record, public_item, record.api_key)

    def _test_api_key_connection(self, record, public_item, api_key: str):
        request = ModelInvocationRequest(
            system_prompt="You are a model connection health check. Reply with a short pong.",
            messages=[{"role": "user", "content": "ping"}],
        )
        url = self._compatibility.build_url(record)
        headers = self._compatibility.build_headers(record, api_key)
        payload = self._compatibility.build_request(record, request)
        started_at = perf_counter()
        try:
            with httpx.Client(timeout=self._settings.llm_request_timeout_seconds) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                parsed = self._compatibility.parse_response(record, response.json())
        except httpx.HTTPError as exc:
            return ModelConfigConnectionTestResponse(
                ok=False,
                message=f"Connection test failed: {exc}",
                item=public_item,
                provider=record.provider,
                api_base_url=record.api_base_url,
                latency_ms=int((perf_counter() - started_at) * 1000),
            )
        preview = (parsed.get("text") or "").strip()
        if preview:
            preview = preview[:120]
        return ModelConfigConnectionTestResponse(
            ok=True,
            message=f"Connection test succeeded for '{record.name}'.",
            item=public_item,
            provider=record.provider,
            api_base_url=record.api_base_url,
            latency_ms=int((perf_counter() - started_at) * 1000),
            preview=preview or None,
        )

    async def _test_oauth_connection(self, record, public_item):
        provider = str(record.oauth_provider or "").strip()
        if not provider:
            return ModelConfigConnectionTestResponse(
                ok=False,
                message=(
                    f"OAuth 2.0 connection test failed for '{record.name}': "
                    "oauth_provider is required."
                ),
                item=public_item,
                provider=record.provider,
                api_base_url=record.api_base_url,
            )
        started_at = perf_counter()
        try:
            access_token = await self._oauth_token_service.fetch_token_once(record)
        except Exception as exc:
            return ModelConfigConnectionTestResponse(
                ok=False,
                message=f"OAuth token fetch failed for '{record.name}': {exc}",
                item=public_item,
                provider=record.provider,
                api_base_url=record.api_base_url,
                latency_ms=int((perf_counter() - started_at) * 1000),
            )
        return self._test_api_key_connection(record, public_item, access_token)

    # Agent-native mailbox settings -----------------------------------------

    def list_email_configs(self):
        return [self._to_email_public(item) for item in self._email_config_store.list_all()]

    def create_email_config(self, payload: EmailConfigCreateRequest):
        self._validate_native_mailbox_payload(payload)
        return self._to_email_public(self._email_config_store.create(payload))

    def update_email_config(self, config_id: int, payload: EmailConfigUpdateRequest):
        self._validate_native_mailbox_payload(payload)
        return self._to_email_public(self._email_config_store.update(config_id, payload))

    @staticmethod
    def _validate_native_mailbox_payload(payload) -> None:
        provider = str(payload.provider or "").strip().lower()
        if provider not in AGENT_MAIL_PROVIDERS:
            raise ValueError(f"Unsupported Agent Mail provider '{provider}'.")
        if not str(payload.config_name or "").strip():
            raise ValueError("Mailbox configuration name is required.")

    def activate_email_config(self, config_id: int):
        item = self._email_config_store.activate(config_id)
        return EmailConfigActionResponse(
            ok=True,
            message=f"'{item.config_name}' is now the globally active Agent mailbox.",
            item=self._to_email_public(item),
        )

    def delete_email_config(self, config_id: int):
        deleted, replacement = self._email_config_store.delete(config_id)
        message = f"Native mailbox '{deleted.config_name}' was deleted."
        if replacement is not None:
            message += f" '{replacement.config_name}' is now the globally active mailbox."
        return EmailConfigActionResponse(
            ok=True,
            message=message,
            item=self._to_email_public(replacement) if replacement else None,
        )

    def _to_email_public(self, item) -> EmailConfigPublic:
        if isinstance(item, EmailConfigPublic):
            return item
        public_item = self._email_config_store.to_public(item)
        if isinstance(public_item, EmailConfigPublic):
            return public_item
        if hasattr(public_item, "model_dump"):
            return EmailConfigPublic.model_validate(public_item.model_dump(mode="python"))
        if hasattr(public_item, "__dict__"):
            return EmailConfigPublic.model_validate(vars(public_item))
        return EmailConfigPublic.model_validate(public_item)
