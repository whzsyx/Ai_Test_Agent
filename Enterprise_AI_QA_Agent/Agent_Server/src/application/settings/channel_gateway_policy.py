from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import secrets
import string
import threading
from typing import Callable

from src.schemas.channel_config import (
    ChannelAdvancedSettings,
    ChannelGatewayDecision,
    ChannelGatewayQueueDecision,
    ChannelGatewayRouteDecision,
    ChannelGatewaySessionReleaseResponse,
    ChannelInboundMessage,
    ChannelPairingRequestPublic,
)


_PAIRING_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_SLASH_BYPASS_COMMANDS = {
    "/stop",
    "/new",
    "/reset",
    "/approve",
    "/deny",
    "/answer",
    "/yolo",
    "/mode",
    "/queue",
    "/projects",
    "/use",
    "/sessions",
    "/attach",
    "/search",
    "/desktop",
    "/status",
    "/help",
}


@dataclass
class _PendingTurn:
    message: ChannelInboundMessage
    timestamp: datetime
    mode: str


class ChannelGatewayPolicyService:
    def __init__(
        self,
        settings_loader: Callable[[], ChannelAdvancedSettings],
        settings_saver: Callable[[ChannelAdvancedSettings], ChannelAdvancedSettings],
        pairing_store_path: Path,
    ) -> None:
        self._settings_loader = settings_loader
        self._settings_saver = settings_saver
        self._pairing_store_path = pairing_store_path
        self._lock = threading.RLock()
        self._active: dict[str, bool] = {}
        self._pending: dict[str, list[_PendingTurn]] = {}
        self._dropped: dict[str, list[str]] = {}

    def evaluate_inbound(self, message: ChannelInboundMessage) -> ChannelGatewayDecision:
        settings = self._settings_loader()
        platform_key = _platform_key(message.platform)
        actor = _actor_id(message)
        route = self._route_for(settings, message)
        base = {
            "max_steps": settings.max_steps,
            "debounce_ms": settings.debounce_ms,
            "route": route,
            "is_admin": actor in _role_set(settings, platform_key, "admins"),
            "is_approver": actor in _role_set(settings, platform_key, "approvers"),
        }

        if self._is_self_message(settings, message, platform_key):
            return ChannelGatewayDecision(
                allowed=False,
                action="ignore",
                reason="self_message",
                message="Ignored self message.",
                **base,
            )

        if not self._allowed(settings, message, platform_key):
            pairing = self._create_or_refresh_pairing(settings, message)
            if pairing:
                return ChannelGatewayDecision(
                    allowed=False,
                    action="pairing_required",
                    reason="pairing_required",
                    message=f"Pairing code: {pairing.code}",
                    pairing=pairing,
                    **base,
                )
            return ChannelGatewayDecision(
                allowed=False,
                action="reject",
                reason="not_allowed",
                message="User is not allowed to use this communication channel.",
                **base,
            )

        session_key = build_channel_session_key(message)
        if not message.claim_session:
            return ChannelGatewayDecision(
                allowed=True,
                action="dispatch",
                reason="admitted",
                message="Message admitted.",
                queue=self._queue_decision(session_key, settings, active=False, queued=False, pending=0),
                **base,
            )

        queue = self._acquire_or_queue(session_key, message, settings)
        if queue.rejected:
            action = "reject"
            reason = "queue_full"
            text = "Queue is full; new message rejected."
        elif queue.queued and queue.mode == "interrupt":
            action = "interrupt"
            reason = "interrupt_active_session"
            text = "Active session should be interrupted; message queued as replacement."
        elif queue.queued:
            action = "queued"
            reason = "session_busy"
            text = "Active session is busy; message queued."
        elif queue.mode == "steer" and queue.active:
            action = "steer"
            reason = "session_active"
            text = "Message should steer the active session."
        else:
            action = "dispatch"
            reason = "admitted"
            text = "Message admitted."

        return ChannelGatewayDecision(
            allowed=not queue.rejected,
            action=action,
            reason=reason,
            message=text,
            queue=queue,
            **base,
        )

    def approve_pairing(self, code: str, approve: bool) -> ChannelPairingRequestPublic:
        normalized = str(code or "").strip().upper()
        with self._lock:
            requests = self._load_pairing_requests_locked(prune=True)
            match = next((item for item in requests if item.code == normalized), None)
            if not match:
                raise KeyError(normalized)
            requests = [item for item in requests if item.code != normalized]
            self._save_pairing_requests_locked(requests)
        if approve:
            self._approve_pairing_request(match)
        return match

    def list_pairing_requests(self) -> list[ChannelPairingRequestPublic]:
        with self._lock:
            return self._load_pairing_requests_locked(prune=True)

    def release_session(self, session_key: str) -> ChannelGatewaySessionReleaseResponse:
        with self._lock:
            queue = self._pending.get(session_key) or []
            dropped = self._dropped.pop(session_key, [])
            if queue:
                mode = _normalize_queue_mode(queue[0].mode)
                if mode == "followup":
                    next_message = queue.pop(0).message
                    if queue:
                        self._pending[session_key] = queue
                    else:
                        self._pending.pop(session_key, None)
                else:
                    next_message = _merge_pending_turns(queue)
                    self._pending.pop(session_key, None)
                next_message.text = _with_dropped_prefix(next_message.text, dropped)
                self._active[session_key] = True
                return ChannelGatewaySessionReleaseResponse(
                    session_key=session_key,
                    active=True,
                    next_message=next_message,
                    pending=len(queue),
                    dropped_summaries=dropped,
                )
            self._active.pop(session_key, None)
            self._pending.pop(session_key, None)
            return ChannelGatewaySessionReleaseResponse(
                session_key=session_key,
                active=False,
                next_message=None,
                pending=0,
                dropped_summaries=dropped,
            )

    def _acquire_or_queue(
        self,
        session_key: str,
        message: ChannelInboundMessage,
        settings: ChannelAdvancedSettings,
    ) -> ChannelGatewayQueueDecision:
        mode = _normalize_queue_mode(settings.queue_mode)
        cap = settings.queue_cap if settings.queue_cap > 0 else 20
        drop = _normalize_queue_drop(settings.queue_drop)
        with self._lock:
            active = self._active.get(session_key, False)
            if not active:
                self._active[session_key] = True
                return self._queue_decision(session_key, settings, active=False, queued=False, pending=0)

            if _is_slash_bypass(message.text):
                return self._queue_decision(session_key, settings, active=True, queued=False, pending=len(self._pending.get(session_key, [])))

            if mode == "steer":
                return self._queue_decision(session_key, settings, active=True, queued=False, pending=len(self._pending.get(session_key, [])))

            queue = list(self._pending.get(session_key, []))
            now = datetime.now(timezone.utc)
            if mode == "interrupt":
                self._pending[session_key] = [_PendingTurn(message=message, timestamp=now, mode="followup")]
                self._dropped.pop(session_key, None)
                return self._queue_decision(session_key, settings, active=True, queued=True, pending=1)

            if len(queue) >= cap:
                if drop == "new":
                    return self._queue_decision(
                        session_key,
                        settings,
                        active=True,
                        queued=False,
                        rejected=True,
                        pending=len(queue),
                    )
                removed = queue.pop(0)
                if drop == "summarize":
                    self._dropped.setdefault(session_key, []).append(_queue_summary(removed.message.text))

            if mode == "collect" and queue and message.text:
                last = queue[-1]
                debounce_seconds = max(settings.debounce_ms, 0) / 1000
                if (now - last.timestamp).total_seconds() < debounce_seconds:
                    if last.message.text:
                        last.message.text = f"{last.message.text}\n{message.text}"
                    else:
                        last.message.text = message.text
                    last.timestamp = now
                    last.mode = mode
                    queue[-1] = last
                    self._pending[session_key] = queue
                    return self._queue_decision(session_key, settings, active=True, queued=True, dropped=bool(self._dropped.get(session_key)), pending=len(queue))

            queue.append(_PendingTurn(message=message, timestamp=now, mode=mode))
            self._pending[session_key] = queue
            return self._queue_decision(session_key, settings, active=True, queued=True, dropped=bool(self._dropped.get(session_key)), pending=len(queue))

    @staticmethod
    def _queue_decision(
        session_key: str,
        settings: ChannelAdvancedSettings,
        *,
        active: bool,
        queued: bool,
        rejected: bool = False,
        dropped: bool = False,
        pending: int,
    ) -> ChannelGatewayQueueDecision:
        return ChannelGatewayQueueDecision(
            session_key=session_key,
            mode=_normalize_queue_mode(settings.queue_mode),
            cap=settings.queue_cap if settings.queue_cap > 0 else 20,
            drop=_normalize_queue_drop(settings.queue_drop),
            active=active,
            queued=queued,
            rejected=rejected,
            dropped=dropped,
            pending=pending,
        )

    def _allowed(self, settings: ChannelAdvancedSettings, message: ChannelInboundMessage, platform_key: str) -> bool:
        allowlist = settings.allowlist
        if allowlist.allow_all:
            return True
        if not allowlist.enabled:
            return False
        actor = _actor_id(message)
        users = _role_set(settings, platform_key, "users")
        users.update(_role_set(settings, platform_key, "admins"))
        users.update(_role_set(settings, platform_key, "approvers"))
        groups = set(getattr(allowlist, f"{platform_key}_groups", []))
        actor_allowed = actor in users
        if _chat_uses_group_allowlist(message.chat_type) and groups:
            return actor_allowed and message.chat_id in groups
        return actor_allowed

    def _is_self_message(self, settings: ChannelAdvancedSettings, message: ChannelInboundMessage, platform_key: str) -> bool:
        if not settings.ignore_self_messages:
            return False
        if message.is_from_self:
            return True
        return message.user_id in set(getattr(settings.self_user_ids, platform_key, []))

    def _route_for(self, settings: ChannelAdvancedSettings, message: ChannelInboundMessage) -> ChannelGatewayRouteDecision:
        for route in settings.routes:
            if _route_matches(route, message):
                return ChannelGatewayRouteDecision(
                    connection_id=route.connection_id,
                    platform=route.platform,
                    chat_type=route.chat_type,
                    chat_id=route.chat_id,
                    user_id=route.user_id,
                    thread_id=route.thread_id,
                    workspace_root=route.workspace_root,
                    model=route.model,
                    tool_approval_mode="" if route.tool_approval_mode == "inherit" else route.tool_approval_mode,
                )
        return ChannelGatewayRouteDecision()

    def _create_or_refresh_pairing(
        self,
        settings: ChannelAdvancedSettings,
        message: ChannelInboundMessage,
    ) -> ChannelPairingRequestPublic | None:
        if not settings.pairing.enabled or message.chat_type not in {"dm", "direct"}:
            return None
        if not message.user_id or not message.chat_id:
            return None
        with self._lock:
            requests = self._load_pairing_requests_locked(prune=True)
            for request in requests:
                if _pairing_matches(request, message):
                    self._save_pairing_requests_locked(requests)
                    return request
            pending_for_platform = sum(
                1
                for request in requests
                if _platform_key(request.platform) == _platform_key(message.platform)
                and request.connection_id == message.connection_id
            )
            max_pending = settings.pairing.max_pending_per_platform or 3
            if pending_for_platform >= max_pending:
                return None
            now = datetime.now(timezone.utc)
            ttl = max(settings.pairing.request_ttl_minutes, 1)
            request = ChannelPairingRequestPublic(
                code=_new_pairing_code(),
                platform=str(message.platform),
                connection_id=message.connection_id,
                domain=str(message.domain or message.platform),
                chat_type=message.chat_type,
                chat_id=message.chat_id,
                user_id=message.user_id,
                user_name=message.user_name,
                created_at=now,
                expires_at=now + timedelta(minutes=ttl),
            )
            requests.append(request)
            self._save_pairing_requests_locked(requests)
            return request

    def _approve_pairing_request(self, request: ChannelPairingRequestPublic) -> None:
        settings = self._settings_loader()
        platform_key = _platform_key(request.platform)
        if not settings.allowlist.enabled:
            settings.allowlist.enabled = True
        target = getattr(settings.allowlist, f"{platform_key}_users")
        if request.user_id not in target:
            target.append(request.user_id)
        admins = getattr(settings.allowlist, f"{platform_key}_admins")
        approvers = getattr(settings.allowlist, f"{platform_key}_approvers")
        if not any(
            getattr(settings.allowlist, f"{key}_admins") or getattr(settings.allowlist, f"{key}_approvers")
            for key in ("qq", "feishu", "weixin")
        ):
            admins.append(request.user_id)
            approvers.append(request.user_id)
        self._settings_saver(settings)

    def _load_pairing_requests_locked(self, *, prune: bool) -> list[ChannelPairingRequestPublic]:
        if not self._pairing_store_path.exists():
            return []
        try:
            data = json.loads(self._pairing_store_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        raw_items = data.get("requests") if isinstance(data, dict) else []
        requests: list[ChannelPairingRequestPublic] = []
        for item in raw_items or []:
            try:
                requests.append(ChannelPairingRequestPublic.model_validate(item))
            except Exception:
                continue
        if prune:
            now = datetime.now(timezone.utc)
            requests = [item for item in requests if item.expires_at > now]
            self._save_pairing_requests_locked(requests)
        return requests

    def _save_pairing_requests_locked(self, requests: list[ChannelPairingRequestPublic]) -> None:
        self._pairing_store_path.parent.mkdir(parents=True, exist_ok=True)
        self._pairing_store_path.write_text(
            json.dumps(
                {"requests": [item.model_dump(mode="json") for item in requests]},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )


def build_channel_session_key(message: ChannelInboundMessage) -> str:
    source = message.connection_id or (f"{message.platform}:{message.domain}" if message.domain else str(message.platform))
    if message.chat_type == "dm":
        scope = f"{source}:dm:{message.chat_id}"
    elif message.chat_type == "group":
        scope = f"{source}:group:{message.chat_id}:{message.user_id}"
    elif message.chat_type == "guild":
        scope = f"{source}:guild:{message.chat_id}:{message.user_id}"
    elif message.chat_type == "direct":
        scope = f"{source}:direct:{message.chat_id}"
    elif message.chat_type == "thread":
        scope = f"{source}:thread:{message.thread_id or message.chat_id}"
    else:
        scope = f"{source}:{message.chat_type}:{message.chat_id}:{message.user_id}"
    return hashlib.sha256(scope.encode("utf-8")).hexdigest()[:16]


def _platform_key(value: str) -> str:
    text = str(value or "").strip().lower()
    if text == "lark":
        return "feishu"
    if text in {"qq", "feishu", "weixin"}:
        return text
    return "feishu"


def _actor_id(message: ChannelInboundMessage) -> str:
    return message.operator_id or message.user_id


def _role_set(settings: ChannelAdvancedSettings, platform_key: str, role: str) -> set[str]:
    return set(getattr(settings.allowlist, f"{platform_key}_{role}", []))


def _chat_uses_group_allowlist(chat_type: str) -> bool:
    return chat_type in {"group", "guild", "thread"}


def _route_matches(route, message: ChannelInboundMessage) -> bool:
    route_platform = str(route.platform or "").strip()
    message_platform = str(message.platform or "").strip()
    platform_matches = (
        not route_platform
        or route_platform == message_platform
        or _platform_key(route_platform) == _platform_key(message_platform)
    )
    if not platform_matches:
        return False
    checks = [
        (route.connection_id, message.connection_id),
        (route.chat_type, message.chat_type),
        (route.chat_id, message.chat_id),
        (route.user_id, message.user_id),
        (route.thread_id, message.thread_id),
    ]
    return all(not expected or str(expected).strip() == str(actual).strip() for expected, actual in checks)


def _pairing_matches(request: ChannelPairingRequestPublic, message: ChannelInboundMessage) -> bool:
    return (
        request.platform == message.platform
        and request.connection_id == message.connection_id
        and request.chat_type == message.chat_type
        and request.chat_id == message.chat_id
        and request.user_id == message.user_id
    )


def _new_pairing_code() -> str:
    return "".join(secrets.choice(_PAIRING_ALPHABET) for _ in range(6))


def _normalize_queue_mode(mode: str) -> str:
    value = str(mode or "").strip().lower()
    return value if value in {"steer", "followup", "collect", "interrupt"} else "steer"


def _normalize_queue_drop(drop: str) -> str:
    value = str(drop or "").strip().lower()
    return value if value in {"old", "new", "summarize"} else "summarize"


def _is_slash_bypass(text: str) -> bool:
    command = str(text or "").strip().split(" ", 1)[0]
    return command in _SLASH_BYPASS_COMMANDS


def _queue_summary(text: str) -> str:
    compact = " ".join(str(text or "").split())
    if not compact:
        return "(empty message)"
    if len(compact) <= 180:
        return compact
    return f"{compact[:180]}..."


def _merge_pending_turns(queue: list[_PendingTurn]) -> ChannelInboundMessage:
    merged = queue[0].message.model_copy(deep=True)
    texts = [turn.message.text for turn in queue if turn.message.text]
    if texts:
        merged.text = "\n".join(texts)
    return merged


def _with_dropped_prefix(text: str, dropped: list[str]) -> str:
    if not dropped:
        return text
    preview = dropped[:3]
    lines = [
        f"[Queue note: {len(dropped)} older pending message(s) were dropped because this bot session reached its queue cap.",
        "Dropped summaries:",
        *[f"- {item}" for item in preview],
    ]
    if len(dropped) > len(preview):
        lines.append(f"- ... and {len(dropped) - len(preview)} more")
    lines.append("]")
    return "\n".join(lines) + "\n\n" + text
