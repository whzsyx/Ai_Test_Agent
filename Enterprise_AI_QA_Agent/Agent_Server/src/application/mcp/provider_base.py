from __future__ import annotations

from abc import ABC, abstractmethod

from src.schemas.integration import (
    IntegrationImportSourcesResponse,
    IntegrationRecord,
)
from src.schemas.mcp_management import MCPProviderDescriptor
from src.schemas.mcp_management import ResolvedImportDocument


class BaseExternalMCPProvider(ABC):
    descriptor: MCPProviderDescriptor

    @abstractmethod
    def supports(self, integration: IntegrationRecord) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def list_import_sources(
        self,
        integration: IntegrationRecord,
        *,
        workspace_id: str | None = None,
    ) -> IntegrationImportSourcesResponse:
        raise NotImplementedError

    @abstractmethod
    async def resolve_import_document(
        self,
        integration: IntegrationRecord,
        *,
        import_source_id: str,
        workspace_id: str | None = None,
    ) -> ResolvedImportDocument:
        raise NotImplementedError
