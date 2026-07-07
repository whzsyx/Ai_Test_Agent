"""Unified Mail API routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field


router = APIRouter(prefix="/mail", tags=["mail"])


class ProviderSetupActionRequest(BaseModel):
    action: str
    payload: dict[str, Any] = Field(default_factory=dict)


class ProvisionInboxRequest(BaseModel):
    options: dict[str, Any] = Field(default_factory=dict)


class SendPrepareRequest(BaseModel):
    recipients: list[str]
    subject: str
    content: str = ""
    content_html: str = ""
    config_id: int | None = None


class SendConfirmRequest(BaseModel):
    confirmation_token: str
    config_id: int | None = None


@router.get("/providers")
async def list_providers(request: Request):
    registry = request.app.state.mail_service._registry
    providers = []
    for key in registry.registered_keys():
        adapter = registry.resolve(key)
        providers.append({
            "provider": key,
            "capabilities": sorted(cap.value for cap in adapter.capabilities()),
        })
    return {"providers": providers}


@router.post("/providers/{provider}/status")
async def provider_status(provider: str, request: Request):
    mail_service = request.app.state.mail_service
    registry = mail_service._registry
    adapter = registry.get(provider)
    if adapter is None:
        raise HTTPException(status_code=404, detail="Unknown provider: " + provider)
    store = mail_service._email_config_store
    if store is None:
        raise HTTPException(status_code=500, detail="Email config store unavailable.")
    records = store.list_all()
    record = next((r for r in records if r.provider == provider and r.enabled), None)
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

    if body.action == "auth_status":
        store = mail_service._email_config_store
        if store is None:
            raise HTTPException(status_code=500, detail="Email config store unavailable.")
        records = store.list_all()
        record = next(
            (r for r in records if r.provider == provider and r.enabled), None
        )
        if record is None:
            return {"ok": False, "error": "no_enabled_config"}
        return adapter.status(record)

    return {"ok": True, "action": body.action, "result": "no_op"}


@router.post("/providers/{provider}/provision-inbox")
async def provision_inbox(
    provider: str, body: ProvisionInboxRequest, request: Request
):
    mail_service = request.app.state.mail_service
    try:
        result = mail_service.provision_inbox(options=body.options)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


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
    registry = mail_service._registry
    record = mail_service._resolve_record_by_id(body.config_id)
    adapter = registry.resolve(record.provider)

    if not hasattr(adapter, "send_confirm"):
        raise HTTPException(
            status_code=400,
            detail="Provider does not support two-phase send confirmation.",
        )
    try:
        result = adapter.send_confirm(record, body.confirmation_token)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result.to_dict()


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
