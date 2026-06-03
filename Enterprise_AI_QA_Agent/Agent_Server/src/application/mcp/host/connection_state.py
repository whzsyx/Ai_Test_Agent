from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


McpConnectionStatus = Literal[
    "disconnected",
    "connecting",
    "connected",
    "degraded",
    "reconnecting",
    "failed",
]


@dataclass
class McpToolInfo:
    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)


@dataclass
class McpResourceInfo:
    uri: str
    name: str = ""
    description: str = ""
    mime_type: str | None = None


@dataclass
class McpPromptInfo:
    name: str
    description: str = ""
    arguments: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class McpCallResult:
    ok: bool
    summary: str
    payload: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass
class McpConnectionState:
    server_key: str
    status: McpConnectionStatus = "disconnected"
    tool_count: int = 0
    resource_count: int = 0
    prompt_count: int = 0
    last_error: str | None = None
    connected_at: datetime | None = None
    last_health_at: datetime | None = None
    transport: str = ""

    def to_payload(self) -> dict[str, Any]:
        return {
            "server_key": self.server_key,
            "status": self.status,
            "tool_count": self.tool_count,
            "resource_count": self.resource_count,
            "prompt_count": self.prompt_count,
            "last_error": self.last_error,
            "connected_at": self.connected_at.isoformat() if self.connected_at else None,
            "last_health_at": self.last_health_at.isoformat() if self.last_health_at else None,
            "transport": self.transport,
        }
