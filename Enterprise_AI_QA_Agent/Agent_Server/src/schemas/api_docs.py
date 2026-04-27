from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ApiDocRecord(BaseModel):
    id: str
    title: str
    filename: str
    source: str = "manual_upload"
    format_label: str = "其他文档"
    content_type: str = "application/octet-stream"
    size_bytes: int = 0
    storage_uri: str
    bucket: str | None = None
    object_name: str | None = None
    endpoint_count: int | None = None
    preview_available: bool = False
    preview_truncated: bool = False
    preview_text: str | None = None
    preview_error: str | None = None
    uploaded_at: datetime
    updated_at: datetime
    metadata: dict[str, object] = Field(default_factory=dict)


class ApiDocUploadRequest(BaseModel):
    filename: str
    content_base64: str
    source: str = "manual_upload"
    title: str | None = None

