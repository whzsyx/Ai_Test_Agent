from __future__ import annotations

import asyncio
import hashlib
import json
import re
from datetime import datetime
from typing import Any

from src.core.config import Settings
from src.infrastructure.memgraph_runtime import MemgraphRuntimeProvider


class UIGraphStore:
    """Persist UI Explorer output as project-scoped Memgraph nodes and relationships."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._provider = MemgraphRuntimeProvider(settings)

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
        self._provider.initialize()
        now = datetime.utcnow().isoformat()
        common = {
            "project_scope": project_scope,
            "session_id": session_id,
            "turn_id": turn_id,
            "trace_id": trace_id,
            "updated_at": now,
        }
        page_count = self._upsert_nodes("Page", graph.get("pages") or [], common)
        element_count = self._upsert_nodes("Element", graph.get("elements") or [], common)
        entity_count = self._upsert_nodes("Entity", graph.get("entities") or [], common)
        edge_count = 0
        for edge in graph.get("edges") or []:
            if not isinstance(edge, dict):
                continue
            edge_type = str(edge.get("type") or "").strip()
            if edge_type == "page_contains_element":
                edge_count += self._upsert_edge("Page", "CONTAINS", "Element", edge, common)
            elif edge_type == "element_belongs_to_entity":
                edge_count += self._upsert_edge("Element", "BELONGS_TO", "Entity", edge, common)
            elif edge_type == "element_triggers_navigation":
                edge_count += self._upsert_edge("Element", "TRIGGERS_NAVIGATION", "Page", edge, common)
            elif edge_type == "element_reveals_element":
                edge_count += self._upsert_edge("Element", "REVEALS", "Element", edge, common)
        return {
            "status": "success",
            "backend": "memgraph",
            "project_scope": project_scope,
            "metrics": {
                "page_vertices": page_count,
                "element_vertices": element_count,
                "entity_vertices": entity_count,
                "edges": edge_count,
            },
        }

    def _upsert_nodes(self, label: str, rows: list[Any], common: dict[str, Any]) -> int:
        count = 0
        for row in rows:
            if not isinstance(row, dict):
                continue
            node_id = str(row.get("id") or "").strip()
            if not node_id:
                continue
            props = self._node_properties(label, row, common)
            self._provider.execute_write(
                f"""
                MERGE (n:{label} {{project_scope: $project_scope, id: $id}})
                SET n += $props
                """,
                {
                    "project_scope": common["project_scope"],
                    "id": node_id,
                    "props": props,
                },
            )
            count += 1
        return count

    def _upsert_edge(
        self,
        from_label: str,
        relation: str,
        to_label: str,
        edge: dict[str, Any],
        common: dict[str, Any],
    ) -> int:
        source_id = str(edge.get("from") or "").strip()
        target_id = str(edge.get("to") or "").strip()
        if not source_id or not target_id:
            return 0
        edge_id = self._scoped_key(common["project_scope"], relation, source_id, target_id, edge.get("href") or "")
        props = self._edge_properties(edge, common, relation, edge_id)
        self._provider.execute_write(
            f"""
            MATCH (a:{from_label} {{project_scope: $project_scope, id: $source_id}})
            MATCH (b:{to_label} {{project_scope: $project_scope, id: $target_id}})
            MERGE (a)-[r:{relation} {{project_scope: $project_scope, edge_id: $edge_id}}]->(b)
            SET r += $props
            """,
            {
                "project_scope": common["project_scope"],
                "source_id": source_id,
                "target_id": target_id,
                "edge_id": edge_id,
                "props": props,
            },
        )
        return 1

    def _node_properties(self, label: str, row: dict[str, Any], common: dict[str, Any]) -> dict[str, Any]:
        scalar = self._safe_scalar_map(row)
        if label == "Page":
            scalar["label"] = str(row.get("title") or row.get("name") or row.get("url") or row.get("id") or "Page")
        elif label == "Element":
            scalar["label"] = str(row.get("name") or row.get("title") or row.get("role") or row.get("id") or "Element")
        else:
            scalar["label"] = str(row.get("name") or row.get("title") or row.get("id") or "Entity")
        scalar["kind"] = label.lower()
        scalar["payload_json"] = json.dumps(row, ensure_ascii=False)
        scalar.update(common)
        return scalar

    def _edge_properties(self, row: dict[str, Any], common: dict[str, Any], relation: str, edge_id: str) -> dict[str, Any]:
        scalar = self._safe_scalar_map(row)
        scalar["type"] = str(row.get("type") or relation.lower())
        scalar["edge_id"] = edge_id
        scalar["payload_json"] = json.dumps(row, ensure_ascii=False)
        scalar.update(common)
        return scalar

    def _safe_scalar_map(self, row: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in row.items():
            if value is None:
                continue
            if isinstance(value, (str, int, float, bool)):
                result[str(key)] = value
        return result

    def _scoped_key(self, *parts: Any) -> str:
        raw = "::".join(str(part or "") for part in parts).strip()
        if not raw:
            return ""
        digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
        label = re.sub(r"[^A-Za-z0-9_.:@()+,=;$!*'%-]+", "_", str(parts[-1] or "item")).strip("._")
        label = label[:64] or "item"
        return f"{label}_{digest}"
