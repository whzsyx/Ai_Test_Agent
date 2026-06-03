from __future__ import annotations

from typing import Any, Protocol


class McpTransport(Protocol):
    async def open(self) -> Any:
        """Open the transport and return an MCP SDK ClientSession."""

    async def close(self) -> None:
        """Close the transport and release any subprocess/network resources."""
