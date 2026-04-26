from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel


SHANGHAI_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")
UTC = timezone.utc


def ensure_utc_datetime(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(UTC).replace(tzinfo=None)
        return value
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is not None:
        return parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def serialize_datetime(value: datetime | str | None) -> str | None:
    normalized = ensure_utc_datetime(value)
    return normalized.isoformat() if normalized is not None else None


def make_json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, datetime):
        return serialize_datetime(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, BaseModel):
        return make_json_safe(value.model_dump(mode="python"))
    if isinstance(value, dict):
        return {str(key): make_json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [make_json_safe(item) for item in value]
    return value


def day_bucket(value: datetime | str | None) -> str:
    normalized = ensure_utc_datetime(value) or datetime.utcnow()
    local_time = normalized.replace(tzinfo=UTC).astimezone(SHANGHAI_TZ)
    return local_time.strftime("%Y-%m-%d")


def recent_day_buckets(days: int) -> list[str]:
    now = datetime.utcnow().replace(tzinfo=UTC).astimezone(SHANGHAI_TZ)
    return [
        (now - timedelta(days=offset)).strftime("%Y-%m-%d")
        for offset in range(max(days, 1))
    ]
