from __future__ import annotations

import asyncio
import hashlib
import re
from datetime import datetime
from typing import Any

from src.core.config import Settings
from src.infrastructure.arango_runtime import ArangoRuntimeProvider, day_bucket, make_json_safe, serialize_datetime


class UIGraphStore:
    """Persist UI Explorer output as project-scoped ArangoDB graph collections."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._provider = ArangoRuntimeProvider(settings)

    async def write_exploration_graph(
        self,
        graph: dict[str, Any],
        *,
        session_id: str,
        turn_id: str,
        trace_id: str,
        project_scope: str = "default",
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._write_sync,
            graph,
            session_id=session_id,
            turn_id=turn_id,
            trace_id=trace_id,
            project_scope=project_scope,
        )

    def _write_sync(
        self,
        graph: dict[str, Any],
        *,
        session_id: str,
        turn_id: str,
        trace_id: str,
        project_scope: str,
    ) -> dict[str, Any]:
        self._ensure_graph_collections()
        now = datetime.utcnow()
        common = {
            "project_scope": project_scope,
            "session_id": session_id,
            "turn_id": turn_id,
            "trace_id": trace_id,
            "updated_at": serialize_datetime(now),
            "day_bucket": day_bucket(now),
            "day_bucket_tz": self._settings.arango_timezone,
        }
        page_count = self._upsert_vertices(
            self._settings.arango_ui_page_collection,
            graph.get("pages") or [],
            common,
        )
        element_count = self._upsert_vertices(
            self._settings.arango_ui_element_collection,
            graph.get("elements") or [],
            common,
        )
        entity_count = self._upsert_vertices(
            self._settings.arango_ui_entity_collection,
            graph.get("entities") or [],
            common,
        )
        edge_count = 0
        for edge in graph.get("edges") or []:
            if not isinstance(edge, dict):
                continue
            edge_type = str(edge.get("type") or "").strip()
            if edge_type == "page_contains_element":
                edge_count += self._upsert_edge(
                    self._settings.arango_ui_page_contains_edge_collection,
                    from_collection=self._settings.arango_ui_page_collection,
                    to_collection=self._settings.arango_ui_element_collection,
                    edge=edge,
                    common=common,
                )
            elif edge_type == "element_belongs_to_entity":
                edge_count += self._upsert_edge(
                    self._settings.arango_ui_belongs_edge_collection,
                    from_collection=self._settings.arango_ui_element_collection,
                    to_collection=self._settings.arango_ui_entity_collection,
                    edge=edge,
                    common=common,
                )
            elif edge_type == "element_triggers_navigation":
                edge_count += self._upsert_edge(
                    self._settings.arango_ui_navigation_edge_collection,
                    from_collection=self._settings.arango_ui_element_collection,
                    to_collection=self._settings.arango_ui_page_collection,
                    edge=edge,
                    common=common,
                )
            elif edge_type == "element_reveals_element":
                edge_count += self._upsert_edge(
                    self._settings.arango_ui_reveals_edge_collection,
                    from_collection=self._settings.arango_ui_element_collection,
                    to_collection=self._settings.arango_ui_element_collection,
                    edge=edge,
                    common=common,
                )
        return {
            "status": "success",
            "backend": "arangodb",
            "project_scope": project_scope,
            "collections": {
                "pages": self._settings.arango_ui_page_collection,
                "elements": self._settings.arango_ui_element_collection,
                "entities": self._settings.arango_ui_entity_collection,
            },
            "metrics": {
                "page_vertices": page_count,
                "element_vertices": element_count,
                "entity_vertices": entity_count,
                "edges": edge_count,
            },
        }

    def _ensure_graph_collections(self) -> None:
        database = self._provider.db()
        for name in [
            self._settings.arango_ui_page_collection,
            self._settings.arango_ui_element_collection,
            self._settings.arango_ui_entity_collection,
        ]:
            if not database.has_collection(name):
                database.create_collection(name)
        for name in [
            self._settings.arango_ui_page_contains_edge_collection,
            self._settings.arango_ui_belongs_edge_collection,
            self._settings.arango_ui_navigation_edge_collection,
            self._settings.arango_ui_reveals_edge_collection,
        ]:
            if not database.has_collection(name):
                database.create_collection(name, edge=True)

    def _upsert_vertices(self, collection_name: str, rows: list[Any], common: dict[str, Any]) -> int:
        collection = self._provider.collection(collection_name)
        count = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            key = self._scoped_key(common["project_scope"], row.get("id"))
            if not key:
                continue
            document = {
                "_key": key,
                **make_json_safe(row),
                **common,
            }
            if collection.has(key):
                collection.update(document)
            else:
                collection.insert(document)
            count += 1
        return count

    def _upsert_edge(
        self,
        collection_name: str,
        *,
        from_collection: str,
        to_collection: str,
        edge: dict[str, Any],
        common: dict[str, Any],
    ) -> int:
        project_scope = str(common.get("project_scope") or "default")
        from_key = self._scoped_key(project_scope, edge.get("from"))
        to_key = self._scoped_key(project_scope, edge.get("to"))
        if not from_key or not to_key:
            return 0
        collection = self._provider.collection(collection_name)
        key = self._scoped_key(
            project_scope,
            edge.get("type"),
            edge.get("from"),
            edge.get("to"),
            edge.get("href") or "",
        )
        document = {
            "_key": key,
            "_from": f"{from_collection}/{from_key}",
            "_to": f"{to_collection}/{to_key}",
            **make_json_safe(edge),
            **common,
        }
        if collection.has(key):
            collection.update(document)
        else:
            collection.insert(document)
        return 1

    def _scoped_key(self, *parts: Any) -> str:
        raw = "::".join(str(part or "") for part in parts).strip()
        if not raw:
            return ""
        digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
        label = re.sub(r"[^A-Za-z0-9_.:@()+,=;$!*'%-]+", "_", str(parts[-1] or "item")).strip("._")
        label = label[:64] or "item"
        return f"{label}_{digest}"
