from __future__ import annotations

import smtplib
from time import perf_counter

import httpx

from src.application.model_adapters import AdapterRegistry, build_default_adapter_registry
from src.application.model_compatibility import ModelCompatibilityLayer
from src.core.config import Settings
from src.infrastructure.email_config_store import MySQLEmailConfigStore
from src.infrastructure.model_config_store import MySQLModelConfigStore
from src.schemas.model_config import ModelInvocationRequest
from src.schemas.email_config import (
    EmailConfigActionResponse,
    EmailConfigConnectionTestResponse,
    EmailConfigUpdateRequest,
)
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
    ) -> None:
        self._settings = settings
        self._model_config_store = model_config_store
        self._email_config_store = email_config_store
        self._adapter_registry = adapter_registry or build_default_adapter_registry()
        self._compatibility = ModelCompatibilityLayer(adapter_registry=self._adapter_registry)

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

    def test_model_config_connection(self, model_name: str):
        record = self._model_config_store.get_by_name(model_name)
        public_item = self._model_config_store.to_public(record)
        if not record.api_key:
            return ModelConfigConnectionTestResponse(
                ok=False,
                message=f"Model '{record.name}' has no API key configured.",
                item=public_item,
                provider=record.provider,
                api_base_url=record.api_base_url,
            )

        request = ModelInvocationRequest(
            system_prompt="You are a model connection health check. Reply with a short pong.",
            messages=[{"role": "user", "content": "ping"}],
        )
        url = self._compatibility.build_url(record)
        headers = self._compatibility.build_headers(record, record.api_key)
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

    def list_email_configs(self):
        return [self._email_config_store.to_public(item) for item in self._email_config_store.list_all()]

    def update_email_config(self, payload: EmailConfigUpdateRequest):
        return self._email_config_store.to_public(self._email_config_store.update(payload))

    def activate_email_config(self, provider: str):
        item = self._email_config_store.activate(provider)
        return EmailConfigActionResponse(
            ok=True,
            message=f"Email provider '{item.provider}' is now enabled and set as default.",
            item=self._email_config_store.to_public(item),
        )

    def delete_email_config(self, provider: str):
        deleted, replacement = self._email_config_store.delete(provider)
        message = f"Email provider '{deleted.provider}' was deleted."
        if replacement is not None:
            message += f" '{replacement.provider}' is now enabled as the default channel."
        return EmailConfigActionResponse(
            ok=True,
            message=message,
            item=self._email_config_store.to_public(replacement) if replacement else None,
        )

    def test_email_config_connection(self, provider: str):
        record = self._email_config_store.get_by_provider(provider)
        public_item = self._email_config_store.to_public(record)

        if not record.smtp_host or not record.smtp_port:
            return EmailConfigConnectionTestResponse(
                ok=False,
                message=f"Email provider '{provider}' is missing SMTP host or port.",
                item=public_item,
                smtp_host=record.smtp_host,
                smtp_port=record.smtp_port,
            )

        started_at = perf_counter()
        try:
            if record.use_tls:
                with smtplib.SMTP_SSL(record.smtp_host, int(record.smtp_port), timeout=10) as client:
                    if record.smtp_username:
                        client.login(record.smtp_username, record.smtp_password or "")
                    code, response = client.noop()
            else:
                with smtplib.SMTP(record.smtp_host, int(record.smtp_port), timeout=10) as client:
                    client.ehlo()
                    try:
                        client.starttls()
                        client.ehlo()
                    except smtplib.SMTPException:
                        pass
                    if record.smtp_username:
                        client.login(record.smtp_username, record.smtp_password or "")
                    code, response = client.noop()
        except (OSError, smtplib.SMTPException) as exc:
            return EmailConfigConnectionTestResponse(
                ok=False,
                message=f"Connection test failed: {exc}",
                item=public_item,
                smtp_host=record.smtp_host,
                smtp_port=record.smtp_port,
                latency_ms=int((perf_counter() - started_at) * 1000),
            )

        preview = f"SMTP NOOP {code}"
        if response:
            preview = f"{preview} / {str(response).strip()[:120]}"

        return EmailConfigConnectionTestResponse(
            ok=True,
            message=f"Connection test succeeded for '{provider}'.",
            item=public_item,
            smtp_host=record.smtp_host,
            smtp_port=record.smtp_port,
            latency_ms=int((perf_counter() - started_at) * 1000),
            preview=preview,
        )
