from __future__ import annotations

from datetime import datetime, timedelta, timezone
import secrets
from time import perf_counter

import httpx

from src.application.model_adapters import AdapterRegistry, build_default_adapter_registry
from src.application.models.model_compatibility import ModelCompatibilityLayer
from src.application.models.oauth_token_service import OAuthTokenService
from src.core.config import Settings
from src.domain.channel_strategies import channel_strategy_factory
from src.infrastructure.channel_config_store import MySQLChannelConfigStore
from src.infrastructure.email_config_store import AGENT_MAIL_PROVIDERS, MySQLEmailConfigStore
from src.infrastructure.model_config_store import MySQLModelConfigStore
from src.schemas.channel_config import (
    ChannelConfigActionResponse,
    ChannelConfigCreateRequest,
    ChannelPairingSessionPublic,
    ChannelPairingStartRequest,
    ChannelConfigPublic,
    ChannelConfigUpdateRequest,
)
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
        channel_config_store: MySQLChannelConfigStore,
        adapter_registry: AdapterRegistry | None = None,
        oauth_token_service: OAuthTokenService | None = None,
    ) -> None:
        self._settings = settings
        self._model_config_store = model_config_store
        self._email_config_store = email_config_store
        self._channel_config_store = channel_config_store
        self._adapter_registry = adapter_registry or build_default_adapter_registry()
        self._compatibility = ModelCompatibilityLayer(adapter_registry=self._adapter_registry)
        self._oauth_token_service = oauth_token_service or OAuthTokenService(
            settings=settings,
            request_timeout=settings.llm_request_timeout_seconds,
        )
        self._channel_pairing_sessions: dict[str, dict] = {}

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

    # Communication channel settings ----------------------------------------

    def list_channel_configs(self) -> list[ChannelConfigPublic]:
        return [self._channel_config_store.to_public(item) for item in self._channel_config_store.list_all()]

    def create_channel_config(self, payload: ChannelConfigCreateRequest) -> ChannelConfigPublic:
        return self._channel_config_store.to_public(self._channel_config_store.create(payload))

    def update_channel_config(self, config_id: int, payload: ChannelConfigUpdateRequest) -> ChannelConfigPublic:
        return self._channel_config_store.to_public(self._channel_config_store.update(config_id, payload))

    def delete_channel_config(self, config_id: int) -> ChannelConfigActionResponse:
        existing = self._channel_config_store.get_by_id(config_id)
        strategy = channel_strategy_factory.get(existing.domain)
        official_result = strategy.delete_official_bot(
            public_config=existing.public_config,
            credentials=self._channel_config_store.credentials_for(existing),
        )
        deleted = self._channel_config_store.delete(config_id)
        official_message = str(official_result.get("message") or "").strip()
        message = f"Communication channel '{deleted.config_name}' was deleted."
        if official_message:
            message += f" {official_message}"
        return ChannelConfigActionResponse(
            ok=True,
            message=message,
            item=None,
        )

    def start_channel_pairing(
        self,
        domain: str,
        payload: ChannelPairingStartRequest,
        base_url: str,
    ) -> ChannelPairingSessionPublic:
        strategy = channel_strategy_factory.get(domain)
        strategy.ensure_pairing_supported()
        self._prune_channel_pairing_sessions()
        session_id = secrets.token_urlsafe(24)
        install = strategy.start_pairing(session_id=session_id)
        expire_in = int(install.get("expire_in") or 300)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expire_in)
        session = {
            "session_id": session_id,
            "provider": install.get("provider") or strategy.provider,
            "domain": install.get("domain") or strategy.domain,
            "requested_domain": strategy.domain,
            "status": "pending",
            "pairing_url": install.get("pairing_url") or install.get("qr_payload") or "",
            "qr_payload": install.get("qr_payload") or install.get("pairing_url") or "",
            "expires_at": expires_at,
            "confirmed_at": None,
            "config_name": payload.config_name,
            "enabled": payload.enabled,
            "device_hint": payload.device_hint,
            "interval": int(install.get("interval") or 3),
            "message": install.get("message"),
            "item": None,
        }
        for key, value in install.items():
            if key not in session:
                session[key] = value
        self._channel_pairing_sessions[session_id] = session
        return self._pairing_session_public(session)

    def get_channel_pairing(self, session_id: str) -> ChannelPairingSessionPublic:
        self._prune_channel_pairing_sessions()
        session = self._channel_pairing_sessions.get(session_id)
        if not session:
            raise KeyError(session_id)
        if session.get("status") == "pending":
            self._poll_channel_pairing_session(session)
        return self._pairing_session_public(session)

    def confirm_channel_pairing(self, session_id: str, device_name: str | None = None) -> ChannelPairingSessionPublic:
        self._prune_channel_pairing_sessions()
        session = self._channel_pairing_sessions.get(session_id)
        if not session:
            raise KeyError(session_id)
        if session.get("device_code") or session.get("qrcode"):
            raise ValueError("Official channel pairing must be confirmed by the provider scan flow.")
        if session["status"] == "expired":
            raise ValueError("Pairing session has expired.")
        domain = str(session["domain"])
        strategy = channel_strategy_factory.get(domain)
        strategy.ensure_pairing_supported()
        now = datetime.now(timezone.utc)
        device = (device_name or session.get("device_hint") or "Mobile device").strip() or "Mobile device"
        config_name = (session.get("config_name") or strategy.pairing_config_name()).strip()
        existing = next((item for item in self._channel_config_store.list_all() if item.domain == domain), None)
        public_config = strategy.build_pairing_public_config(
            existing_public_config=existing.public_config if existing else None,
            session_id=session_id,
            device=device,
            paired_at=now,
        )
        if existing:
            saved = self._channel_config_store.update(
                int(existing.id or 0),
                ChannelConfigUpdateRequest(
                    config_name=config_name,
                    provider=strategy.provider,
                    domain=strategy.domain,
                    enabled=bool(session.get("enabled", True)),
                    public_config=public_config,
                    credentials=None,
                    clear_credentials=False,
                    description=existing.description,
                ),
            )
        else:
            saved = self._channel_config_store.create(
                ChannelConfigCreateRequest(
                    config_name=config_name,
                    provider=strategy.provider,
                    domain=strategy.domain,
                    enabled=bool(session.get("enabled", True)),
                    public_config=public_config,
                    credentials=None,
                    description=None,
                ),
            )
        session["status"] = "confirmed"
        session["confirmed_at"] = now
        session["item"] = self._channel_config_store.to_public(saved)
        return self._pairing_session_public(session)

    def _poll_channel_pairing_session(self, session: dict) -> None:
        if session["status"] != "pending":
            return
        if datetime.now(timezone.utc) >= session["expires_at"]:
            session["status"] = "expired"
            session["message"] = "Pairing session expired."
            return
        strategy = channel_strategy_factory.get(str(session.get("requested_domain") or session["domain"]))
        result = strategy.poll_pairing(session)
        if result.get("poll_domain"):
            session["poll_domain"] = result["poll_domain"]
        if result.get("base_url"):
            session["base_url"] = result["base_url"]
        if result.get("message"):
            session["message"] = result["message"]
        if not result.get("done"):
            return
        self._complete_official_channel_pairing(session, result)

    def _complete_official_channel_pairing(self, session: dict, result: dict) -> None:
        domain = str(result.get("domain") or session["domain"])
        strategy = channel_strategy_factory.get(domain)
        now = datetime.now(timezone.utc)
        config_name = (session.get("config_name") or strategy.pairing_config_name()).strip()
        existing = next((item for item in self._channel_config_store.list_all() if item.domain == domain), None)
        public_config = strategy.build_connected_public_config(
            existing_public_config=existing.public_config if existing else None,
            result=result,
            session_id=str(session["session_id"]),
            connected_at=now,
        )
        credentials = strategy.build_connected_credentials(result)
        if existing:
            saved = self._channel_config_store.update(
                int(existing.id or 0),
                ChannelConfigUpdateRequest(
                    config_name=config_name,
                    provider=strategy.provider,
                    domain=strategy.domain,
                    enabled=bool(session.get("enabled", True)),
                    public_config=public_config,
                    credentials=credentials,
                    clear_credentials=False,
                    description=existing.description,
                ),
            )
        else:
            saved = self._channel_config_store.create(
                ChannelConfigCreateRequest(
                    config_name=config_name,
                    provider=strategy.provider,
                    domain=strategy.domain,
                    enabled=bool(session.get("enabled", True)),
                    public_config=public_config,
                    credentials=credentials,
                    description=None,
                ),
            )
        session["status"] = "confirmed"
        session["domain"] = strategy.domain
        session["provider"] = strategy.provider
        session["confirmed_at"] = now
        session["message"] = result.get("message") or "Channel connected."
        session["item"] = self._channel_config_store.to_public(saved)

    def _pairing_session_public(self, session: dict) -> ChannelPairingSessionPublic:
        if session["status"] == "pending" and datetime.now(timezone.utc) >= session["expires_at"]:
            session["status"] = "expired"
        return ChannelPairingSessionPublic(
            session_id=session["session_id"],
            provider=session["provider"],
            domain=session["domain"],
            status=session["status"],
            pairing_url=session["pairing_url"],
            qr_payload=session["qr_payload"],
            expires_at=session["expires_at"],
            confirmed_at=session.get("confirmed_at"),
            interval=session.get("interval"),
            message=session.get("message"),
            item=session.get("item"),
        )

    def _prune_channel_pairing_sessions(self) -> None:
        now = datetime.now(timezone.utc)
        for session_id, session in list(self._channel_pairing_sessions.items()):
            expires_at = session["expires_at"]
            if session["status"] == "pending" and now >= expires_at:
                session["status"] = "expired"
            if now - expires_at > timedelta(minutes=30):
                self._channel_pairing_sessions.pop(session_id, None)
