from __future__ import annotations

from typing import Any

from src.application.context.mcp_runtime_service import MCPRuntimeService
from src.application.integrations.integration_catalog_service import IntegrationCatalogService
from src.application.mcp.client import ExternalMCPClient, ExternalMCPSession
from src.application.mcp.provider_registry import MCPProviderRegistry
from src.registry.mcp import MCPRegistry
from src.schemas.integration import IntegrationRecord
from src.schemas.mcp_management import (
    ManagedMCPServerDescriptor,
    ManagedMCPSourceKind,
    ManagedMCPTestResponse,
    ManagedMCPToolCallResponse,
    ManagedMCPToolDescriptor,
    ManagedMCPToolsResponse,
)


class MCPRuntimeManager:
    def __init__(
        self,
        *,
        builtin_registry: MCPRegistry,
        mcp_runtime_service: MCPRuntimeService,
        integration_catalog_service: IntegrationCatalogService,
        provider_registry: MCPProviderRegistry,
        external_mcp_client: ExternalMCPClient,
    ) -> None:
        self._builtin_registry = builtin_registry
        self._mcp_runtime_service = mcp_runtime_service
        self._integration_catalog_service = integration_catalog_service
        self._provider_registry = provider_registry
        self._external_mcp_client = external_mcp_client
        self._session_cache: dict[str, ExternalMCPSession] = {}

    async def list_tools(self, descriptor: ManagedMCPServerDescriptor) -> ManagedMCPToolsResponse:
        if descriptor.source_kind == "builtin":
            tools = self._build_builtin_tools(descriptor)
        else:
            tools = await self._build_external_tools(descriptor)
        return ManagedMCPToolsResponse(
            server_key=descriptor.key,
            server_name=descriptor.name,
            source_kind=descriptor.source_kind,
            tools=tools,
        )

    async def test_server(self, descriptor: ManagedMCPServerDescriptor) -> ManagedMCPTestResponse:
        if descriptor.source_kind == "builtin":
            message = (
                f"{descriptor.name} is enabled and available."
                if descriptor.enabled
                else f"{descriptor.name} is currently disabled."
            )
            return ManagedMCPTestResponse(
                ok=descriptor.enabled,
                message=message,
                server_key=descriptor.key,
                server_name=descriptor.name,
                source_kind=descriptor.source_kind,
                tool_count=len(descriptor.capabilities),
            )

        if not descriptor.integration_id:
            return ManagedMCPTestResponse(
                ok=False,
                message="External MCP integration id is missing.",
                server_key=descriptor.key,
                server_name=descriptor.name,
                source_kind=descriptor.source_kind,
            )

        integration_result = await self._integration_catalog_service.test_integration(descriptor.integration_id)
        tools = await self._safe_list_external_tools(descriptor)
        return ManagedMCPTestResponse(
            ok=integration_result.ok,
            message=integration_result.message,
            server_key=descriptor.key,
            server_name=descriptor.name,
            source_kind=descriptor.source_kind,
            status_code=integration_result.status_code,
            latency_ms=integration_result.latency_ms,
            tool_count=len(tools),
        )

    async def call_tool(
        self,
        descriptor: ManagedMCPServerDescriptor,
        *,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ManagedMCPToolCallResponse:
        if descriptor.source_kind == "builtin":
            result = await self._mcp_runtime_service.call(
                descriptor.key,
                tool_name,
                arguments,
                context={},
            )
            ok = str(result.get("status") or "").lower() != "failed"
            return ManagedMCPToolCallResponse(
                ok=ok,
                server_key=descriptor.key,
                server_name=descriptor.name,
                source_kind=descriptor.source_kind,
                tool_name=tool_name,
                result=result if isinstance(result, dict) else {"value": result},
                error=None if ok else str(result.get("error") or "Builtin MCP capability call failed."),
            )

        integration = await self._require_external_integration(descriptor)
        if integration.transport in {"stdio", "websocket"} and not integration.endpoint_url:
            return ManagedMCPToolCallResponse(
                ok=False,
                server_key=descriptor.key,
                server_name=descriptor.name,
                source_kind=descriptor.source_kind,
                tool_name=tool_name,
                error="This external MCP transport is configured but runtime tool calls are only supported for HTTP endpoints right now.",
            )

        session = await self._open_external_session(integration)
        result = await self._external_mcp_client.call_tool(
            session,
            tool_name=tool_name,
            arguments=arguments,
        )
        error = None
        if isinstance(result, dict) and "error" in result:
            error_payload = result.get("error")
            if isinstance(error_payload, dict):
                error = str(error_payload.get("message") or error_payload)
            else:
                error = str(error_payload)
        return ManagedMCPToolCallResponse(
            ok=error is None,
            server_key=descriptor.key,
            server_name=descriptor.name,
            source_kind=descriptor.source_kind,
            tool_name=tool_name,
            result=result if isinstance(result, dict) else {"value": result},
            error=error,
        )

    def _build_builtin_tools(self, descriptor: ManagedMCPServerDescriptor) -> list[ManagedMCPToolDescriptor]:
        return [
            ManagedMCPToolDescriptor(
                key=capability,
                name=capability,
                description=self._builtin_capability_description(capability),
                input_schema={"type": "object", "additionalProperties": True},
                source_kind="builtin_capability",
                managed_server_key=descriptor.key,
                server_name=descriptor.name,
                tags=[descriptor.transport, "builtin"],
            )
            for capability in descriptor.capabilities
        ]

    async def _build_external_tools(self, descriptor: ManagedMCPServerDescriptor) -> list[ManagedMCPToolDescriptor]:
        integration = await self._require_external_integration(descriptor)
        if integration.transport in {"stdio", "websocket"} and not integration.endpoint_url:
            return [
                ManagedMCPToolDescriptor(
                    key=capability,
                    name=capability,
                    description="Configured external MCP capability. Live runtime discovery is unavailable for this transport.",
                    input_schema={"type": "object", "additionalProperties": True},
                    source_kind="external_capability",
                    managed_server_key=descriptor.key,
                    server_name=descriptor.name,
                    provider_key=descriptor.provider_key,
                    tags=[integration.transport or "unknown", "configured-capability"],
                )
                for capability in integration.capabilities
            ]

        session = await self._open_external_session(integration)
        tools = await self._external_mcp_client.list_tools(session)
        return [
            ManagedMCPToolDescriptor(
                key=str(tool.get("name") or ""),
                name=str(tool.get("name") or ""),
                description=str(tool.get("description") or ""),
                input_schema=tool.get("inputSchema") if isinstance(tool.get("inputSchema"), dict) else {},
                source_kind="external_tool",
                managed_server_key=descriptor.key,
                server_name=descriptor.name,
                provider_key=descriptor.provider_key,
                tags=[integration.transport or "unknown", "discovered-tool"],
            )
            for tool in tools
            if str(tool.get("name") or "").strip()
        ]

    async def _safe_list_external_tools(self, descriptor: ManagedMCPServerDescriptor) -> list[ManagedMCPToolDescriptor]:
        try:
            return (await self.list_tools(descriptor)).tools
        except Exception:
            return []

    async def _require_external_integration(self, descriptor: ManagedMCPServerDescriptor) -> IntegrationRecord:
        if not descriptor.integration_id:
            raise ValueError("External MCP integration id is missing.")
        return await self._integration_catalog_service.get_integration(descriptor.integration_id)

    async def _open_external_session(self, integration: IntegrationRecord) -> ExternalMCPSession:
        endpoint_url = integration.endpoint_url or integration.document_url
        if not endpoint_url:
            raise ValueError("External MCP endpoint URL is missing.")

        cache_key = integration.id
        cached = self._session_cache.get(cache_key)
        if cached is not None and cached.endpoint_url == endpoint_url:
            return cached

        session = await self._external_mcp_client.initialize(
            endpoint_url=endpoint_url,
            headers=integration.headers,
        )
        await self._external_mcp_client.notify_initialized(session)
        self._session_cache[cache_key] = session
        return session

    def _builtin_capability_description(self, capability: str) -> str:
        descriptions = {
            "inspect-page": "Inspect the active page and collect DOM metadata plus screenshots.",
            "browser-automation": "Run guided browser automation steps using the built-in Playwright runtime.",
            "browser-control": "Send low-level browser control commands to the browser runtime.",
            "read-file": "Read file content through the MCP filesystem bridge.",
            "write-file": "Write or overwrite a file through the MCP filesystem bridge.",
            "write-artifact": "Persist an artifact into the current run artifact directory.",
            "list-dir": "List files and folders through the MCP filesystem bridge.",
            "search": "Search indexed knowledge content exposed by the MCP server.",
            "fetch-document": "Fetch a single knowledge document or note from the MCP server.",
            "create-issue": "Create an issue in the external tracking system.",
            "update-issue": "Update an existing issue in the external tracking system.",
            "query-issue": "Query issues in the external tracking system.",
        }
        return descriptions.get(capability, "Built-in MCP capability.")
