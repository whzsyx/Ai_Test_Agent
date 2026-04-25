from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime
from typing import Any

from src.core.config import Settings
from src.infrastructure.arango_runtime import ArangoRuntimeProvider
from src.schemas.knowledge import (
    KnowledgeGraphEdge,
    KnowledgeGraphNode,
    KnowledgeProjectDeleteResponse,
    KnowledgeGraphResponse,
    KnowledgeGraphSummary,
    KnowledgeProjectSummary,
)


class KnowledgeGraphService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._provider = ArangoRuntimeProvider(settings)

    async def list_projects(self) -> list[KnowledgeProjectSummary]:
        return await asyncio.to_thread(self._list_projects_sync)

    async def get_graph(self, project_scope: str) -> KnowledgeGraphResponse:
        return await asyncio.to_thread(self._get_graph_sync, project_scope)

    async def delete_project(self, project_scope: str) -> KnowledgeProjectDeleteResponse:
        return await asyncio.to_thread(self._delete_project_sync, project_scope)

    def _list_projects_sync(self) -> list[KnowledgeProjectSummary]:
        summary_map: dict[str, dict[str, Any]] = {}

        self._merge_scope_counts(
            summary_map,
            self._settings.arango_ui_page_collection,
            "page_count",
        )
        self._merge_scope_counts(
            summary_map,
            self._settings.arango_ui_element_collection,
            "element_count",
        )
        self._merge_scope_counts(
            summary_map,
            self._settings.arango_ui_entity_collection,
            "entity_count",
        )
        for collection_name in [
            self._settings.arango_ui_page_contains_edge_collection,
            self._settings.arango_ui_belongs_edge_collection,
            self._settings.arango_ui_navigation_edge_collection,
            self._settings.arango_ui_reveals_edge_collection,
        ]:
            self._merge_scope_counts(summary_map, collection_name, "edge_count")

        items = [
            KnowledgeProjectSummary(
                project_scope=scope,
                page_count=int(data.get("page_count") or 0),
                element_count=int(data.get("element_count") or 0),
                entity_count=int(data.get("entity_count") or 0),
                edge_count=int(data.get("edge_count") or 0),
                latest_updated_at=self._parse_datetime(data.get("latest_updated_at")),
            )
            for scope, data in summary_map.items()
            if scope
        ]
        items.sort(
            key=lambda item: (
                item.latest_updated_at or datetime.min,
                item.page_count + item.element_count + item.entity_count + item.edge_count,
                item.project_scope,
            ),
            reverse=True,
        )
        return items

    def _get_graph_sync(self, project_scope: str) -> KnowledgeGraphResponse:
        scope = str(project_scope or "").strip()
        if not scope:
            raise ValueError("project_scope is required")

        pages = self._fetch_collection_rows(self._settings.arango_ui_page_collection, scope)
        elements = self._fetch_collection_rows(self._settings.arango_ui_element_collection, scope)
        entities = self._fetch_collection_rows(self._settings.arango_ui_entity_collection, scope)
        if not pages and not elements and not entities:
            raise KeyError(scope)

        edges_by_type: dict[str, list[dict[str, Any]]] = {}
        for edge_type, collection_name in [
            ("page_contains_element", self._settings.arango_ui_page_contains_edge_collection),
            ("element_belongs_to_entity", self._settings.arango_ui_belongs_edge_collection),
            ("element_triggers_navigation", self._settings.arango_ui_navigation_edge_collection),
            ("element_reveals_element", self._settings.arango_ui_reveals_edge_collection),
        ]:
            edges_by_type[edge_type] = self._fetch_collection_rows(collection_name, scope)

        nodes = [
            *[self._page_to_node(item) for item in pages],
            *[self._element_to_node(item) for item in elements],
            *[self._entity_to_node(item) for item in entities],
        ]
        edges: list[KnowledgeGraphEdge] = []
        relation_counts: dict[str, int] = defaultdict(int)
        for edge_type, rows in edges_by_type.items():
            for row in rows:
                edge = self._edge_to_record(row, edge_type)
                if edge is None:
                    continue
                edges.append(edge)
                relation_counts[edge.type] += 1

        latest_updated_at = max(
            (
                value
                for value in (
                    [self._parse_datetime(item.get("updated_at")) for item in pages]
                    + [self._parse_datetime(item.get("updated_at")) for item in elements]
                    + [self._parse_datetime(item.get("updated_at")) for item in entities]
                )
                if value is not None
            ),
            default=None,
        )

        return KnowledgeGraphResponse(
            summary=KnowledgeGraphSummary(
                project_scope=scope,
                page_count=len(pages),
                element_count=len(elements),
                entity_count=len(entities),
                edge_count=len(edges),
                relation_counts=dict(sorted(relation_counts.items())),
                latest_updated_at=latest_updated_at,
            ),
            nodes=nodes,
            edges=edges,
        )

    def _delete_project_sync(self, project_scope: str) -> KnowledgeProjectDeleteResponse:
        scope = str(project_scope or "").strip()
        if not scope:
            raise ValueError("project_scope is required")

        collection_names = {
            "pages": self._settings.arango_ui_page_collection,
            "elements": self._settings.arango_ui_element_collection,
            "entities": self._settings.arango_ui_entity_collection,
            "page_contains_element": self._settings.arango_ui_page_contains_edge_collection,
            "element_belongs_to_entity": self._settings.arango_ui_belongs_edge_collection,
            "element_triggers_navigation": self._settings.arango_ui_navigation_edge_collection,
            "element_reveals_element": self._settings.arango_ui_reveals_edge_collection,
        }

        existing = any(self._count_scope_rows(name, scope) > 0 for name in collection_names.values())
        if not existing:
            raise KeyError(scope)

        deleted_counts: dict[str, int] = {}
        for label, collection_name in collection_names.items():
            deleted_counts[label] = self._delete_scope_rows(collection_name, scope)

        return KnowledgeProjectDeleteResponse(
            ok=True,
            project_scope=scope,
            deleted_counts=deleted_counts,
            message=f"Deleted knowledge graph project '{scope}'",
        )

    def _merge_scope_counts(
        self,
        summary_map: dict[str, dict[str, Any]],
        collection_name: str,
        count_field: str,
    ) -> None:
        query = """
        FOR doc IN @@collection
          FILTER doc.project_scope != null AND doc.project_scope != ""
          COLLECT scope = doc.project_scope INTO grouped
          RETURN {
            project_scope: scope,
            total: LENGTH(grouped),
            latest_updated_at: MAX(grouped[*].doc.updated_at)
          }
        """
        rows = self._provider.execute(query, {"@collection": collection_name})
        for row in rows:
            scope = str(row.get("project_scope") or "").strip()
            if not scope:
                continue
            entry = summary_map.setdefault(
                scope,
                {
                    "page_count": 0,
                    "element_count": 0,
                    "entity_count": 0,
                    "edge_count": 0,
                    "latest_updated_at": None,
                },
            )
            entry[count_field] = int(entry.get(count_field) or 0) + int(row.get("total") or 0)
            latest = row.get("latest_updated_at")
            if latest and (entry["latest_updated_at"] is None or str(latest) > str(entry["latest_updated_at"])):
                entry["latest_updated_at"] = latest

    def _fetch_collection_rows(self, collection_name: str, project_scope: str) -> list[dict[str, Any]]:
        query = """
        FOR doc IN @@collection
          FILTER doc.project_scope == @project_scope
          SORT doc.updated_at DESC, doc._key ASC
          RETURN UNSET(doc, ["_id", "_rev"])
        """
        return self._provider.execute(
            query,
            {
                "@collection": collection_name,
                "project_scope": project_scope,
            },
        )

    def _count_scope_rows(self, collection_name: str, project_scope: str) -> int:
        query = """
        RETURN LENGTH(
          FOR doc IN @@collection
            FILTER doc.project_scope == @project_scope
            RETURN 1
        )
        """
        rows = self._provider.execute(
            query,
            {
                "@collection": collection_name,
                "project_scope": project_scope,
            },
        )
        return int(rows[0] or 0) if rows else 0

    def _delete_scope_rows(self, collection_name: str, project_scope: str) -> int:
        query = """
        LET to_remove = (
          FOR doc IN @@collection
            FILTER doc.project_scope == @project_scope
            RETURN doc
        )
        FOR doc IN to_remove
          REMOVE doc IN @@collection
        RETURN LENGTH(to_remove)
        """
        rows = self._provider.execute(
            query,
            {
                "@collection": collection_name,
                "project_scope": project_scope,
            },
        )
        return int(rows[0] or 0) if rows else 0

    def _page_to_node(self, row: dict[str, Any]) -> KnowledgeGraphNode:
        label = str(row.get("title") or row.get("name") or row.get("url") or row.get("id") or "Page").strip()
        summary = str(row.get("url") or row.get("id") or "").strip()
        return KnowledgeGraphNode(
            id=str(row.get("id") or row.get("_key") or label),
            label=label,
            kind="page",
            summary=summary,
            metadata=self._clean_metadata(
                row,
                exclude={"id", "title", "name", "url", "_key"},
            ),
        )

    def _element_to_node(self, row: dict[str, Any]) -> KnowledgeGraphNode:
        role = str(row.get("role") or "").strip()
        name = str(row.get("name") or row.get("title") or "").strip()
        label = name or role or str(row.get("id") or "Element")
        summary = role or str(row.get("context_role") or "").strip()
        return KnowledgeGraphNode(
            id=str(row.get("id") or row.get("_key") or label),
            label=label,
            kind="element",
            summary=summary,
            metadata=self._clean_metadata(
                row,
                exclude={"id", "name", "title", "role", "_key"},
            ),
        )

    def _entity_to_node(self, row: dict[str, Any]) -> KnowledgeGraphNode:
        label = str(row.get("name") or row.get("title") or row.get("id") or "Entity").strip()
        summary = str(row.get("type") or row.get("role") or "").strip()
        return KnowledgeGraphNode(
            id=str(row.get("id") or row.get("_key") or label),
            label=label,
            kind="entity",
            summary=summary,
            metadata=self._clean_metadata(
                row,
                exclude={"id", "name", "title", "type", "role", "_key"},
            ),
        )

    def _edge_to_record(self, row: dict[str, Any], fallback_type: str) -> KnowledgeGraphEdge | None:
        source = str(row.get("from") or "").strip()
        target = str(row.get("to") or "").strip()
        if not source or not target:
            return None
        edge_type = str(row.get("type") or fallback_type).strip() or fallback_type
        return KnowledgeGraphEdge(
            id=str(row.get("_key") or f"{edge_type}:{source}:{target}"),
            source=source,
            target=target,
            type=edge_type,
            label=self._format_relation_label(edge_type),
            metadata=self._clean_metadata(
                row,
                exclude={"_key", "_from", "_to", "from", "to", "type"},
            ),
        )

    def _clean_metadata(self, row: dict[str, Any], *, exclude: set[str]) -> dict[str, Any]:
        return {
            str(key): value
            for key, value in row.items()
            if key not in exclude and not str(key).startswith("_")
        }

    def _format_relation_label(self, edge_type: str) -> str:
        return edge_type.replace("_", " ").title()

    def _parse_datetime(self, value: Any) -> datetime | None:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value))
        except ValueError:
            return None
