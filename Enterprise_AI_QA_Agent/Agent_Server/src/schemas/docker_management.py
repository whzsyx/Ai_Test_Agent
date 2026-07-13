from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class DockerPortBinding(BaseModel):
    host_port: int = Field(ge=0, le=65535)
    container_port: int = Field(ge=1, le=65535)
    protocol: Literal["tcp", "udp"] = "tcp"


class DockerVolumeBinding(BaseModel):
    source: str
    target: str
    read_only: bool = False


class DockerContainerCreateRequest(BaseModel):
    name: str
    image: str
    command: list[str] = Field(default_factory=list)
    entrypoint: str | None = None
    ports: list[DockerPortBinding] = Field(default_factory=list)
    volumes: list[DockerVolumeBinding] = Field(default_factory=list)
    environment: dict[str, str] = Field(default_factory=dict)
    restart_policy: Literal["no", "always", "unless-stopped", "on-failure"] = "unless-stopped"
    start: bool = True

    @field_validator("name", "image")
    @classmethod
    def strip_required(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("value is required")
        return normalized


class DockerTemplateCreateRequest(BaseModel):
    name: str = ""
    pull_if_missing: bool = True


class DockerContainerActionRequest(BaseModel):
    action: Literal["start", "stop", "restart", "pause", "unpause"]


class DockerContainerRemoveRequest(BaseModel):
    force: bool = False


class DockerImagePullRequest(BaseModel):
    image: str

    @field_validator("image")
    @classmethod
    def strip_image(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("image is required")
        return normalized


class DockerImageRemoveRequest(BaseModel):
    image: str
    force: bool = False

    @field_validator("image")
    @classmethod
    def strip_image(cls, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("image is required")
        return normalized
