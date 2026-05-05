from __future__ import annotations

from src.application.integrations.integration_catalog_service import IntegrationCatalogService
from src.application.mcp.provider_registry import MCPProviderRegistry
from src.registry.mcp import MCPRegistry
from src.schemas.integration import IntegrationRecord
from src.schemas.mcp_management import ManagedMCPServerDescriptor, MCPProviderDescriptor


class MCPManagerService:
    def __init__(
        self,
        *,
        builtin_registry: MCPRegistry,
        integration_catalog_service: IntegrationCatalogService,
        provider_registry: MCPProviderRegistry,
    ) -> None:
        self._builtin_registry = builtin_registry
        self._integration_catalog_service = integration_catalog_service
        self._provider_registry = provider_registry

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
