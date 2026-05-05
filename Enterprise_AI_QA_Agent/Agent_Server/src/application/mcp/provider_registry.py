from __future__ import annotations

from src.application.mcp.client import ExternalMCPClient
from src.application.mcp.provider_base import BaseExternalMCPProvider
from src.application.mcp.providers.postman import PostmanExternalMCPProvider
from src.schemas.integration import IntegrationRecord
from src.schemas.mcp_management import MCPProviderDescriptor


class MCPProviderRegistry:
    def __init__(self, *, client: ExternalMCPClient) -> None:
        self._providers: list[BaseExternalMCPProvider] = [
            PostmanExternalMCPProvider(client=client),
        ]

    def list(self) -> list[MCPProviderDescriptor]:
        return [provider.descriptor for provider in self._providers]

    def resolve(self, integration: IntegrationRecord) -> BaseExternalMCPProvider | None:
        for provider in self._providers:
            if provider.supports(integration):
                return provider
        return None
