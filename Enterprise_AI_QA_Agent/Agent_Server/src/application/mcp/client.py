from __future__ import annotations

import json
from typing import Any

import httpx

from src.core.config import Settings


class ExternalMCPSession:
    def __init__(
        self,
        *,
        endpoint_url: str,
        headers: dict[str, str],
        session_id: str | None = None,
    ) -> None:
        self.endpoint_url = endpoint_url
        self.headers = dict(headers)
        self.session_id = session_id


class ExternalMCPClient:
    def __init__(self, *, settings: Settings) -> None:
        self._settings = settings

    async def initialize(self, *, endpoint_url: str, headers: dict[str, str]) -> ExternalMCPSession:
        request_headers = dict(headers)
        request_headers.setdefault("Accept", "application/json, text/event-stream")
        request_headers.setdefault("Content-Type", "application/json")
        payload = {
            "jsonrpc": "2.0",
            "id": "initialize",
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {
                    "name": "enterprise-ai-qa-agent",
                    "version": "0.2.0",
                },
            },
        }
        response = await self._post(endpoint_url=endpoint_url, headers=request_headers, payload=payload)
        session = ExternalMCPSession(
            endpoint_url=endpoint_url,
            headers=request_headers,
            session_id=self._extract_session_id(response.headers),
        )
        if session.session_id:
            session.headers["Mcp-Session-Id"] = session.session_id
        return session

    async def notify_initialized(self, session: ExternalMCPSession) -> None:
        payload = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        }
        await self._post(endpoint_url=session.endpoint_url, headers=session.headers, payload=payload)

    async def list_tools(self, session: ExternalMCPSession) -> list[dict[str, Any]]:
        payload = {
            "jsonrpc": "2.0",
            "id": "tools-list",
            "method": "tools/list",
            "params": {},
        }
        response = await self._post(endpoint_url=session.endpoint_url, headers=session.headers, payload=payload)
        data = self._parse_jsonrpc_response(response.text)
        result = data.get("result", {})
        tools = result.get("tools", [])
        return [item for item in tools if isinstance(item, dict)]

    async def call_tool(
        self,
        session: ExternalMCPSession,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        request_id: str | None = None,
    ) -> dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": request_id or f"call-{tool_name}",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }
        response = await self._post(endpoint_url=session.endpoint_url, headers=session.headers, payload=payload)
        return self._parse_jsonrpc_response(response.text)

    async def _post(self, *, endpoint_url: str, headers: dict[str, str], payload: dict[str, Any]) -> httpx.Response:
        async with httpx.AsyncClient(
            timeout=min(self._settings.llm_request_timeout_seconds, 45.0),
            follow_redirects=True,
        ) as client:
            response = await client.post(endpoint_url, headers=headers, json=payload)
            response.raise_for_status()
            return response

    def _extract_session_id(self, headers: httpx.Headers) -> str | None:
        return (
            headers.get("mcp-session-id")
            or headers.get("Mcp-Session-Id")
            or headers.get("x-mcp-session-id")
        )

    def _parse_jsonrpc_response(self, body: str) -> dict[str, Any]:
        stripped = body.strip()
        if not stripped:
            return {}
        if stripped.startswith("event:"):
            data_lines: list[str] = []
            for line in stripped.splitlines():
                if line.startswith("data:"):
                    data_lines.append(line[len("data:"):].strip())
            if not data_lines:
                raise ValueError("MCP response did not contain any data payload.")
            return json.loads("\n".join(data_lines))
        return json.loads(stripped)
