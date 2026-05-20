from __future__ import annotations

import asyncio
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


_export_tasks: dict[str, dict] = {}


@router.post("/data/export/start")
async def export_start(request: Request):
    """Start a background export task, return task_id for progress polling."""
    store = request.app.state.store
    total = await store.count_sessions()
    task_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    _export_tasks[task_id] = {"progress": 0, "total": total, "status": "running", "data": None}

    async def _run() -> None:
        try:
            def _on_progress(n: int) -> None:
                _export_tasks[task_id]["progress"] = n

            bundle = await store.bulk_export(progress_fn=_on_progress)
            _export_tasks[task_id]["data"] = bundle
            _export_tasks[task_id]["progress"] = total
            _export_tasks[task_id]["status"] = "done"
        except Exception as exc:
            _export_tasks[task_id]["status"] = "error"
            _export_tasks[task_id]["error"] = str(exc)

    asyncio.get_event_loop().create_task(_run())
    return {"ok": True, "task_id": task_id, "total": total}


@router.get("/data/export/progress/{task_id}")
async def export_progress(task_id: str):
    """Poll export progress."""
    task = _export_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Export task not found.")
    return {
        "progress": task["progress"],
        "total": task["total"],
        "status": task["status"],
        "error": task.get("error"),
    }


@router.get("/data/export/download/{task_id}")
async def export_download(task_id: str):
    """Download completed export data via streaming JSON."""
    task = _export_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Export task not found.")
    if task["status"] != "done":
        raise HTTPException(status_code=409, detail="Export not yet complete.")

    bundle: list[dict] = task["data"]
    _export_tasks.pop(task_id, None)

    def _stream():
        header = json.dumps({
            "version": "1.0",
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "session_count": len(bundle),
        }, ensure_ascii=False)
        yield header[:-1].encode("utf-8")
        yield b',"sessions":['

        for i, session in enumerate(bundle):
            if i > 0:
                yield b","
            yield json.dumps(session, ensure_ascii=False).encode("utf-8")

        yield b"]}"

    filename = f"qa-agent-backup-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json"
    return StreamingResponse(
        _stream(),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/data/export/preview")
async def export_data_preview(request: Request):
    """Preview export: return session count without downloading."""
    store = request.app.state.store
    count = await store.count_sessions()
    return {"ok": True, "session_count": count}


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

    cutoff: datetime | None = None
    if payload.time_range_days and payload.time_range_days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=payload.time_range_days)

    total_count = await store.count_sessions()
    affected_count = await store.count_sessions(before=cutoff) if cutoff else total_count
    date_range = await store.get_session_date_range()

    if payload.dry_run:
        oldest = date_range.get("oldest")
        newest = date_range.get("newest")
        return DataManagementResponse(
            ok=True,
            action="cleanup",
            dry_run=True,
            summary=f"Dry-run: {affected_count} of {total_count} sessions would be deleted.",
            affected_count=affected_count,
            details={
                "time_range_days": payload.time_range_days,
                "total_sessions": total_count,
                "affected_sessions": affected_count,
                "oldest_session": oldest.isoformat() if oldest else None,
                "newest_session": newest.isoformat() if newest else None,
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

    deleted_count = await store.delete_sessions_before(cutoff)

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
