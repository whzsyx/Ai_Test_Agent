"""API doc resolution shared service.

Wraps ApiDocsService to provide structured doc discovery and
endpoint resolution for performance_testing_mode and other modes.

Design: per performance_testing_mode_image_capability_and_api_doc_resolution_design.md
section 11-14.
"""
from __future__ import annotations

import logging
from typing import Any

from src.application.api_doc_resolution.contracts import (
    DocResolutionResult,
    ResolvedEndpoint,
)
from src.application.documents.api_docs_service import ApiDocsService

logger = logging.getLogger(__name__)

_AMBIGUOUS_SCORE_GAP = 20


class ApiDocResolutionService:
    """Shared service for discovering and resolving API docs to concrete endpoints."""

    def __init__(self, *, api_docs_service: ApiDocsService) -> None:
        self._api_docs_service = api_docs_service

    async def discover_project_docs(
        self,
        *,
        project_name: str | None = None,
        project_url: str | None = None,
    ) -> DocResolutionResult:
        """Check whether API documents exist and locate project candidates."""
        documents = await self._api_docs_service.list_documents()
        if not documents:
            return DocResolutionResult(
                status="awaiting_input",
                missing_doc_reason="no_documents_in_library",
                summary="系统中完全没有导入任何 API 文档，请上传接口文档或提供 OpenAPI/Swagger URL。",
            )

        search_result = await self._api_docs_service.search_documents(
            project_name=project_name,
            project_url=project_url,
            limit=50,
        )
        matches = search_result.get("matches", [])
        total = search_result.get("total_match_count", len(matches))

        if not matches:
            return DocResolutionResult(
                status="awaiting_input",
                missing_doc_reason="no_project_documents",
                project_name=project_name or "",
                project_url=project_url or "",
                summary=f"未找到项目 {project_name or project_url or ''} 的 API 文档。",
            )

        candidates = self._build_candidates(matches)
        return DocResolutionResult(
            status="resolved",
            missing_doc_reason="none",
            project_name=project_name or "",
            project_url=project_url or "",
            candidates=candidates,
            summary=f"找到 {len(candidates)} 个候选文档。",
        )

    async def resolve_endpoint_from_docs(
        self,
        *,
        project_name: str | None = None,
        project_url: str | None = None,
        method: str | None = None,
        path: str | None = None,
        query: str | None = None,
    ) -> DocResolutionResult:
        """Resolve a concrete endpoint from API documents.

        Returns structured DocResolutionResult with confidence and
        missing_doc_reason per the design doc's 4-category classification.
        """
        documents = await self._api_docs_service.list_documents()
        if not documents:
            return DocResolutionResult(
                status="awaiting_input",
                missing_doc_reason="no_documents_in_library",
                summary="系统中完全没有导入任何 API 文档。",
            )

        search_result = await self._api_docs_service.search_documents(
            query=query,
            project_name=project_name,
            project_url=project_url,
            method=method,
            path=path,
            limit=20,
            include_preview=False,
        )
        matches = search_result.get("matches", [])
        endpoint_matches = [m for m in matches if m.get("match_type") == "endpoint"]
        document_matches = [m for m in matches if m.get("match_type") == "document"]

        if not matches:
            return DocResolutionResult(
                status="awaiting_input",
                missing_doc_reason="endpoint_not_found_in_docs",
                project_name=project_name or "",
                project_url=project_url or "",
                summary=f"项目文档中未找到目标接口 {method or ''} {path or query or ''}。",
            )

        if endpoint_matches:
            top = endpoint_matches[0]
            if len(endpoint_matches) > 1:
                gap = float(top.get("score", 0)) - float(endpoint_matches[1].get("score", 0))
                if gap < _AMBIGUOUS_SCORE_GAP:
                    return DocResolutionResult(
                        status="ambiguous",
                        confidence="low",
                        match_type="endpoint",
                        missing_doc_reason="ambiguous_document_match",
                        candidates=self._build_candidates(endpoint_matches),
                        summary="多个接口候选分数接近，无法高置信自动确认目标接口。",
                    )

            endpoint = self._build_resolved_endpoint(top)
            return DocResolutionResult(
                status="resolved",
                confidence="high",
                match_type="endpoint",
                missing_doc_reason="none",
                selected_doc_id=str(top.get("doc_id", "")),
                selected_doc_title=str(top.get("title", "")),
                resolved_endpoint=endpoint,
                project_name=str(top.get("project_name", "")),
                project_url=str(top.get("project_url", "")),
                candidates=self._build_candidates(matches[:5]),
                summary=f"已从文档定位目标接口: {endpoint.method} {endpoint.path}",
            )

        return DocResolutionResult(
            status="ambiguous",
            confidence="low",
            match_type="document",
            missing_doc_reason="ambiguous_document_match",
            selected_doc_id=str(document_matches[0].get("doc_id", "")) if document_matches else "",
            candidates=self._build_candidates(document_matches[:5]),
            summary="仅有文档级匹配，没有精确的接口级匹配，需要人工确认。",
        )

    async def ingest_doc_from_attachment(
        self,
        *,
        filename: str,
        content_base64: str,
        title: str | None = None,
        project_name: str | None = None,
        project_url: str | None = None,
        content_type: str | None = None,
    ) -> dict[str, Any]:
        """Import an API document from an uploaded attachment."""
        record = await self._api_docs_service.upload_document(
            filename=filename,
            content_base64=content_base64,
            source="perf_api_doc_attachment",
            title=title,
            project_name=project_name,
            project_url=project_url,
            content_type=content_type,
        )
        return {
            "ok": True,
            "action": "import_attachment",
            "summary": f"已导入 API 文档: {record.title}",
            "document": {
                "doc_id": record.id,
                "title": record.title,
                "project_name": record.project_name or "",
                "project_url": record.project_url or "",
                "endpoint_count": record.endpoint_count or 0,
            },
        }

    async def ingest_doc_from_url(
        self,
        *,
        url: str,
        title: str | None = None,
        project_name: str | None = None,
        project_url: str | None = None,
    ) -> dict[str, Any]:
        """Import an API document from a URL (OpenAPI/Swagger/markdown)."""
        record = await self._api_docs_service.import_document_from_url(
            url=url,
            title=title,
            project_name=project_name,
            project_url=project_url,
            source="perf_api_doc_url",
        )
        return {
            "ok": True,
            "action": "import_url",
            "summary": f"已从 URL 导入 API 文档: {record.title}",
            "document": {
                "doc_id": record.id,
                "title": record.title,
                "project_name": record.project_name or "",
                "project_url": record.project_url or "",
                "endpoint_count": record.endpoint_count or 0,
            },
        }

    @staticmethod
    def _build_candidates(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "doc_id": m.get("doc_id", ""),
                "title": m.get("title", ""),
                "project_name": m.get("project_name", ""),
                "method": m.get("method", ""),
                "path": m.get("path", ""),
                "score": m.get("score", 0),
                "match_type": m.get("match_type", ""),
            }
            for m in matches
        ]

    @staticmethod
    def _build_resolved_endpoint(match: dict[str, Any]) -> ResolvedEndpoint:
        project_url = str(match.get("project_url", ""))
        path = str(match.get("path", ""))
        method = str(match.get("method", "GET")).upper()
        base_url = project_url
        if path and path.startswith("http"):
            base_url = path.rsplit("/", 1)[0] if "/" in path[8:] else path
        full_url = str(match.get("full_url") or "")
        if full_url and not base_url:
            parts = full_url.split("/")
            if len(parts) >= 4:
                base_url = "/".join(parts[:3])

        return ResolvedEndpoint(
            method=method,
            path=path,
            base_url=base_url,
            doc_id=str(match.get("doc_id", "")),
        )
