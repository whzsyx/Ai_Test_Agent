from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import logging
from typing import Any

from redis import Redis
from redis.exceptions import RedisError


LOGGER = logging.getLogger(__name__)


class ChannelPairingSessionStore:
    """Persist short-lived channel pairing sessions in Redis with an in-memory fallback."""

    def __init__(
        self,
        redis_url: str,
        *,
        key_prefix: str = "qa_agent:channel_pairing",
        retention_seconds: int = 1800,
        client: Redis | None = None,
    ) -> None:
        self._redis_url = str(redis_url or "").strip()
        self._key_prefix = key_prefix.rstrip(":")
        self._retention_seconds = max(60, int(retention_seconds))
        self._client = client
        self._memory_sessions: dict[str, dict[str, Any]] = {}
        self._redis_failed = False

    def save(self, session: dict[str, Any]) -> None:
        normalized = self._normalize_for_storage(session)
        session_id = str(normalized["session_id"])
        self._memory_sessions[session_id] = dict(normalized)
        ttl = self._ttl_seconds(normalized)
        if ttl <= 0:
            return
        client = self._safe_client()
        if client is None:
            return
        try:
            client.setex(self._key(session_id), ttl, json.dumps(normalized, ensure_ascii=False))
        except RedisError as exc:
            self._mark_redis_failed(exc)

    def get(self, session_id: str) -> dict[str, Any] | None:
        client = self._safe_client()
        if client is not None:
            try:
                raw = client.get(self._key(session_id))
                if raw:
                    parsed = json.loads(raw)
                    if isinstance(parsed, dict):
                        self._memory_sessions[session_id] = parsed
                        return self._normalize_from_storage(parsed)
            except (RedisError, json.JSONDecodeError) as exc:
                self._mark_redis_failed(exc)
        session = self._memory_sessions.get(session_id)
        return self._normalize_from_storage(session) if session else None

    def latest_pending_for_domain(self, domain: str) -> dict[str, Any] | None:
        now = datetime.now(timezone.utc)
        matches = [
            session
            for session in self.list_all()
            if str(session.get("requested_domain") or session.get("domain") or "") == domain
            and session.get("status") == "pending"
            and self._parse_datetime(session.get("expires_at")) > now
        ]
        if not matches:
            return None
        matches.sort(key=lambda item: self._parse_datetime(item.get("created_at")), reverse=True)
        return matches[0]

    def list_all(self) -> list[dict[str, Any]]:
        sessions: dict[str, dict[str, Any]] = {}
        client = self._safe_client()
        if client is not None:
            try:
                for key in client.scan_iter(match=f"{self._key_prefix}:*"):
                    raw = client.get(key)
                    if not raw:
                        continue
                    parsed = json.loads(raw)
                    if isinstance(parsed, dict) and parsed.get("session_id"):
                        sessions[str(parsed["session_id"])] = parsed
            except (RedisError, json.JSONDecodeError) as exc:
                self._mark_redis_failed(exc)
        sessions.update(self._memory_sessions)
        return [self._normalize_from_storage(item) for item in sessions.values()]

    def delete(self, session_id: str) -> None:
        self._memory_sessions.pop(session_id, None)
        client = self._safe_client()
        if client is None:
            return
        try:
            client.delete(self._key(session_id))
        except RedisError as exc:
            self._mark_redis_failed(exc)

    def prune(self) -> None:
        now = datetime.now(timezone.utc)
        for session_id, session in list(self._memory_sessions.items()):
            destroy_at = self._parse_datetime(session.get("destroy_at"))
            if now >= destroy_at:
                self._memory_sessions.pop(session_id, None)

    def _safe_client(self) -> Redis | None:
        if self._redis_failed:
            return None
        if not self._redis_url and self._client is None:
            return None
        if self._client is None:
            try:
                self._client = Redis.from_url(
                    self._redis_url,
                    decode_responses=True,
                    socket_connect_timeout=3,
                    socket_timeout=3,
                )
            except RedisError as exc:
                self._mark_redis_failed(exc)
                return None
        return self._client

    def _mark_redis_failed(self, exc: Exception) -> None:
        if not self._redis_failed:
            LOGGER.warning("Channel pairing Redis store is unavailable; falling back to process memory: %s", exc)
        self._redis_failed = True

    def _key(self, session_id: str) -> str:
        return f"{self._key_prefix}:{session_id}"

    def _ttl_seconds(self, session: dict[str, Any]) -> int:
        destroy_at = self._parse_datetime(session.get("destroy_at"))
        return max(0, int((destroy_at - datetime.now(timezone.utc)).total_seconds()))

    def _normalize_for_storage(self, session: dict[str, Any]) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for key, value in session.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
            elif hasattr(value, "model_dump"):
                data[key] = value.model_dump(mode="json")
            else:
                data[key] = value
        expires_at = self._parse_datetime(data.get("expires_at"))
        data["expires_at"] = expires_at.isoformat()
        data["destroy_at"] = self._parse_datetime(
            data.get("destroy_at"),
            default=expires_at + timedelta(seconds=self._retention_seconds),
        ).isoformat()
        data["created_at"] = self._parse_datetime(
            data.get("created_at"),
            default=datetime.now(timezone.utc),
        ).isoformat()
        return data

    def _normalize_from_storage(self, session: dict[str, Any]) -> dict[str, Any]:
        data = dict(session)
        expires_at = self._parse_datetime(data.get("expires_at"))
        for key in ("created_at", "expires_at", "destroy_at", "confirmed_at"):
            value = data.get(key)
            if value:
                data[key] = self._parse_datetime(value)
            elif key == "destroy_at":
                data[key] = expires_at + timedelta(seconds=self._retention_seconds)
            elif key == "confirmed_at":
                data[key] = None
        return data

    @staticmethod
    def _parse_datetime(value: Any, *, default: datetime | None = None) -> datetime:
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str) and value.strip():
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        elif default is not None:
            parsed = default
        else:
            parsed = datetime.now(timezone.utc)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
