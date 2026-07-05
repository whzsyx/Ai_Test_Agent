from __future__ import annotations
import json

from src.schemas.session import ExecutionEvent


def format_sse(event: ExecutionEvent) -> str:
    event_id = str(event.id or "").replace("\r", "").replace("\n", "")
    payload = json.dumps(event.model_dump(mode="json"), ensure_ascii=False)
    return f"id: {event_id}\ndata: {payload}\n\n"

