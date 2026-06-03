from __future__ import annotations

from urllib.parse import quote, unquote


PREFIX = "mcp"
SEPARATOR = "__"


def encode(server_key: str, tool_name: str) -> str:
    server = quote(str(server_key or "").strip(), safe="-._~")
    tool = quote(str(tool_name or "").strip(), safe="-._~")
    if not server or not tool:
        raise ValueError("MCP namespace requires both server_key and tool_name.")
    return f"{PREFIX}{SEPARATOR}{server}{SEPARATOR}{tool}"


def decode(tool_key: str) -> tuple[str, str]:
    parts = str(tool_key or "").split(SEPARATOR, 2)
    if len(parts) != 3 or parts[0] != PREFIX:
        raise ValueError(f"Tool key '{tool_key}' is not an MCP bridge tool key.")
    server = unquote(parts[1])
    tool = unquote(parts[2])
    if not server or not tool:
        raise ValueError(f"Tool key '{tool_key}' has an invalid MCP namespace.")
    return server, tool


def is_mcp_tool_key(tool_key: str) -> bool:
    return str(tool_key or "").startswith(f"{PREFIX}{SEPARATOR}")
