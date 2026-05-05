from __future__ import annotations

from io import BytesIO
import mimetypes
from copy import deepcopy
from pathlib import Path, PurePosixPath
from typing import Any

from src.core.config import Settings


class ArtifactStorageService:
    """Uploads tool artifacts to the configured object storage backend."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._artifact_root = (Path(__file__).resolve().parents[2] / settings.artifact_root_dir).resolve()

    @property
    def enabled(self) -> bool:
        return self._settings.artifact_storage_backend.lower() == "minio"

    async def store_output_artifacts(
        self,
        output: dict[str, Any],
        *,
        session_id: str,
        turn_id: str,
        tool_key: str,
    ) -> dict[str, Any]:
        if not self.enabled:
            return output
        cache: dict[str, dict[str, Any]] = {}
        normalized = deepcopy(output)
        return self._rewrite_artifact_paths(
            normalized,
            session_id=session_id,
            turn_id=turn_id,
            tool_key=tool_key,
            cache=cache,
        )

    async def store_uploaded_bytes(
        self,
        *,
        content: bytes,
        filename: str,
        object_prefix: str,
        content_type: str | None = None,
        bucket_name: str | None = None,
        object_name: str | None = None,
    ) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("Artifact storage backend is not enabled.")

        target_bucket = bucket_name or self._settings.minio_bucket
        resolved_object_name = (
            self._safe_object_name(object_name)
            if object_name
            else self._build_uploaded_object_name(object_prefix=object_prefix, filename=filename)
        )
        resolved_content_type = content_type or self._content_type(Path(filename))
        client = self._minio_client()
        self._ensure_bucket(client, target_bucket)
        buffer = BytesIO(content)
        client.put_object(
            target_bucket,
            resolved_object_name,
            buffer,
            length=len(content),
            content_type=resolved_content_type,
        )
        minio_uri = f"minio://{target_bucket}/{resolved_object_name}"
        return {
            "path": minio_uri,
            "uri": minio_uri,
            "storage_backend": "minio",
            "bucket": target_bucket,
            "object_name": resolved_object_name,
            "content_type": resolved_content_type,
            "original_filename": filename,
            "size_bytes": len(content),
        }

    async def delete_object_uri(self, uri: str) -> None:
        if not self.enabled or not uri.startswith("minio://"):
            return
        bucket, object_name = self._parse_minio_uri(uri)
        client = self._minio_client()
        if not client.bucket_exists(bucket):
            return
        client.remove_object(bucket, object_name)

    async def read_object_uri(self, uri: str) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("Artifact storage backend is not enabled.")
        if not uri.startswith("minio://"):
            raise ValueError(f"Unsupported artifact URI: {uri}")

        bucket, object_name = self._parse_minio_uri(uri)
        client = self._minio_client()
        response = client.get_object(bucket, object_name)
        try:
            content = response.read()
            stat = client.stat_object(bucket, object_name)
        finally:
            response.close()
            response.release_conn()

        return {
            "uri": uri,
            "bucket": bucket,
            "object_name": object_name,
            "content": content,
            "content_type": getattr(stat, "content_type", None) or self._content_type(Path(object_name)),
            "size_bytes": getattr(stat, "size", len(content)),
            "etag": getattr(stat, "etag", ""),
        }

    async def copy_object_uri(
        self,
        uri: str,
        *,
        bucket_name: str,
        object_name: str,
    ) -> dict[str, Any]:
        source = await self.read_object_uri(uri)
        return await self.store_uploaded_bytes(
            content=source["content"],
            filename=Path(source["object_name"]).name,
            object_prefix="",
            content_type=str(source.get("content_type") or "application/octet-stream"),
            bucket_name=bucket_name,
            object_name=object_name,
        )

    async def move_object_uri(
        self,
        uri: str,
        *,
        bucket_name: str,
        object_name: str,
    ) -> dict[str, Any]:
        copied = await self.copy_object_uri(
            uri,
            bucket_name=bucket_name,
            object_name=object_name,
        )
        await self.delete_object_uri(uri)
        return copied

    def _rewrite_artifact_paths(
        self,
        value: Any,
        *,
        session_id: str,
        turn_id: str,
        tool_key: str,
        cache: dict[str, dict[str, Any]],
    ) -> Any:
        if isinstance(value, list):
            for index, item in enumerate(value):
                value[index] = self._rewrite_artifact_paths(
                    item,
                    session_id=session_id,
                    turn_id=turn_id,
                    tool_key=tool_key,
                    cache=cache,
                )
            return value

        if not isinstance(value, dict):
            return value

        cached = self._cached_artifact(value, cache)
        if cached is not None:
            value.update(cached)
        elif self._is_file_artifact(value):
            stored = self._store_artifact_dict(
                value,
                session_id=session_id,
                turn_id=turn_id,
                tool_key=tool_key,
                cache=cache,
            )
            value.update(stored)

        for key, item in list(value.items()):
            if key == "path" and self._is_file_artifact(value):
                continue
            value[key] = self._rewrite_artifact_paths(
                item,
                session_id=session_id,
                turn_id=turn_id,
                tool_key=tool_key,
                cache=cache,
            )
        return value

    def _cached_artifact(self, value: dict[str, Any], cache: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
        raw_path = str(value.get("path") or "").strip()
        if not raw_path or "://" in raw_path:
            return None
        try:
            return cache.get(str(Path(raw_path).resolve()))
        except (OSError, ValueError):
            return None

    def _is_file_artifact(self, value: dict[str, Any]) -> bool:
        raw_path = str(value.get("path") or "").strip()
        if not raw_path or "://" in raw_path:
            return False
        try:
            path = Path(raw_path)
        except (OSError, ValueError):
            return False
        return path.exists() and path.is_file()

    def _store_artifact_dict(
        self,
        artifact: dict[str, Any],
        *,
        session_id: str,
        turn_id: str,
        tool_key: str,
        cache: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        local_path = Path(str(artifact.get("path") or "")).resolve()
        cache_key = str(local_path)
        if cache_key in cache:
            return cache[cache_key]

        object_name = self._object_name(
            local_path,
            session_id=session_id,
            turn_id=turn_id,
            tool_key=tool_key,
        )
        content_type = self._content_type(local_path)
        client = self._minio_client()
        self._ensure_bucket(client, self._settings.minio_bucket)
        client.fput_object(
            self._settings.minio_bucket,
            object_name,
            str(local_path),
            content_type=content_type,
        )

        minio_uri = f"minio://{self._settings.minio_bucket}/{object_name}"
        stored = {
            "path": minio_uri,
            "uri": minio_uri,
            "storage_backend": "minio",
            "bucket": self._settings.minio_bucket,
            "object_name": object_name,
            "content_type": content_type,
            "original_local_path": str(local_path),
        }
        cache[cache_key] = stored

        if not self._settings.artifact_keep_local_copy:
            self._remove_local_file(local_path)

        return stored

    def _object_name(self, local_path: Path, *, session_id: str, turn_id: str, tool_key: str) -> str:
        try:
            relative = local_path.relative_to(self._artifact_root)
            return self._normalize_object_name(relative)
        except ValueError:
            safe_tool = self._safe_segment(tool_key or "tool")
            safe_session = self._safe_segment(session_id or "session")
            safe_turn = self._safe_segment(turn_id or "turn")
            return f"{safe_session}/{safe_turn}/{safe_tool}/{local_path.name}"

    def _normalize_object_name(self, relative: Path) -> str:
        return "/".join(self._safe_segment(part) for part in relative.parts if part)

    def _build_uploaded_object_name(self, *, object_prefix: str, filename: str) -> str:
        safe_prefix = "/".join(self._safe_segment(part) for part in object_prefix.split("/") if part.strip())
        safe_name = self._safe_segment(filename or "upload.bin")
        return f"{safe_prefix}/{safe_name}" if safe_prefix else safe_name

    def _safe_object_name(self, value: str) -> str:
        return "/".join(
            self._safe_segment(part)
            for part in PurePosixPath(str(value)).parts
            if part not in {"", ".", "/"}
        )

    def _safe_segment(self, value: str) -> str:
        normalized = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in str(value))
        return normalized.strip("._") or "artifact"

    def _content_type(self, path: Path) -> str:
        guessed, _ = mimetypes.guess_type(str(path))
        return guessed or "application/octet-stream"

    def _minio_client(self):
        try:
            from minio import Minio
        except ImportError as exc:
            raise RuntimeError("MinIO artifact storage requires the 'minio' Python package.") from exc
        return Minio(
            self._settings.minio_endpoint,
            access_key=self._settings.minio_access_key,
            secret_key=self._settings.minio_secret_key,
            secure=self._settings.minio_secure,
        )

    def _ensure_bucket(self, client: Any, bucket_name: str) -> None:
        if client.bucket_exists(bucket_name):
            return
        client.make_bucket(bucket_name)

    def _remove_local_file(self, path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            return

    def _parse_minio_uri(self, uri: str) -> tuple[str, str]:
        raw = uri.removeprefix("minio://")
        bucket, _, object_name = raw.partition("/")
        if not bucket or not object_name:
            raise ValueError(f"Invalid MinIO URI: {uri}")
        return bucket, object_name
