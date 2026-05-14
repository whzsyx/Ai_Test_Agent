"""Manage credential sessions for API testing campaigns.

First version: in-memory per-session credential store. Credentials are
provided by the user (token / username+password) or obtained via a dynamic
login flow executed by the executor.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from src.modes.api_testing_mode.campaign_state import CredentialSession
from src.modes.api_testing_mode.contracts import (
    AUTH_BEARER,
    AUTH_BASIC,
    AUTH_COOKIE,
    AUTH_CUSTOM,
    AUTH_NONE,
)


class CredentialManager:
    """Create, store, and resolve credential sessions."""

    def __init__(self) -> None:
        self._sessions: dict[str, CredentialSession] = {}

    def create_from_user_input(
        self,
        *,
        extracted: dict[str, Any],
        source: str = "user_input",
    ) -> CredentialSession:
        auth_type = str(extracted.get("auth_type") or AUTH_BEARER)
        token = str(extracted.get("token") or "")
        cookie = str(extracted.get("cookie") or "")
        username = str(extracted.get("username") or "")
        password = str(extracted.get("password") or "")

        headers: dict[str, str] = {}
        cookie_jar: dict[str, str] = {}

        if auth_type == AUTH_BEARER and token:
            headers["Authorization"] = f"Bearer {token}"
        elif auth_type == "api_key" and token:
            headers["Authorization"] = token
        elif auth_type == AUTH_BASIC and username:
            import base64
            encoded = base64.b64encode(f"{username}:{password}".encode()).decode()
            headers["Authorization"] = f"Basic {encoded}"
        elif auth_type == AUTH_COOKIE and cookie:
            cookie_jar["session"] = cookie

        session = CredentialSession(
            credential_session_id=str(uuid4()),
            auth_type=auth_type,
            token=token,
            cookie_jar=cookie_jar,
            headers=headers,
            expires_at="",
            source=source,
            notes=f"Created from {source} at {datetime.now(timezone.utc).isoformat()}",
        )
        self._sessions[session.credential_session_id] = session
        return session

    def create_from_login_response(
        self,
        *,
        response_body: dict[str, Any],
        token_field: str = "access_token",
        login_endpoint: str = "",
    ) -> CredentialSession:
        token = str(response_body.get(token_field) or response_body.get("token") or "")
        if not token:
            for key, value in response_body.items():
                if "token" in key.lower() and isinstance(value, str) and len(value) > 10:
                    token = value
                    token_field = key
                    break

        headers: dict[str, str] = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        session = CredentialSession(
            credential_session_id=str(uuid4()),
            auth_type=AUTH_BEARER,
            token=token,
            headers=headers,
            expires_at="",
            source="dynamic_login",
            login_endpoint=login_endpoint,
            notes=f"Obtained via {login_endpoint} field={token_field}",
        )
        self._sessions[session.credential_session_id] = session
        return session

    def get(self, credential_session_id: str) -> CredentialSession | None:
        return self._sessions.get(credential_session_id)

    def restore_session(self, session: CredentialSession) -> CredentialSession:
        restored = session.model_copy(deep=True)
        if not restored.credential_session_id:
            restored.credential_session_id = str(uuid4())
        self._sessions[restored.credential_session_id] = restored
        return restored

    def has_valid_session(self) -> bool:
        for session in self._sessions.values():
            if session.token or session.headers or session.cookie_jar:
                return True
        return False

    def get_latest(self) -> CredentialSession | None:
        if not self._sessions:
            return None
        return list(self._sessions.values())[-1]

    def build_request_headers(self, credential_session_id: str) -> dict[str, str]:
        session = self._sessions.get(credential_session_id)
        if session is None:
            return {}
        headers = dict(session.headers)
        if session.cookie_jar:
            cookie_str = "; ".join(f"{k}={v}" for k, v in session.cookie_jar.items())
            headers["Cookie"] = cookie_str
        return headers

    def clear(self) -> None:
        self._sessions.clear()


__all__ = ["CredentialManager"]
