from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from src.schemas.email_config import EmailConfigCreateRequest, EmailConfigUpdateRequest
from src.schemas.settings import ModelConfigUpdateRequest


router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/models")
async def list_model_configs(request: Request):
    return request.app.state.settings_service.list_model_configs()


@router.put("/models")
async def update_model_config(payload: ModelConfigUpdateRequest, request: Request):
    return request.app.state.settings_service.update_model_config(payload)


@router.patch("/models/{model_name}")
async def edit_model_config(model_name: str, payload: ModelConfigUpdateRequest, request: Request):
    try:
        return request.app.state.settings_service.edit_model_config(model_name, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found.") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/models/{model_name}/activate")
async def activate_model_config(model_name: str, request: Request):
    try:
        return request.app.state.settings_service.activate_model_config(model_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found.") from exc


@router.post("/models/{model_name}/test-connection")
async def test_model_config_connection(model_name: str, request: Request):
    try:
        return await request.app.state.settings_service.test_model_config_connection(model_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found.") from exc


@router.delete("/models/{model_name}")
async def delete_model_config(model_name: str, request: Request):
    try:
        return request.app.state.settings_service.delete_model_config(model_name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Model '{model_name}' not found.") from exc


@router.get("/email")
async def list_email_configs(request: Request):
    return request.app.state.settings_service.list_email_configs()


@router.post("/email")
async def create_email_config(payload: EmailConfigCreateRequest, request: Request):
    return request.app.state.settings_service.create_email_config(payload)


@router.patch("/email/{config_id}")
async def update_email_config(config_id: int, payload: EmailConfigUpdateRequest, request: Request):
    try:
        return request.app.state.settings_service.update_email_config(config_id, payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Email channel '{config_id}' not found.") from exc


@router.post("/email/{config_id}/activate")
async def activate_email_config(config_id: int, request: Request):
    try:
        return request.app.state.settings_service.activate_email_config(config_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Email channel '{config_id}' not found.") from exc


@router.post("/email/{config_id}/test-connection")
async def test_email_config_connection(config_id: int, request: Request):
    try:
        return request.app.state.settings_service.test_email_config_connection(config_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Email channel '{config_id}' not found.") from exc


@router.delete("/email/{config_id}")
async def delete_email_config(config_id: int, request: Request):
    try:
        return request.app.state.settings_service.delete_email_config(config_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Email channel '{config_id}' not found.") from exc


# ---------------------------------------------------------------------------
# General Settings (user workspace preferences)
# ---------------------------------------------------------------------------

from pydantic import BaseModel, Field
from typing import Any
import json
from pathlib import Path


class GeneralSettingsPayload(BaseModel):
    language: str = "zh-CN"
    modelOutputLanguage: str = "follow-system"
    notifySessionCompleteWhenAway: bool = True
    notifyApprovalRequiredWhenAway: bool = True
    notificationsAwayOnly: bool = True
    fontFamily: str = "system"
    fontSize: str = "standard"
    reduceMotion: bool = False
    lastSavedAt: str = ""


class DataManagementRequest(BaseModel):
    action: str  # backup / import / cleanup
    dry_run: bool = True
    time_range_days: int | None = None
    confirm: bool = False


class DataManagementResponse(BaseModel):
    ok: bool = True
    action: str = ""
    dry_run: bool = True
    summary: str = ""
    affected_count: int = 0
    details: dict[str, Any] = Field(default_factory=dict)


_GENERAL_SETTINGS_FILE = Path(__file__).resolve().parents[3] / "src" / "data" / "general_settings.json"


def _read_general_settings() -> dict[str, Any]:
    if _GENERAL_SETTINGS_FILE.exists():
        try:
            return json.loads(_GENERAL_SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _write_general_settings(data: dict[str, Any]) -> None:
    _GENERAL_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _GENERAL_SETTINGS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


@router.get("/general")
async def get_general_settings(request: Request):
    """Read the current general settings (workspace preferences)."""
    stored = _read_general_settings()
    if not stored:
        return GeneralSettingsPayload().model_dump()
    return stored


@router.put("/general")
async def save_general_settings(payload: GeneralSettingsPayload, request: Request):
    """Save general settings (workspace preferences)."""
    from datetime import datetime, timezone

    data = payload.model_dump()
    data["lastSavedAt"] = datetime.now(timezone.utc).isoformat()
    _write_general_settings(data)
    return data


# ---------------------------------------------------------------------------
# Data Management (backup / import / cleanup)
# ---------------------------------------------------------------------------


@router.post("/data/export")
async def export_data(request: Request):
    """Export session data as a backup bundle (placeholder)."""
    store = request.app.state.store
    sessions = await store.list_sessions(limit=1000)
    session_count = len(sessions)
    return {
        "ok": True,
        "action": "export",
        "summary": f"Export ready: {session_count} sessions available for backup.",
        "session_count": session_count,
        "format": "json",
        "note": "Full export implementation pending. Currently returns metadata only.",
    }


@router.post("/data/import")
async def import_data(request: Request):
    """Import data from a backup bundle (placeholder)."""
    return {
        "ok": False,
        "action": "import",
        "summary": "Import is not yet implemented. Backup file validation will be added in the next version.",
        "note": "Requires schema version check and integrity validation before write.",
    }


@router.post("/data/cleanup")
async def cleanup_data(payload: DataManagementRequest, request: Request):
    """Clean up historical session data with dry-run support."""
    store = request.app.state.store
    sessions = await store.list_sessions(limit=1000)

    if payload.time_range_days and payload.time_range_days > 0:
        from datetime import datetime, timezone, timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(days=payload.time_range_days)
        affected = [s for s in sessions if s.updated_at < cutoff]
    else:
        affected = list(sessions)

    affected_count = len(affected)

    if payload.dry_run:
        return DataManagementResponse(
            ok=True,
            action="cleanup",
            dry_run=True,
            summary=f"Dry-run: {affected_count} sessions would be affected.",
            affected_count=affected_count,
            details={
                "time_range_days": payload.time_range_days,
                "total_sessions": len(sessions),
                "affected_sessions": affected_count,
            },
        )

    if not payload.confirm:
        return DataManagementResponse(
            ok=False,
            action="cleanup",
            dry_run=False,
            summary="Cleanup requires explicit confirmation. Set confirm=true to proceed.",
            affected_count=affected_count,
        )

    # Real cleanup: delete affected sessions.
    deleted_count = 0
    for session in affected:
        try:
            # Note: SessionStore protocol doesn't have delete yet.
            # For now, mark as completed/archived.
            session.status = "completed"
            await store.save_session(session)
            deleted_count += 1
        except Exception:
            pass

    return DataManagementResponse(
        ok=True,
        action="cleanup",
        dry_run=False,
        summary=f"Cleanup completed: {deleted_count} sessions archived.",
        affected_count=deleted_count,
        details={
            "time_range_days": payload.time_range_days,
            "archived_count": deleted_count,
        },
    )
