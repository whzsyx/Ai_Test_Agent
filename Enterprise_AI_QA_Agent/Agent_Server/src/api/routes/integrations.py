from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from src.schemas.integration import IntegrationCreateRequest, IntegrationUpdateRequest


router = APIRouter(prefix="/registry/integrations", tags=["integrations"])


@router.get("")
async def list_integrations(request: Request):
    return await request.app.state.integration_catalog_service.list_integrations()


@router.get("/{integration_id}")
async def get_integration(integration_id: str, request: Request):
    try:
        return await request.app.state.integration_catalog_service.get_integration(integration_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("")
async def create_integration(payload: IntegrationCreateRequest, request: Request):
    try:
        return await request.app.state.integration_catalog_service.create_integration(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch("/{integration_id}")
async def update_integration(integration_id: str, payload: IntegrationUpdateRequest, request: Request):
    try:
        return await request.app.state.integration_catalog_service.update_integration(integration_id, payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{integration_id}")
async def delete_integration(integration_id: str, request: Request):
    try:
        return await request.app.state.integration_catalog_service.delete_integration(integration_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{integration_id}/test")
async def test_integration(integration_id: str, request: Request):
    try:
        return await request.app.state.integration_catalog_service.test_integration(integration_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{integration_id}/import-sources")
async def list_integration_import_sources(
    integration_id: str,
    request: Request,
    workspace_id: str | None = None,
):
    try:
        return await request.app.state.integration_catalog_service.list_import_sources(
            integration_id,
            workspace_id=workspace_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
