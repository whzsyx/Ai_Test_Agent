from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from src.schemas.api_docs import AttachmentUploadRequest


router = APIRouter(prefix="/registry/attachments", tags=["attachments"])


@router.post("/upload")
async def upload_attachment(payload: AttachmentUploadRequest, request: Request):
    try:
        return await request.app.state.api_docs_service.upload_attachment(
            filename=payload.filename,
            content_base64=payload.content_base64,
            source=payload.source,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

