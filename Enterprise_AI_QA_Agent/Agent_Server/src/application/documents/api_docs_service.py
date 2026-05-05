from __future__ import annotations

import asyncio
import base64
import json
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from src.application.artifacts.artifact_storage_service import ArtifactStorageService
from src.application.security.upload_security_service import UploadSecurityService
from src.core.config import Settings
from src.schemas.api_docs import ApiDocRecord, UploadedAttachmentRecord


class ApiDocsService:
    def __init__(
        self,
        *,
        settings: Settings,
        artifact_storage_service: ArtifactStorageService,
        upload_security_service: UploadSecurityService | None = None,
    ) -> None:
        self._settings = settings
        self._artifact_storage_service = artifact_storage_service
        self._upload_security_service = upload_security_service
        self._data_dir = (Path(__file__).resolve().parents[2] / settings.data_dir / "api_docs").resolve()
        self._catalog_path = self._data_dir / "catalog.json"
        self._lock = asyncio.Lock()
        self._data_dir.mkdir(parents=True, exist_ok=True)

    async def list_documents(self) -> list[ApiDocRecord]:
        async with self._lock:
            catalog = self._load_catalog()
        items = [ApiDocRecord.model_validate(item) for item in catalog]
        return sorted(items, key=lambda item: item.updated_at, reverse=True)

    async def get_document(self, doc_id: str) -> ApiDocRecord:
        async with self._lock:
            catalog = self._load_catalog()
            item = self._find_item(catalog, doc_id)
        return ApiDocRecord.model_validate(item)

    async def upload_document(
        self,
        *,
        filename: str,
        content_base64: str,
        source: str = "manual_upload",
        title: str | None = None,
    ) -> ApiDocRecord:
        content = self._decode_base64(content_base64)
        declared_content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        preview_text, preview_truncated, preview_error = self._build_preview(filename, content, declared_content_type)
        format_label, endpoint_count = self._detect_format(filename, content, preview_text)
        doc_id = str(uuid4())
        now = datetime.now(timezone.utc)
        storage_result = await self._store_upload(
            content=content,
            filename=filename,
            object_prefix=f"api-docs/{doc_id}",
            profile="api_document",
            source=source,
            content_type=declared_content_type,
        )
        content_type = str(storage_result.get("content_type") or declared_content_type)

        record = ApiDocRecord(
            id=doc_id,
            title=(title or Path(filename).stem or filename).strip(),
            filename=filename,
            source=source,
            format_label=format_label,
            content_type=content_type,
            size_bytes=len(content),
            storage_uri=str(storage_result["uri"]),
            bucket=str(storage_result.get("bucket") or ""),
            object_name=str(storage_result.get("object_name") or ""),
            endpoint_count=endpoint_count,
            preview_available=preview_text is not None,
            preview_truncated=preview_truncated,
            preview_text=preview_text,
            preview_error=preview_error,
            uploaded_at=now,
            updated_at=now,
            metadata={
                "original_filename": filename,
                "storage_backend": storage_result.get("storage_backend", "minio"),
                "size_bytes": len(content),
                "security": storage_result.get("security_report"),
            },
        )

        async with self._lock:
            catalog = self._load_catalog()
            catalog.append(record.model_dump(mode="json"))
            self._save_catalog(catalog)
        return record

    async def upload_attachment(
        self,
        *,
        filename: str,
        content_base64: str,
        source: str = "chat_attachment",
    ) -> UploadedAttachmentRecord:
        content = self._decode_base64(content_base64)
        declared_content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        preview_text, preview_truncated, preview_error = self._build_preview(filename, content, declared_content_type)
        attachment_id = str(uuid4())
        now = datetime.now(timezone.utc)
        storage_result = await self._store_upload(
            content=content,
            filename=filename,
            object_prefix=f"attachments/{attachment_id}",
            profile="chat_attachment",
            source=source,
            content_type=declared_content_type,
        )
        content_type = str(storage_result.get("content_type") or declared_content_type)
        return UploadedAttachmentRecord(
            id=attachment_id,
            filename=filename,
            content_type=content_type,
            size_bytes=len(content),
            storage_uri=str(storage_result["uri"]),
            preview_text=preview_text,
            preview_truncated=preview_truncated,
            preview_error=preview_error,
            uploaded_at=now,
            metadata={
                "source": source,
                "storage_backend": storage_result.get("storage_backend", "minio"),
                "bucket": storage_result.get("bucket", ""),
                "object_name": storage_result.get("object_name", ""),
                "security": storage_result.get("security_report"),
            },
        )

    async def delete_document(self, doc_id: str) -> dict[str, Any]:
        async with self._lock:
            catalog = self._load_catalog()
            item = self._find_item(catalog, doc_id)
            catalog = [entry for entry in catalog if str(entry.get("id") or "") != doc_id]
            self._save_catalog(catalog)

        uri = str(item.get("storage_uri") or "")
        if uri:
            try:
                await self._artifact_storage_service.delete_object_uri(uri)
            except Exception:
                pass
        return {"ok": True, "deleted_id": doc_id}

    async def _store_upload(
        self,
        *,
        content: bytes,
        filename: str,
        object_prefix: str,
        profile: str,
        source: str,
        content_type: str,
    ) -> dict[str, Any]:
        if self._upload_security_service is not None:
            return await self._upload_security_service.secure_store_upload(
                content=content,
                filename=filename,
                object_prefix=object_prefix,
                profile=profile,
                source=source,
                content_type=content_type,
            )
        return await self._artifact_storage_service.store_uploaded_bytes(
            content=content,
            filename=filename,
            object_prefix=object_prefix,
            content_type=content_type,
        )

    def _decode_base64(self, value: str) -> bytes:
        try:
            return base64.b64decode(value, validate=True)
        except Exception as exc:
            raise ValueError("上传文件内容不是有效的 Base64 数据。") from exc

    def _build_preview(self, filename: str, content: bytes, content_type: str) -> tuple[str | None, bool, str | None]:
        is_text_like = content_type.startswith("text/") or Path(filename).suffix.lower() in {
            ".json",
            ".yaml",
            ".yml",
            ".txt",
            ".md",
            ".csv",
            ".xml",
            ".html",
            ".js",
            ".ts",
        }
        if not is_text_like:
            return None, False, "该文件不是文本类型，暂不支持内容预览。"

        decoded: str | None = None
        for encoding in ("utf-8", "utf-8-sig", "gb18030", "latin-1"):
            try:
                decoded = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if decoded is None:
            return None, False, "文件内容无法按常见文本编码解析。"

        limit = 20000
        truncated = len(decoded) > limit
        return decoded[:limit], truncated, None

    def _detect_format(self, filename: str, content: bytes, preview_text: str | None) -> tuple[str, int | None]:
        suffix = Path(filename).suffix.lower()
        if suffix in {".yaml", ".yml"}:
            if preview_text and ("openapi:" in preview_text.lower() or "swagger:" in preview_text.lower()):
                return "OpenAPI / Swagger", self._count_yaml_paths(preview_text)
            return "YAML 文档", None

        if suffix == ".json":
            try:
                parsed = json.loads(content.decode("utf-8"))
            except Exception:
                return "JSON 文档", None
            if isinstance(parsed, dict) and ("openapi" in parsed or "swagger" in parsed):
                return "OpenAPI / Swagger", self._count_openapi_paths(parsed)
            if isinstance(parsed, dict) and "item" in parsed and "info" in parsed:
                return "Postman Collection", self._count_postman_requests(parsed.get("item"))
            return "JSON 文档", None

        if suffix == ".md":
            return "Markdown 文档", None
        if suffix in {".txt", ".log"}:
            return "文本文件", None
        return "其他文档", None

    def _count_openapi_paths(self, payload: dict[str, Any]) -> int | None:
        paths = payload.get("paths")
        if not isinstance(paths, dict):
            return None
        count = 0
        for methods in paths.values():
            if isinstance(methods, dict):
                count += sum(1 for key in methods.keys() if str(key).lower() in {"get", "post", "put", "delete", "patch", "head", "options"})
        return count or len(paths)

    def _count_postman_requests(self, items: Any) -> int | None:
        if not isinstance(items, list):
            return None
        count = 0
        stack = list(items)
        while stack:
            item = stack.pop()
            if not isinstance(item, dict):
                continue
            if "request" in item:
                count += 1
            nested = item.get("item")
            if isinstance(nested, list):
                stack.extend(nested)
        return count or None

    def _count_yaml_paths(self, content: str) -> int | None:
        count = 0
        in_paths = False
        for line in content.splitlines():
            if line.strip().lower().startswith("paths:"):
                in_paths = True
                continue
            if in_paths:
                if line and not line.startswith((" ", "\t")):
                    break
                stripped = line.strip()
                if stripped.startswith("/") and stripped.endswith(":"):
                    count += 1
        return count or None

    def _load_catalog(self) -> list[dict[str, Any]]:
        if not self._catalog_path.exists():
            return []
        try:
            raw = json.loads(self._catalog_path.read_text(encoding="utf-8"))
        except Exception:
            return []
        return raw if isinstance(raw, list) else []

    def _save_catalog(self, catalog: list[dict[str, Any]]) -> None:
        self._catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")

    def _find_item(self, catalog: list[dict[str, Any]], doc_id: str) -> dict[str, Any]:
        for item in catalog:
            if str(item.get("id") or "") == doc_id:
                return item
        raise ValueError(f"未找到 API 文档：{doc_id}")
