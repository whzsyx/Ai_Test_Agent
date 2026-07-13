"""Unified Mail API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from src.application.mail.contracts import MailCapability
from src.schemas.email_config import EmailConfigUpdateRequest


router = APIRouter(prefix="/mail", tags=["mail"])


class ProviderSetupActionRequest(BaseModel):
    action: str
    payload: dict[str, Any] = Field(default_factory=dict)


class SendPrepareRequest(BaseModel):
    recipients: list[str]
    subject: str
    content: str = ""
    content_html: str = ""
    config_id: int | None = None


class SendConfirmRequest(BaseModel):
    confirmation_token: str
    config_id: int | None = None


def _resolve_provider_record(mail_service, provider: str, config_id: int | None = None):
    store = mail_service._email_config_store
    if store is None:
        raise HTTPException(status_code=500, detail="Email config store unavailable.")

    if config_id is not None:
        record = store.get_by_id(config_id)
        if record.provider != provider:
            raise HTTPException(
                status_code=400,
                detail=f"Config {config_id} does not belong to provider {provider}.",
            )
        return record

    records = store.list_all()
    record = next((r for r in records if r.provider == provider and r.enabled), None)
    if record is None:
        return None
    return record


@router.get("/providers")
async def list_providers(request: Request):
    registry = request.app.state.mail_service._registry
    providers = []
    for key in registry.registered_keys():
        adapter = registry.resolve(key)
        providers.append(adapter.descriptor())
    return {"providers": providers}


@router.post("/providers/{provider}/status")
async def provider_status(provider: str, request: Request):
    mail_service = request.app.state.mail_service
    registry = mail_service._registry
    adapter = registry.get(provider)
    if adapter is None:
        raise HTTPException(status_code=404, detail="Unknown provider: " + provider)
    record = _resolve_provider_record(mail_service, provider)
    if record is None:
        return {"ok": False, "error": "no_enabled_config", "provider": provider}
    return adapter.status(record)


@router.post("/providers/{provider}/setup-action")
async def provider_setup_action(
    provider: str, body: ProviderSetupActionRequest, request: Request
):
    mail_service = request.app.state.mail_service
    registry = mail_service._registry
    adapter = registry.get(provider)
    if adapter is None:
        raise HTTPException(status_code=404, detail="Unknown provider: " + provider)

    if body.action in {
        "status",
        "auth_status",
        "auth_login",
        "auth_login_status",
        "whoami",
        "provision_inbox",
    }:
        config_id = body.payload.get("config_id")
        if config_id is not None and not isinstance(config_id, int):
            try:
                config_id = int(config_id)
            except (TypeError, ValueError) as exc:
                raise HTTPException(status_code=400, detail="Invalid config_id.") from exc

        record = _resolve_provider_record(mail_service, provider, config_id)
        if record is None:
            return {"ok": False, "error": "no_enabled_config", "provider": provider}

        # Existing Tencent records created before mailbox-isolated credentials
        # were introduced are migrated lazily when the user authorizes again.
        if (
            body.action == "auth_login"
            and provider == "tencent_agently"
            and config_id is not None
        ):
            record = mail_service._email_config_store.ensure_tencent_credential_profile(
                config_id
            )

        if body.action == "status":
            return adapter.status(record)

        if body.action == "provision_inbox":
            if not adapter.supports(MailCapability.PROVISION_INBOX):
                return {"ok": False, "provider": provider, "error": "capability_not_supported"}
            try:
                result = adapter.provision_inbox(record, body.payload.get("options") or {})
            except RuntimeError as exc:
                return {"ok": False, "provider": provider, "error": str(exc)}
            mailbox_id = str(result.get("mailbox_id") or "").strip()
            email = str(result.get("email") or record.sender_email or "").strip()
            if mailbox_id:
                extra = dict(record.extra_config or {})
                extra["mailbox_id"] = mailbox_id
                mail_service._email_config_store.update(record.id, EmailConfigUpdateRequest(
                    config_name=record.config_name,
                    provider=record.provider,
                    sender_email=email,
                    enabled=record.enabled,
                    is_default=record.is_default,
                    description=record.description,
                    extra_config=extra,
                ))
            return result

        if body.action == "auth_status":
            if hasattr(adapter, "auth_status"):
                return adapter.auth_status(record)
            return adapter.status(record)

        if body.action == "auth_login":
            if hasattr(adapter, "auth_login"):
                return adapter.auth_login(record)
            return {
                "ok": False,
                "provider": provider,
                "action": body.action,
                "error": "setup_action_not_supported",
            }

        if body.action == "auth_login_status":
            session_id = str(body.payload.get("session_id") or "").strip()
            if not session_id:
                raise HTTPException(status_code=400, detail="session_id is required.")
            if hasattr(adapter, "auth_login_session_status"):
                return adapter.auth_login_session_status(record, session_id)
            return {
                "ok": False,
                "provider": provider,
                "action": body.action,
                "error": "setup_action_not_supported",
            }

        if body.action == "whoami":
            if hasattr(adapter, "whoami"):
                return adapter.whoami(record)
            return {
                "ok": False,
                "provider": provider,
                "action": body.action,
                "error": "setup_action_not_supported",
            }

    return {"ok": True, "action": body.action, "result": "no_op"}


@router.post("/test-send/prepare")
async def test_send_prepare(body: SendPrepareRequest, request: Request):
    mail_service = request.app.state.mail_service
    try:
        result = mail_service.send(
            body.recipients, body.subject, body.content, body.content_html,
            config_id=body.config_id,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@router.post("/test-send/confirm")
async def test_send_confirm(body: SendConfirmRequest, request: Request):
    mail_service = request.app.state.mail_service
    try:
        result = mail_service.confirm(
            "send",
            body.confirmation_token,
            config_id=body.config_id,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@router.post("/webhooks/{provider}")
async def handle_webhook(provider: str, request: Request):
    mail_service = request.app.state.mail_service
    registry = mail_service._registry
    adapter = registry.get(provider)
    if adapter is None:
        raise HTTPException(status_code=404, detail="Unknown provider: " + provider)

    body = await request.json()
    if hasattr(adapter, "handle_webhook"):
        return adapter.handle_webhook(body)
    return {"ok": True, "handled": False}
