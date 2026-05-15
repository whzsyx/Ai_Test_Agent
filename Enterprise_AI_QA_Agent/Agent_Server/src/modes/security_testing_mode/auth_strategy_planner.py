"""Authentication strategy planning for Security Testing Mode."""
from __future__ import annotations

from uuid import uuid4

from src.modes.security_testing_mode.campaign_state import (
    CredentialSession,
    SecurityTestingRequestState,
)


class SecurityAuthStrategyPlanner:
    """Normalize user-provided authentication hints into a credential session.

    Phase 1 does not attempt automatic login or credential attacks. It only
    preserves explicitly provided, authorized credentials for later safe use.
    """

    def prepare_credential_session(
        self,
        request: SecurityTestingRequestState,
    ) -> CredentialSession | None:
        credentials = request.credentials or {}
        auth_hint = (request.auth_hint or "").strip().lower()
        if not credentials and not auth_hint:
            return None

        token = str(credentials.get("token") or credentials.get("bearer") or credentials.get("api_key") or "").strip()
        username = str(credentials.get("username") or credentials.get("user") or "").strip()
        cookie_value = str(credentials.get("cookie") or credentials.get("cookies") or "").strip()

        auth_type = "none"
        headers: dict[str, str] = {}
        cookie_jar: dict[str, str] = {}
        if token:
            auth_type = "bearer" if "bearer" in auth_hint or "token" in auth_hint else "api_key"
            headers["Authorization"] = f"Bearer {token}" if auth_type == "bearer" else token
        elif cookie_value:
            auth_type = "cookie"
            cookie_jar["Cookie"] = cookie_value
        elif username or auth_hint:
            auth_type = "basic" if "basic" in auth_hint else "provided"

        return CredentialSession(
            credential_session_id=f"cred_{uuid4().hex[:8]}",
            auth_type=auth_type,
            username=username,
            token=token,
            cookie_jar=cookie_jar,
            headers=headers,
            source="user_input" if credentials else "auth_hint",
            login_url=str(credentials.get("login_url") or "").strip(),
            notes=request.auth_hint,
        )


__all__ = ["SecurityAuthStrategyPlanner"]
