from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

from src.application.context.mcp_runtime_service import MCPRuntimeService
from src.core.config import Settings

if TYPE_CHECKING:
    from src.application.runtime.tool_runtime_service import ToolExecutionContext


class UIExplorationService:
    """Explore a UI entry page and persist an app-map style model."""

    def __init__(self, settings: Settings, mcp_runtime_service: MCPRuntimeService) -> None:
        self._settings = settings
        self._mcp_runtime_service = mcp_runtime_service
        self._artifact_root = Path(__file__).resolve().parents[2] / settings.artifact_root_dir

    async def explore(self, arguments: dict[str, Any], context: ToolExecutionContext) -> dict[str, Any]:
        target_url = str(arguments.get("target_url") or arguments.get("url") or "").strip()
        if not target_url:
            return {"status": "failed", "error": "ui-page-explorer requires target_url or url."}

        max_pages = int(arguments.get("max_pages") or 1)
        max_pages = max(1, min(max_pages, 8))
        same_origin_only = bool(arguments.get("same_origin_only", True))

        queue = [target_url]
        visited: set[str] = set()
        pages: list[dict[str, Any]] = []
        artifacts: list[dict[str, Any]] = []

        while queue and len(visited) < max_pages:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)
            result = await self._mcp_runtime_service.call(
                "browser-mcp",
                "inspect-page",
                {"target_url": url},
                {
                    "session_id": context.session_id,
                    "turn_id": context.turn_id,
                    "trace_id": context.trace_id,
                    "user_message": context.user_message,
                    "context_bundle": context.context_bundle,
                },
            )
            if result.get("status") != "success":
                pages.append({"url": url, "status": "failed", "error": result.get("error") or result.get("summary")})
                continue
            page_links = [item for item in result.get("links", []) if isinstance(item, str)]
            pages.append(
                {
                    "url": url,
                    "status": "explored",
                    "title": result.get("title", ""),
                    "current_url": result.get("current_url", url),
                    "dom_summary": result.get("dom_summary", {}),
                    "links": page_links[:20],
                    "artifacts": result.get("artifacts", []),
                }
            )
            artifacts.extend(result.get("artifacts", []))
            for link in page_links:
                if len(visited) + len(queue) >= max_pages:
                    break
                if same_origin_only and not self._same_origin(target_url, link):
                    continue
                if link not in visited and link not in queue:
                    queue.append(link)

        app_map = {
            "entry_url": target_url,
            "page_count": len(pages),
            "same_origin_only": same_origin_only,
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "pages": pages,
        }
        output_dir = self._artifact_root / self._slug(context.session_id) / self._slug(context.turn_id) / "ui-page-explorer"
        output_dir.mkdir(parents=True, exist_ok=True)
        app_map_path = output_dir / "app_map.json"
        app_map_path.write_text(json.dumps(app_map, ensure_ascii=False, indent=2), encoding="utf-8")
        artifacts.append({"type": "app-map", "path": str(app_map_path)})
        return {
            "status": "success",
            "summary": f"Explored {len(pages)} UI page(s) starting from {target_url}.",
            "entry_url": target_url,
            "app_map": app_map,
            "artifacts": artifacts,
        }

    def _same_origin(self, base_url: str, link: str) -> bool:
        base = urlparse(base_url)
        other = urlparse(link)
        return (base.scheme, base.netloc) == (other.scheme, other.netloc)

    def _slug(self, value: str) -> str:
        return "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in value).strip("-") or "item"
