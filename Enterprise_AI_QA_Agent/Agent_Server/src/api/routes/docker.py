from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from src.application.docker_management_service import DockerUnavailableError
from src.schemas.docker_management import (
    DockerContainerActionRequest,
    DockerContainerCreateRequest,
    DockerContainerRemoveRequest,
    DockerImagePullRequest,
    DockerImageRemoveRequest,
    DockerTemplateCreateRequest,
)


router = APIRouter(prefix="/docker", tags=["docker"])


def _service(request: Request):
    return request.app.state.docker_management_service


def _raise_docker_error(exc: Exception) -> None:
    if isinstance(exc, DockerUnavailableError):
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/overview")
async def docker_overview(request: Request):
    return await _service(request).overview()


@router.post("/images/pull")
async def docker_pull_image(payload: DockerImagePullRequest, request: Request):
    try:
        return await _service(request).pull_image(payload.image)
    except Exception as exc:
        _raise_docker_error(exc)


@router.post("/images/remove")
async def docker_remove_image(payload: DockerImageRemoveRequest, request: Request):
    try:
        return await _service(request).remove_image(payload.image, force=payload.force)
    except Exception as exc:
        _raise_docker_error(exc)


@router.post("/containers")
async def docker_create_container(payload: DockerContainerCreateRequest, request: Request):
    try:
        return await _service(request).create_container(payload)
    except Exception as exc:
        _raise_docker_error(exc)


@router.post("/templates/{template_key}/create")
async def docker_create_template_container(
    template_key: str,
    payload: DockerTemplateCreateRequest,
    request: Request,
):
    try:
        return await _service(request).create_from_template(
            template_key,
            name=payload.name,
            pull_if_missing=payload.pull_if_missing,
        )
    except Exception as exc:
        _raise_docker_error(exc)


@router.post("/containers/{container_id}/action")
async def docker_container_action(
    container_id: str,
    payload: DockerContainerActionRequest,
    request: Request,
):
    try:
        return await _service(request).container_action(container_id, payload.action)
    except Exception as exc:
        _raise_docker_error(exc)


@router.post("/containers/{container_id}/remove")
async def docker_remove_container(
    container_id: str,
    payload: DockerContainerRemoveRequest,
    request: Request,
):
    try:
        return await _service(request).remove_container(container_id, force=payload.force)
    except Exception as exc:
        _raise_docker_error(exc)


@router.get("/containers/{container_id}/logs")
async def docker_container_logs(
    container_id: str,
    request: Request,
    tail: int = Query(default=200, ge=1, le=2000),
):
    try:
        return await _service(request).container_logs(container_id, tail=tail)
    except Exception as exc:
        _raise_docker_error(exc)
