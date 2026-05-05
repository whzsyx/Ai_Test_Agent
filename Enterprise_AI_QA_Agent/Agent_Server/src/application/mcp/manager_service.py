from __future__ import annotations

from src.application.integrations.integration_catalog_service import IntegrationCatalogService
from src.application.mcp.provider_registry import MCPProviderRegistry
from src.application.mcp.runtime_manager import MCPRuntimeManager
from src.registry.mcp import MCPRegistry
from src.schemas.integration import IntegrationRecord
from src.schemas.mcp_management import (
    ManagedMCPServerDescriptor,
    MCPProviderDescriptor,
    ManagedMCPTestResponse,
    ManagedMCPToolCallResponse,
    ManagedMCPToolsResponse,
)


class MCPManagerService:
    def __init__(
        self,
        *,
        builtin_registry: MCPRegistry,
        integration_catalog_service: IntegrationCatalogService,
        provider_registry: MCPProviderRegistry,
        runtime_manager: MCPRuntimeManager | None = None,
    ) -> None:
        self._builtin_registry = builtin_registry
        self._integration_catalog_service = integration_catalog_service
        self._provider_registry = provider_registry
        self._runtime_manager = runtime_manager

    async def list_managed_servers(self) -> list[ManagedMCPServerDescriptor]:
        builtin = [self._from_builtin(server) for server in self._builtin_registry.list()]
        integrations = await self._integration_catalog_service.list_integrations()
        external = [self._from_external(item) for item in integrations if item.kind == "mcp"]
        return builtin + external

    def list_builtin_servers(self) -> list[ManagedMCPServerDescriptor]:
        return [self._from_builtin(server) for server in self._builtin_registry.list()]

    async def list_external_servers(self) -> list[ManagedMCPServerDescriptor]:
        integrations = await self._integration_catalog_service.list_integrations()
        return [self._from_external(item) for item in integrations if item.kind == "mcp"]

    def list_providers(self) -> list[MCPProviderDescriptor]:
        return self._provider_registry.list()

    async def list_server_tools(self, server_key: str) -> ManagedMCPToolsResponse:
        runtime_manager = self._require_runtime_manager()
        descriptor = await self._resolve_managed_server(server_key)
        return await runtime_manager.list_tools(descriptor)

    async def test_server(self, server_key: str) -> ManagedMCPTestResponse:
        runtime_manager = self._require_runtime_manager()
        descriptor = await self._resolve_managed_server(server_key)
        return await runtime_manager.test_server(descriptor)

    async def call_server_tool(
        self,
        server_key: str,
        *,
        tool_name: str,
        arguments: dict[str, object],
    ) -> ManagedMCPToolCallResponse:
        runtime_manager = self._require_runtime_manager()
        descriptor = await self._resolve_managed_server(server_key)
        return await runtime_manager.call_tool(descriptor, tool_name=tool_name, arguments=arguments)

    def _from_builtin(self, server) -> ManagedMCPServerDescriptor:
        return ManagedMCPServerDescriptor(
            key=server.key,
            name=server.name,
            summary=server.summary,
            transport=server.transport,
            status=server.status,
            capabilities=list(server.capabilities),
            enabled=server.enabled,
            source_kind="builtin",
            supports_workspace_selection=False,
            supports_document_import=False,
            metadata={},
        )

    def _from_external(self, integration: IntegrationRecord) -> ManagedMCPServerDescriptor:
        provider = self._provider_registry.resolve(integration)
        provider_descriptor = provider.descriptor if provider is not None else None
        endpoint_url = integration.endpoint_url or integration.document_url or integration.base_url
        status = "enabled" if integration.enabled else "disabled"
        summary = integration.description or (
            f"External MCP integration via {integration.transport or 'unknown'} transport."
        )
        return ManagedMCPServerDescriptor(
            key=f"external:{integration.id}",
            name=integration.name,
            summary=summary,
            transport=integration.transport or "unknown",
            status=status,
            capabilities=list(integration.capabilities),
            enabled=integration.enabled,
            source_kind="external",
            provider_key=provider_descriptor.key if provider_descriptor else None,
            provider_name=provider_descriptor.name if provider_descriptor else None,
            integration_id=integration.id,
            project_name=integration.project_name,
            endpoint_url=integration.endpoint_url,
            document_url=integration.document_url,
            supports_workspace_selection=provider_descriptor.supports_workspace_selection if provider_descriptor else False,
            supports_document_import=provider_descriptor.supports_document_import if provider_descriptor else bool(integration.document_url),
            metadata=dict(integration.metadata),
        )

    async def _resolve_managed_server(self, server_key: str) -> ManagedMCPServerDescriptor:
        builtin = self._builtin_registry.get(server_key)
        if builtin is not None:
            return self._from_builtin(builtin)

        if server_key.startswith("external:"):
            integration_id = server_key.split(":", 1)[1]
            integration = await self._integration_catalog_service.get_integration(integration_id)
            if integration.kind != "mcp":
                raise ValueError(f"Integration '{integration_id}' is not an MCP server.")
            return self._from_external(integration)

        raise ValueError(f"MCP server '{server_key}' was not found.")

    def _require_runtime_manager(self) -> MCPRuntimeManager:
        if self._runtime_manager is None:
            raise ValueError("MCP runtime manager is not configured.")
        return self._runtime_manager
