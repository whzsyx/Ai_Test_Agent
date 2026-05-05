from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from src.schemas.api_docs import ApiDocUpdateRequest, ApiDocUploadRequest


router = APIRouter(prefix="/registry/api-docs", tags=["api-docs"])


@router.get("")
async def list_api_docs(request: Request):
    return await request.app.state.api_docs_service.list_documents()


@router.get("/{doc_id}")
async def get_api_doc(doc_id: str, request: Request):
    try:
        return await request.app.state.api_docs_service.get_document(doc_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/upload")
async def upload_api_doc(payload: ApiDocUploadRequest, request: Request):
    try:
        return await request.app.state.api_docs_service.upload_document(
            filename=payload.filename,
            content_base64=payload.content_base64,
            source=payload.source,
            title=payload.title,
            project_name=payload.project_name,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{doc_id}")
async def update_api_doc(doc_id: str, payload: ApiDocUpdateRequest, request: Request):
    try:
        return await request.app.state.api_docs_service.update_document(
            doc_id,
            title=payload.title,
            project_name=payload.project_name,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{doc_id}")
async def delete_api_doc(doc_id: str, request: Request):
    try:
        return await request.app.state.api_docs_service.delete_document(doc_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
