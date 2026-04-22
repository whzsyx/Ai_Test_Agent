from __future__ import annotations

from src.schemas.agent import MCPServerDescriptor


class MCPRegistry:
    def __init__(self) -> None:
        self._servers: dict[str, MCPServerDescriptor] = {
            "browser-mcp": MCPServerDescriptor(
                key="browser-mcp",
                name="Browser MCP",
                summary="Expose playwright-cli browser control and page state through MCP.",
                transport="stdio",
                status="ready",
                capabilities=["inspect-page", "browser-automation", "browser-control"],
                enabled=True,
            ),
            "filesystem-mcp": MCPServerDescriptor(
                key="filesystem-mcp",
                name="Filesystem MCP",
                summary="Read and write run artifacts or fixture files.",
                transport="stdio",
                status="ready",
                capabilities=["read-file", "write-file", "write-artifact", "list-dir"],
                enabled=True,
            ),
            "knowledge-mcp": MCPServerDescriptor(
                key="knowledge-mcp",
                name="Knowledge MCP",
                summary="Serve QA knowledge base content and curated test guidance.",
                transport="http",
                status="planned",
                capabilities=["search", "fetch-document"],
                enabled=False,
            ),
            "tracker-mcp": MCPServerDescriptor(
                key="tracker-mcp",
                name="Issue Tracker MCP",
                summary="Push defects, statuses, and reproduction notes to external systems.",
                transport="http",
                status="planned",
                capabilities=["create-issue", "update-issue", "query-issue"],
                enabled=False,
            ),
        }

    def list(self) -> list[MCPServerDescriptor]:
        return list(self._servers.values())

    def list_enabled(self) -> list[MCPServerDescriptor]:
        return [server for server in self._servers.values() if server.enabled]

    def get(self, key: str) -> MCPServerDescriptor | None:
        return self._servers.get(key)
