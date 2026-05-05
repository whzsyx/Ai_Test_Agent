from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ManagedMCPSourceKind = Literal["builtin", "external"]


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
