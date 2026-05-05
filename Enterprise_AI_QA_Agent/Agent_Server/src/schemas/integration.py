from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


IntegrationKind = Literal["mcp", "api"]
IntegrationTransport = Literal["stdio", "http", "websocket"]
IntegrationAuthType = Literal["none", "bearer", "api_key", "basic"]


class IntegrationRecord(BaseModel):
    id: str
    name: str
    kind: IntegrationKind
    enabled: bool = True
    description: str | None = None
    project_name: str | None = None
    document_url: str | None = None
    transport: IntegrationTransport | None = None
    endpoint_url: str | None = None
    command: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    headers: dict[str, str] = Field(default_factory=dict)
    env: dict[str, str] = Field(default_factory=dict)
    base_url: str | None = None
    auth_type: IntegrationAuthType = "none"
    auth_config: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, object] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class IntegrationCreateRequest(BaseModel):
    name: str
    kind: IntegrationKind
    enabled: bool = True
    description: str | None = None
    project_name: str | None = None
    document_url: str | None = None
    transport: IntegrationTransport | None = None
    endpoint_url: str | None = None
    command: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    headers: dict[str, str] = Field(default_factory=dict)
    env: dict[str, str] = Field(default_factory=dict)
    base_url: str | None = None
    auth_type: IntegrationAuthType = "none"
    auth_config: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, object] = Field(default_factory=dict)


class IntegrationUpdateRequest(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    description: str | None = None
    project_name: str | None = None
    document_url: str | None = None
    transport: IntegrationTransport | None = None
    endpoint_url: str | None = None
    command: str | None = None
    capabilities: list[str] | None = None
    headers: dict[str, str] | None = None
    env: dict[str, str] | None = None
    base_url: str | None = None
    auth_type: IntegrationAuthType | None = None
    auth_config: dict[str, str] | None = None
    metadata: dict[str, object] | None = None


class IntegrationTestResponse(BaseModel):
    ok: bool
    message: str
    target_url: str | None = None
    integration_id: str | None = None
    status_code: int | None = None
    latency_ms: float | None = None
    preview: str | None = None


class IntegrationWorkspaceDescriptor(BaseModel):
    id: str
    name: str
    description: str | None = None
    project_name: str | None = None
    document_count: int = 0


class IntegrationImportSourceDescriptor(BaseModel):
    id: str
    label: str
    document_url: str
    kind: str = "document_url"
    summary: str | None = None
    project_name: str | None = None
    workspace_id: str | None = None
    workspace_name: str | None = None


class IntegrationImportSourcesResponse(BaseModel):
    integration_id: str
    kind: IntegrationKind
    supports_workspace_selection: bool = False
    workspaces: list[IntegrationWorkspaceDescriptor] = Field(default_factory=list)
    sources: list[IntegrationImportSourceDescriptor] = Field(default_factory=list)
