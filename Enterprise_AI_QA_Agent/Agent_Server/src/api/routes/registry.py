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


@router.get("/framework")
async def framework_summary(request: Request):
    return request.app.state.registry_service.framework_summary()


@router.get("/agents")
async def list_agents(request: Request):
    return request.app.state.registry_service.list_agents()


@router.get("/tools")
async def list_tools(request: Request):
    return request.app.state.registry_service.list_tools()


@router.get("/models")
async def list_models(request: Request):
    return request.app.state.registry_service.list_models()


@router.get("/models/configs")
async def list_model_configs(request: Request):
    return request.app.state.registry_service.list_model_configs()


@router.get("/skills")
async def list_skills(request: Request):
    return request.app.state.skill_management_service.list_skills()


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


@router.get("/mcp")
async def list_mcp_servers(request: Request):
    return request.app.state.registry_service.list_mcp_servers()
