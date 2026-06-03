from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


ManagedMCPSourceKind = Literal["builtin", "external"]
ManagedMCPToolSourceKind = Literal["builtin_capability", "external_tool", "external_capability"]
MCPServerTransport = Literal["stdio", "streamable_http", "sse"]
MCPServerProtocol = Literal["stdio", "streamable_http", "sse"]


class MCPProviderDescriptor(BaseModel):
    key: str
    name: str
    summary: str
    supports_workspace_selection: bool = False
    supports_document_import: bool = False


class MCPServerRecord(BaseModel):
    id: str
    name: str
    enabled: bool = True
    transport: MCPServerTransport
    purpose: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    supported_protocols: list[MCPServerProtocol] = Field(default_factory=list)
    description: str | None = None
    project_name: str | None = None
    document_url: str | None = None
    endpoint_url: str | None = None
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    headers: dict[str, str] = Field(default_factory=dict)
    env: dict[str, str] = Field(default_factory=dict)
    cwd: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    provider_key: str | None = None
    confirmed_at: datetime | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class MCPServerCreateRequest(BaseModel):
    name: str
    enabled: bool = True
    transport: MCPServerTransport | None = None
    purpose: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    supported_protocols: list[MCPServerProtocol] = Field(default_factory=list)
    description: str | None = None
    project_name: str | None = None
    document_url: str | None = None
    endpoint_url: str | None = None
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    headers: dict[str, str] = Field(default_factory=dict)
    env: dict[str, str] = Field(default_factory=dict)
    cwd: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    provider_key: str | None = None
    confirmed_at: datetime | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class MCPServerUpdateRequest(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    transport: MCPServerTransport | None = None
    purpose: str | None = None
    config: dict[str, Any] | None = None
    supported_protocols: list[MCPServerProtocol] | None = None
    description: str | None = None
    project_name: str | None = None
    document_url: str | None = None
    endpoint_url: str | None = None
    command: str | None = None
    args: list[str] | None = None
    headers: dict[str, str] | None = None
    env: dict[str, str] | None = None
    cwd: str | None = None
    capabilities: list[str] | None = None
    provider_key: str | None = None
    confirmed_at: datetime | None = None
    metadata: dict[str, object] | None = None


class MCPServerImportRequest(BaseModel):
    payload: dict[str, Any]


class MCPServerImportResponse(BaseModel):
    servers: list[MCPServerRecord] = Field(default_factory=list)


class ManagedMCPServerDescriptor(BaseModel):
    key: str
    name: str
    summary: str
    transport: str
    status: str
    capabilities: list[str] = Field(default_factory=list)
    enabled: bool = True
    purpose: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    supported_protocols: list[str] = Field(default_factory=list)
    source_kind: ManagedMCPSourceKind
    provider_key: str | None = None
    provider_name: str | None = None
    integration_id: str | None = None
    project_name: str | None = None
    endpoint_url: str | None = None
    document_url: str | None = None
    supports_workspace_selection: bool = False
    supports_document_import: bool = False
    metadata: dict[str, object] = Field(default_factory=dict)


class ManagedMCPToolDescriptor(BaseModel):
    key: str
    name: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)
    source_kind: ManagedMCPToolSourceKind
    managed_server_key: str
    server_name: str
    provider_key: str | None = None
    tags: list[str] = Field(default_factory=list)


class ManagedMCPResourceDescriptor(BaseModel):
    uri: str
    name: str = ""
    description: str = ""
    mime_type: str | None = None
    managed_server_key: str
    server_name: str
    provider_key: str | None = None
    tags: list[str] = Field(default_factory=list)


class ManagedMCPPromptDescriptor(BaseModel):
    name: str
    description: str = ""
    arguments: list[dict[str, Any]] = Field(default_factory=list)
    managed_server_key: str
    server_name: str
    provider_key: str | None = None
    tags: list[str] = Field(default_factory=list)


class ManagedMCPToolsResponse(BaseModel):
    server_key: str
    server_name: str
    source_kind: ManagedMCPSourceKind
    tools: list[ManagedMCPToolDescriptor] = Field(default_factory=list)


class ManagedMCPResourcesResponse(BaseModel):
    server_key: str
    server_name: str
    source_kind: ManagedMCPSourceKind
    resources: list[ManagedMCPResourceDescriptor] = Field(default_factory=list)


class ManagedMCPPromptsResponse(BaseModel):
    server_key: str
    server_name: str
    source_kind: ManagedMCPSourceKind
    prompts: list[ManagedMCPPromptDescriptor] = Field(default_factory=list)


class ManagedMCPTestResponse(BaseModel):
    ok: bool
    message: str
    server_key: str
    server_name: str
    source_kind: ManagedMCPSourceKind
    status_code: int | None = None
    latency_ms: float | None = None
    tool_count: int | None = None


class ManagedMCPToolCallRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)


class ManagedMCPToolCallResponse(BaseModel):
    ok: bool
    server_key: str
    server_name: str
    source_kind: ManagedMCPSourceKind
    tool_name: str
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class ResolvedImportDocument(BaseModel):
    mode: Literal["url", "inline"]
    document_url: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    auth: tuple[str, str] | None = None
    filename: str | None = None
    content_base64: str | None = None
    content_type: str | None = None
    title: str | None = None
    project_name: str | None = None
