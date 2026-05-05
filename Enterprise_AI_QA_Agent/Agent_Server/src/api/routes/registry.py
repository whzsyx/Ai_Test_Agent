from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field


router = APIRouter(prefix="/registry", tags=["registry"])


class SkillUpsertRequest(BaseModel):
    content: str = Field(..., description="Full SKILL.md content.")


class SkillInstallRequest(BaseModel):
    source_path: str | None = Field(default=None, description="Local skill directory, SKILL.md, or zip path.")
    url: str | None = Field(default=None, description="HTTP(S) URL to a SKILL.md file or zip archive.")
    key: str | None = Field(default=None, description="Optional installed skill folder name.")
    overwrite: bool = False


class SkillUploadRequest(BaseModel):
    filename: str = Field(..., description="Original uploaded filename.")
    content_base64: str = Field(..., description="Base64 encoded SKILL.md or zip bytes.")
    key: str | None = Field(default=None, description="Optional installed skill folder name.")
    overwrite: bool = False


class SkillMarketplaceInstallRequest(BaseModel):
    source: str = Field(..., description="Marketplace source: anthropic or skillsmp.")
    skill_id: str = Field(..., description="Marketplace skill id/slug.")
    url: str | None = Field(default=None, description="Optional downloadable URL for SkillsMP results.")
    key: str | None = Field(default=None, description="Optional installed skill folder name.")
    overwrite: bool = False


@router.get("/framework")
async def framework_summary(request: Request):
    return request.app.state.registry_service.framework_summary()


@router.get("/agents")
async def list_agents(request: Request):
    return request.app.state.registry_service.list_agents()


@router.get("/tools")
async def list_tools(request: Request):
    return request.app.state.registry_service.list_tools()


@router.get("/modes")
async def list_modes(request: Request):
    return request.app.state.registry_service.list_modes()


@router.get("/models")
async def list_models(request: Request):
    return request.app.state.registry_service.list_models()


@router.get("/models/configs")
async def list_model_configs(request: Request):
    return request.app.state.registry_service.list_model_configs()


@router.get("/skills")
async def list_skills(request: Request):
    return request.app.state.skill_management_service.list_skills()


@router.get("/skills/marketplaces")
async def list_skill_marketplaces(request: Request):
    return request.app.state.skill_marketplace_service.list_marketplaces()


@router.get("/skills/marketplaces/search")
async def search_skill_marketplace(
    source: str,
    request: Request,
    q: str = "",
    limit: int = 20,
):
    try:
        return request.app.state.skill_marketplace_service.search(source=source, query=q, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/skills/marketplaces/preview")
async def preview_skill_marketplace(
    source: str,
    skill_id: str,
    request: Request,
    url: str | None = None,
):
    try:
        return request.app.state.skill_marketplace_service.preview(source=source, skill_id=skill_id, url=url)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/skills/marketplaces/install")
async def install_skill_marketplace(payload: SkillMarketplaceInstallRequest, request: Request):
    try:
        return request.app.state.skill_marketplace_service.install(
            source=payload.source,
            skill_id=payload.skill_id,
            url=payload.url,
            key=payload.key,
            overwrite=payload.overwrite,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/skills/{skill_key}")
async def get_skill(skill_key: str, request: Request):
    try:
        return request.app.state.skill_management_service.get_skill(skill_key)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.put("/skills/{skill_key}")
async def upsert_skill(skill_key: str, payload: SkillUpsertRequest, request: Request):
    try:
        return request.app.state.skill_management_service.upsert_skill(skill_key, payload.content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/skills/{skill_key}")
async def delete_skill(skill_key: str, request: Request):
    try:
        return request.app.state.skill_management_service.delete_skill(skill_key)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/skills/install")
async def install_skill(payload: SkillInstallRequest, request: Request):
    try:
        if payload.source_path:
            return request.app.state.skill_management_service.install_from_path(
                source_path=payload.source_path,
                key=payload.key,
                overwrite=payload.overwrite,
            )
        if payload.url:
            return request.app.state.skill_management_service.install_from_url(
                url=payload.url,
                key=payload.key,
                overwrite=payload.overwrite,
            )
        raise ValueError("Either source_path or url is required.")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/skills/upload")
async def upload_skill(payload: SkillUploadRequest, request: Request):
    try:
        return await request.app.state.skill_management_service.install_from_upload(
            filename=payload.filename,
            content_base64=payload.content_base64,
            key=payload.key,
            overwrite=payload.overwrite,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/mcp")
async def list_mcp_servers(request: Request):
    return request.app.state.registry_service.list_mcp_servers()
