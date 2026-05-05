from __future__ import annotations

import base64
import json
from typing import Any

from src.application.mcp.client import ExternalMCPClient
from src.application.mcp.provider_base import BaseExternalMCPProvider
from src.schemas.integration import (
    IntegrationImportSourceDescriptor,
    IntegrationImportSourcesResponse,
    IntegrationRecord,
    IntegrationWorkspaceDescriptor,
)
from src.schemas.mcp_management import MCPProviderDescriptor, ResolvedImportDocument


class PostmanExternalMCPProvider(BaseExternalMCPProvider):
    descriptor = MCPProviderDescriptor(
        key="postman",
        name="Postman MCP",
        summary="Manage Postman workspaces, collections, and API assets through a remote MCP endpoint.",
        supports_workspace_selection=True,
        supports_document_import=True,
    )

    def __init__(self, *, client: ExternalMCPClient) -> None:
        self._client = client

    def supports(self, integration: IntegrationRecord) -> bool:
        if integration.kind != "mcp":
            return False
        endpoint = (integration.endpoint_url or integration.document_url or "").lower()
        name = (integration.name or "").lower()
        description = (integration.description or "").lower()
        return "postman.com" in endpoint or "postman" in name or "postman" in description

    async def list_import_sources(
        self,
        integration: IntegrationRecord,
        *,
        workspace_id: str | None = None,
    ) -> IntegrationImportSourcesResponse:
        session, tool_map = await self._open_session(integration)
        workspaces = await self._list_workspaces(session, tool_map)
        workspace_lookup = {item.id: item for item in workspaces}

        sources: list[IntegrationImportSourceDescriptor] = []
        if workspace_id:
            workspace = workspace_lookup.get(workspace_id)
            if workspace is None:
                raise ValueError("未找到所选的 Postman 工作区。")
            sources.extend(await self._list_collection_sources(session, tool_map, workspace))
            sources.extend(await self._list_spec_sources(session, tool_map, workspace))

        return IntegrationImportSourcesResponse(
            integration_id=integration.id,
            kind=integration.kind,
            supports_workspace_selection=True,
            workspaces=workspaces,
            sources=sources,
        )

    async def resolve_import_document(
        self,
        integration: IntegrationRecord,
        *,
        import_source_id: str,
        workspace_id: str | None = None,
    ) -> ResolvedImportDocument:
        session, tool_map = await self._open_session(integration)
        kind, object_id = self._split_source_id(import_source_id)

        if kind == "collection":
            document = await self._resolve_collection_document(session, tool_map, collection_id=object_id)
            if workspace_id:
                document.project_name = integration.project_name or workspace_id
            return document

        raise ValueError("当前仅支持从 Postman Collection 导入接口文档。")

    async def _open_session(self, integration: IntegrationRecord) -> tuple[object, dict[str, str]]:
        endpoint_url = integration.endpoint_url or integration.document_url
        if not endpoint_url:
            raise ValueError("当前 Postman MCP 接入缺少 Endpoint URL。")
        session = await self._client.initialize(endpoint_url=endpoint_url, headers=integration.headers)
        await self._client.notify_initialized(session)
        tools = await self._client.list_tools(session)
        return session, self._discover_tools(tools)

    def _discover_tools(self, tools: list[dict[str, Any]]) -> dict[str, str]:
        names = {str(item.get("name")) for item in tools if item.get("name")}
        mapping = {
            "get_workspaces": "getWorkspaces",
            "get_collections": "getCollections",
            "get_collection": "getCollection",
            "get_collection_request": "getCollectionRequest",
            "get_all_specs": "getAllSpecs",
        }
        discovered: dict[str, str] = {}
        for key, name in mapping.items():
            if name in names:
                discovered[key] = name
        if "get_workspaces" not in discovered:
            raise ValueError("当前 Postman MCP 未暴露工作区查询工具 getWorkspaces。")
        return discovered

    async def _list_workspaces(
        self,
        session: object,
        tool_map: dict[str, str],
    ) -> list[IntegrationWorkspaceDescriptor]:
        payload = await self._client.call_tool(
            session,
            tool_name=tool_map["get_workspaces"],
            arguments={},
            request_id="postman-get-workspaces",
        )
        text = self._extract_text_content(payload)
        rows = self._parse_markdown_table(text)
        workspaces: list[IntegrationWorkspaceDescriptor] = []
        for row in rows:
            workspace_id = row.get("id")
            workspace_name = row.get("name")
            if not workspace_id or not workspace_name:
                continue
            workspaces.append(
                IntegrationWorkspaceDescriptor(
                    id=workspace_id,
                    name=workspace_name,
                    description=row.get("about") or None,
                    project_name=None,
                    document_count=0,
                )
            )
        return workspaces

    async def _list_collection_sources(
        self,
        session: object,
        tool_map: dict[str, str],
        workspace: IntegrationWorkspaceDescriptor,
    ) -> list[IntegrationImportSourceDescriptor]:
        tool_name = tool_map.get("get_collections")
        if not tool_name:
            return []
        payload = await self._client.call_tool(
            session,
            tool_name=tool_name,
            arguments={"workspace": workspace.id},
            request_id=f"postman-get-collections-{workspace.id}",
        )
        text = self._extract_text_content(payload)
        rows = self._parse_markdown_table(text)
        sources: list[IntegrationImportSourceDescriptor] = []
        for row in rows:
            collection_id = row.get("id")
            collection_name = row.get("name")
            if not collection_id or not collection_name:
                continue
            sources.append(
                IntegrationImportSourceDescriptor(
                    id=f"collection:{collection_id}",
                    label=collection_name,
                    document_url=f"postman://collection/{collection_id}",
                    kind="postman_collection",
                    summary=f"Postman 工作区 {workspace.name} 中的 Collection",
                    project_name=workspace.project_name,
                    workspace_id=workspace.id,
                    workspace_name=workspace.name,
                )
            )
        return sources

    async def _list_spec_sources(
        self,
        session: object,
        tool_map: dict[str, str],
        workspace: IntegrationWorkspaceDescriptor,
    ) -> list[IntegrationImportSourceDescriptor]:
        tool_name = tool_map.get("get_all_specs")
        if not tool_name:
            return []
        payload = await self._client.call_tool(
            session,
            tool_name=tool_name,
            arguments={"workspaceId": workspace.id},
            request_id=f"postman-get-specs-{workspace.id}",
        )
        text = self._extract_text_content(payload)
        parsed = self._parse_json_text(text)
        specs = parsed.get("specs")
        if not isinstance(specs, list):
            return []
        sources: list[IntegrationImportSourceDescriptor] = []
        for spec in specs:
            if not isinstance(spec, dict):
                continue
            spec_id = str(spec.get("id") or "").strip()
            spec_name = str(spec.get("name") or spec.get("summary") or "").strip()
            if not spec_id or not spec_name:
                continue
            sources.append(
                IntegrationImportSourceDescriptor(
                    id=f"spec:{spec_id}",
                    label=spec_name,
                    document_url=f"postman://spec/{spec_id}",
                    kind="postman_spec",
                    summary=f"Postman 工作区 {workspace.name} 中的 API 规范",
                    project_name=workspace.project_name,
                    workspace_id=workspace.id,
                    workspace_name=workspace.name,
                )
            )
        return sources

    async def _resolve_collection_document(
        self,
        session: object,
        tool_map: dict[str, str],
        *,
        collection_id: str,
    ) -> ResolvedImportDocument:
        collection_payload = await self._client.call_tool(
            session,
            tool_name=tool_map["get_collection"],
            arguments={"collectionId": collection_id},
            request_id=f"postman-get-collection-{collection_id}",
        )
        collection_text = self._extract_text_content(collection_payload)
        collection_data = self._parse_json_text(collection_text)
        collection = collection_data.get("collection")
        if not isinstance(collection, dict):
            raise ValueError("Postman MCP 返回的 Collection 结构无法识别。")

        info = collection.get("info")
        item_refs = collection.get("itemRefs")
        if not isinstance(info, dict):
            raise ValueError("Postman Collection 缺少 info 信息。")
        if not isinstance(item_refs, list):
            item_refs = []

        items: list[dict[str, Any]] = []
        for item_ref in item_refs:
            if not isinstance(item_ref, dict):
                continue
            request_id = str(item_ref.get("id") or "").strip()
            if not request_id:
                continue
            request_payload = await self._client.call_tool(
                session,
                tool_name=tool_map["get_collection_request"],
                arguments={
                    "collectionId": collection_id,
                    "requestId": request_id,
                },
                request_id=f"postman-get-request-{request_id}",
            )
            request_text = self._extract_text_content(request_payload)
            request_data = self._parse_json_text(request_text)
            request_entry = self._build_collection_item(request_data)
            if request_entry is not None:
                items.append(request_entry)

        collection_name = str(info.get("name") or collection_id).strip()
        collection_json = {
            "info": {
                "_postman_id": info.get("_postman_id") or collection_id,
                "name": collection_name,
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            },
            "item": items,
        }
        content = json.dumps(collection_json, ensure_ascii=False, indent=2).encode("utf-8")
        return ResolvedImportDocument(
            mode="inline",
            filename=f"{self._slugify(collection_name)}.postman_collection.json",
            content_base64=base64.b64encode(content).decode("ascii"),
            content_type="application/json",
            title=collection_name,
        )

    def _build_collection_item(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        data = payload.get("data")
        if not isinstance(data, dict):
            return None
        name = str(data.get("name") or "Untitled Request").strip()
        method = str(data.get("method") or "GET").strip().upper()
        url = str(data.get("url") or "").strip()
        header_data = data.get("headerData")
        headers = []
        if isinstance(header_data, list):
            for item in header_data:
                if not isinstance(item, dict):
                    continue
                if item.get("enabled") is False:
                    continue
                key = str(item.get("key") or "").strip()
                if not key:
                    continue
                headers.append(
                    {
                        "key": key,
                        "value": str(item.get("value") or ""),
                    }
                )

        request: dict[str, Any] = {
            "method": method,
            "header": headers,
            "url": {"raw": url} if url else {"raw": ""},
        }
        raw_body = data.get("rawModeData")
        if isinstance(raw_body, str) and raw_body.strip():
            request["body"] = {
                "mode": "raw",
                "raw": raw_body,
                "options": {
                    "raw": {
                        "language": "json",
                    }
                },
            }
        description = data.get("description")
        item: dict[str, Any] = {
            "name": name,
            "request": request,
        }
        if isinstance(description, str) and description.strip():
            item["description"] = description.strip()
        return item

    def _extract_text_content(self, payload: dict[str, Any]) -> str:
        result = payload.get("result")
        if not isinstance(result, dict):
            raise ValueError("MCP 调用返回内容为空。")
        if result.get("isError"):
            content = result.get("content")
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        raise ValueError(str(item.get("text") or "MCP 调用失败。"))
            raise ValueError("MCP 调用失败。")
        content = result.get("content")
        if not isinstance(content, list):
            raise ValueError("MCP 返回中没有 content 内容。")
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = item.get("text")
                if isinstance(text, str):
                    return text
        raise ValueError("MCP 返回内容中没有可解析的文本。")

    def _parse_markdown_table(self, text: str) -> list[dict[str, str]]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        header_index = next((index for index, line in enumerate(lines) if line.startswith("|") and line.endswith("|")), None)
        if header_index is None or header_index + 1 >= len(lines):
            return []
        headers = [part.strip() for part in lines[header_index].strip("|").split("|")]
        rows: list[dict[str, str]] = []
        for line in lines[header_index + 2:]:
            if not (line.startswith("|") and line.endswith("|")):
                break
            values = [part.strip() for part in line.strip("|").split("|")]
            if len(values) != len(headers):
                continue
            rows.append(dict(zip(headers, values)))
        return rows

    def _parse_json_text(self, text: str) -> dict[str, Any]:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("MCP 返回内容不是有效 JSON。") from exc
        if not isinstance(parsed, dict):
            raise ValueError("MCP 返回的 JSON 结构不是对象。")
        return parsed

    def _split_source_id(self, source_id: str) -> tuple[str, str]:
        kind, _, object_id = source_id.partition(":")
        if not kind or not object_id:
            raise ValueError("导入源标识格式无效。")
        return kind, object_id

    def _slugify(self, value: str) -> str:
        slug = "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")
        return slug or "postman-collection"
