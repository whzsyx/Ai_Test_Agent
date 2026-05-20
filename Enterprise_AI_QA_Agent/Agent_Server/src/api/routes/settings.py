from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from fastapi.responses import StreamingResponse

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
    """Export all session data as a downloadable JSON file."""
    store = request.app.state.store
    sessions = await store.list_sessions(limit=5000)

    bundle: list[dict] = []
    for s in sessions:
        events = await store.list_events(s.id)
        snapshots = await store.list_snapshots(s.id)
        approvals = await store.list_approvals(s.id)
        bundle.append({
            "id": s.id,
            "title": s.title,
            "status": s.status.value if hasattr(s.status, "value") else str(s.status),
            "session_mode": s.session_mode.value if hasattr(s.session_mode, "value") else str(s.session_mode),
            "runtime_mode": s.runtime_mode.value if hasattr(s.runtime_mode, "value") else str(s.runtime_mode),
            "mode_key": s.mode_key,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
            "preferred_model": s.preferred_model,
            "selected_agent": s.selected_agent,
            "metadata": s.metadata,
            "event_count": s.event_count,
            "snapshot_count": s.snapshot_count,
            "messages": [
                {"id": m.id, "role": m.role.value if hasattr(m.role, "value") else str(m.role),
                 "content": m.content, "created_at": m.created_at.isoformat() if m.created_at else None,
                 "metadata": m.metadata}
                for m in (s.messages or [])
            ],
            "events": [
                {"type": e.type, "session_id": e.session_id, "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                 "payload": e.payload}
                for e in events
            ],
            "snapshots": [
                {"id": snap.id, "session_id": snap.session_id, "version": snap.version,
                 "stage": snap.stage, "created_at": snap.created_at.isoformat() if snap.created_at else None,
                 "graph_state": snap.graph_state}
                for snap in snapshots
            ],
            "approvals": [
                {"id": a.id, "session_id": a.session_id, "tool_key": a.tool_key, "tool_name": a.tool_name,
                 "reason": a.reason, "status": a.status.value if hasattr(a.status, "value") else str(a.status),
                 "created_at": a.created_at.isoformat() if a.created_at else None,
                 "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
                 "decision_note": a.decision_note, "metadata": a.metadata}
                for a in approvals
            ],
        })

    export_payload = {
        "version": "1.0",
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "session_count": len(bundle),
        "sessions": bundle,
    }
    content = json.dumps(export_payload, ensure_ascii=False, indent=2)
    filename = f"qa-agent-backup-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json"

    return StreamingResponse(
        iter([content]),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/data/export/preview")
async def export_data_preview(request: Request):
    """Preview export: return session count without downloading."""
    store = request.app.state.store
    sessions = await store.list_sessions(limit=5000)
    return {"ok": True, "session_count": len(sessions)}


@router.post("/data/import")
async def import_data(request: Request, file: UploadFile = File(...)):
    """Import sessions from a backup JSON file."""
    store = request.app.state.store

    try:
        raw = await file.read()
        data = json.loads(raw)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON file: {exc}") from exc

    if "sessions" not in data or not isinstance(data["sessions"], list):
        raise HTTPException(status_code=400, detail="Invalid backup format: missing 'sessions' array.")

    imported = 0
    skipped = 0
    for item in data["sessions"]:
        sid = item.get("id")
        if not sid:
            skipped += 1
            continue

        existing = await store.get_session(sid)
        if existing is not None:
            skipped += 1
            continue

        from src.domain.models import SessionRecord
        from src.schemas.session import SessionStatus, SessionMode, RuntimeMode, MessageRole, ChatMessage

        session = SessionRecord(
            id=sid,
            title=item.get("title", ""),
            status=SessionStatus(item.get("status", "completed")),
            session_mode=SessionMode(item.get("session_mode", "chat")),
            runtime_mode=RuntimeMode(item.get("runtime_mode", "auto")),
            mode_key=item.get("mode_key", ""),
            preferred_model=item.get("preferred_model", ""),
            selected_agent=item.get("selected_agent", ""),
            metadata=item.get("metadata") or {},
            event_count=item.get("event_count", 0),
            snapshot_count=item.get("snapshot_count", 0),
            messages=[
                ChatMessage(
                    id=m.get("id", ""),
                    role=MessageRole(m.get("role", "user")),
                    content=m.get("content", ""),
                    metadata=m.get("metadata") or {},
                )
                for m in (item.get("messages") or [])
            ],
        )
        await store.save_session(session)

        from src.schemas.session import ExecutionEvent, SessionSnapshot, ToolApprovalRequest, ToolApprovalStatus

        for ev in (item.get("events") or []):
            await store.append_event(sid, ExecutionEvent(
                type=ev.get("type", ""),
                session_id=sid,
                payload=ev.get("payload") or {},
            ))

        for snap in (item.get("snapshots") or []):
            await store.save_snapshot(sid, SessionSnapshot(
                id=snap.get("id", ""),
                session_id=sid,
                version=snap.get("version", 1),
                stage=snap.get("stage", ""),
                graph_state=snap.get("graph_state") or {},
            ))

        for ap in (item.get("approvals") or []):
            await store.save_approval(sid, ToolApprovalRequest(
                id=ap.get("id", ""),
                session_id=sid,
                tool_key=ap.get("tool_key", ""),
                tool_name=ap.get("tool_name", ""),
                reason=ap.get("reason", ""),
                status=ToolApprovalStatus(ap.get("status", "pending")),
                decision_note=ap.get("decision_note"),
                metadata=ap.get("metadata") or {},
            ))

        imported += 1

    return {
        "ok": True,
        "action": "import",
        "summary": f"Imported {imported} sessions, skipped {skipped} (duplicate or invalid).",
        "imported_count": imported,
        "skipped_count": skipped,
    }


@router.post("/data/cleanup")
async def cleanup_data(payload: DataManagementRequest, request: Request):
    """Clean up historical session data with dry-run and confirmation support."""
    store = request.app.state.store
    sessions = await store.list_sessions(limit=5000)

    if payload.time_range_days and payload.time_range_days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=payload.time_range_days)
        affected = [s for s in sessions if s.updated_at and s.updated_at < cutoff]
    else:
        affected = list(sessions)

    affected_count = len(affected)

    if payload.dry_run:
        return DataManagementResponse(
            ok=True,
            action="cleanup",
            dry_run=True,
            summary=f"Dry-run: {affected_count} sessions would be deleted.",
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

    deleted_count = 0
    for session in affected:
        try:
            await store.delete_session(session.id)
            deleted_count += 1
        except Exception:
            pass

    return DataManagementResponse(
        ok=True,
        action="cleanup",
        dry_run=False,
        summary=f"Cleanup completed: {deleted_count} sessions deleted.",
        affected_count=deleted_count,
        details={
            "time_range_days": payload.time_range_days,
            "deleted_count": deleted_count,
        },
    )
