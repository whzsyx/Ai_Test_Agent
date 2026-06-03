from __future__ import annotations

from typing import Any

from src.application.context.mcp_runtime_service import MCPRuntimeService
from src.application.mcp.host.connection_manager import McpConnectionManager
from src.registry.mcp import MCPRegistry
from src.schemas.mcp_management import (
    ManagedMCPServerDescriptor,
    ManagedMCPPromptDescriptor,
    ManagedMCPPromptsResponse,
    ManagedMCPResourceDescriptor,
    ManagedMCPResourcesResponse,
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
        connection_manager: McpConnectionManager | None = None,
    ) -> None:
        self._builtin_registry = builtin_registry
        self._mcp_runtime_service = mcp_runtime_service
        self._connection_manager = connection_manager

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

    async def list_resources(self, descriptor: ManagedMCPServerDescriptor) -> ManagedMCPResourcesResponse:
        resources: list[ManagedMCPResourceDescriptor] = []
        if descriptor.source_kind == "external" and self._connection_manager is not None:
            resources = [
                ManagedMCPResourceDescriptor(
                    uri=resource.uri,
                    name=resource.name,
                    description=resource.description,
                    mime_type=resource.mime_type,
                    managed_server_key=descriptor.key,
                    server_name=descriptor.name,
                    provider_key=descriptor.provider_key,
                    tags=[descriptor.transport or "unknown", "resource", "mcp-host"],
                )
                for resource in await self._connection_manager.list_resources(descriptor.key)
            ]
        return ManagedMCPResourcesResponse(
            server_key=descriptor.key,
            server_name=descriptor.name,
            source_kind=descriptor.source_kind,
            resources=resources,
        )

    async def list_prompts(self, descriptor: ManagedMCPServerDescriptor) -> ManagedMCPPromptsResponse:
        prompts: list[ManagedMCPPromptDescriptor] = []
        if descriptor.source_kind == "external" and self._connection_manager is not None:
            prompts = [
                ManagedMCPPromptDescriptor(
                    name=prompt.name,
                    description=prompt.description,
                    arguments=prompt.arguments,
                    managed_server_key=descriptor.key,
                    server_name=descriptor.name,
                    provider_key=descriptor.provider_key,
                    tags=[descriptor.transport or "unknown", "prompt", "mcp-host"],
                )
                for prompt in await self._connection_manager.list_prompts(descriptor.key)
            ]
        return ManagedMCPPromptsResponse(
            server_key=descriptor.key,
            server_name=descriptor.name,
            source_kind=descriptor.source_kind,
            prompts=prompts,
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

        tools = await self._safe_list_external_tools(descriptor)
        connection_state = self.get_connection_state(descriptor.key)
        ok = connection_state is not None and connection_state.status == "connected"
        return ManagedMCPTestResponse(
            ok=ok,
            message=(
                connection_state.last_error
                if connection_state is not None and connection_state.status == "failed" and connection_state.last_error
                else ("MCP Host server is connected." if ok else "MCP Host server is not connected.")
            ),
            server_key=descriptor.key,
            server_name=descriptor.name,
            source_kind=descriptor.source_kind,
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

        if self._connection_manager is not None:
            result = await self._connection_manager.call_tool(
                descriptor.key,
                tool_name,
                arguments,
            )
            return ManagedMCPToolCallResponse(
                ok=result.ok,
                server_key=descriptor.key,
                server_name=descriptor.name,
                source_kind=descriptor.source_kind,
                tool_name=tool_name,
                result=result.payload,
                error=result.error,
            )

        return ManagedMCPToolCallResponse(
            ok=False,
            server_key=descriptor.key,
            server_name=descriptor.name,
            source_kind=descriptor.source_kind,
            tool_name=tool_name,
            error="MCP Host connection manager is not configured.",
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
        if self._connection_manager is not None:
            tools = await self._connection_manager.list_tools(descriptor.key)
            return [
                ManagedMCPToolDescriptor(
                    key=tool.name,
                    name=tool.name,
                    description=tool.description,
                    input_schema=tool.input_schema,
                    source_kind="external_tool",
                    managed_server_key=descriptor.key,
                    server_name=descriptor.name,
                    provider_key=descriptor.provider_key,
                    tags=[descriptor.transport or "unknown", "discovered-tool", "mcp-host"],
                )
                for tool in tools
            ]

        return []

    async def _safe_list_external_tools(self, descriptor: ManagedMCPServerDescriptor) -> list[ManagedMCPToolDescriptor]:
        try:
            return (await self.list_tools(descriptor)).tools
        except Exception:
            return []

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

    def get_connection_state(self, server_key: str):
        if self._connection_manager is None:
            return None
        return self._connection_manager.get_state(server_key)
