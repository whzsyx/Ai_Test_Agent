from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


ManagedMCPSourceKind = Literal["builtin", "external"]
ManagedMCPToolSourceKind = Literal["builtin_capability", "external_tool", "external_capability"]


class MCPProviderDescriptor(BaseModel):
    key: str
    name: str
    summary: str
    supports_workspace_selection: bool = False
    supports_document_import: bool = False


class ManagedMCPServerDescriptor(BaseModel):
    key: str
    name: str
    summary: str
    transport: str
    status: str
    capabilities: list[str] = Field(default_factory=list)
    enabled: bool = True
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


class ManagedMCPToolsResponse(BaseModel):
    server_key: str
    server_name: str
    source_kind: ManagedMCPSourceKind
    tools: list[ManagedMCPToolDescriptor] = Field(default_factory=list)


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
