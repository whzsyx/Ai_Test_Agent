"""OAuth 2.0 multi-flow token service.

Supported grant types
─────────────────────
- **Authorization Code + PKCE** (browser-based, RFC 7636)
  1. ``start_auth_code_flow()``  → returns authorization URL + opaque state
  2. ``handle_callback()``       → exchanges code for tokens (called by callback route)
  3. ``get_flow_status()``       → poll until "completed" or "failed"
- **Refresh Token** (RFC 6749 §6) — used for runtime invocations after Auth Code
- **Client Credentials** (RFC 6749 §4.4) — for server-to-server (backward compat)

Token cache
───────────
Access tokens are cached in memory keyed by model config name.  Tokens are
proactively refreshed when within ``_REFRESH_BUFFER_SECONDS`` of expiry.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import os
import secrets
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

import httpx

from src.application.models.oauth_provider_profiles import get_profile, resolve_url
from src.core.config import Settings
from src.schemas.oauth import OAuthStartRequest, OAuthStartResponse, OAuthStatusResponse

if TYPE_CHECKING:
    from src.schemas.model_config import ModelConfigRecord

_REFRESH_BUFFER_SECONDS = 60
_FLOW_TTL_SECONDS = 600  # pending / completed flows expire after 10 min


# ── Internal state objects ────────────────────────────────────────────────────


@dataclass
class _PendingFlow:
    provider: str
    client_id: str
    client_secret: str
    token_url: str
    redirect_uri: str
    code_verifier: str
    scope: str
    created_at: float = field(default_factory=time.monotonic)


@dataclass
class _CompletedFlow:
    status: Literal["completed", "failed"]
    access_token: str = ""
    refresh_token: str = ""
    error: str = ""
    completed_at: float = field(default_factory=time.monotonic)


# ── Service ───────────────────────────────────────────────────────────────────


class OAuthTokenService:
    def __init__(self, settings: Settings, request_timeout: float = 30.0) -> None:
        self._settings = settings
        self._request_timeout = request_timeout
        # access-token cache:  config_name → (token, expire_at monotonic)
        self._token_cache: dict[str, tuple[str, float]] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        # Auth Code flow state
        self._pending: dict[str, _PendingFlow] = {}
        self._completed: dict[str, _CompletedFlow] = {}

    # ── Runtime token resolution ──────────────────────────────────────────────

    async def get_token(self, config: "ModelConfigRecord") -> str:
        """Return a valid access token for *config*, refreshing/fetching as needed."""
        lock = self._get_lock(config.name)
        async with lock:
            cached = self._token_cache.get(config.name)
            if cached is not None:
                token, expire_at = cached
                if time.monotonic() < expire_at - _REFRESH_BUFFER_SECONDS:
                    return token
            token, expire_at = await self._acquire_token(config)
            self._token_cache[config.name] = (token, expire_at)
            return token

    async def fetch_token_once(self, config: "ModelConfigRecord") -> str:
        """Fetch a fresh token (bypass cache). Used for connection tests."""
        token, _ = await self._acquire_token(config)
        return token

    def invalidate(self, config: "ModelConfigRecord") -> None:
        """Drop cached token — call after credential changes."""
        self._token_cache.pop(config.name, None)

    # ── Authorization Code + PKCE flow ───────────────────────────────────────

    async def start_auth_code_flow(self, req: OAuthStartRequest) -> OAuthStartResponse:
        """Initiate an Authorization Code flow.  Returns the URL to open in the browser."""
        self._cleanup_expired_flows()

        state = secrets.token_urlsafe(32)
        code_verifier = (
            base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
        )
        code_challenge = (
            base64.urlsafe_b64encode(
                hashlib.sha256(code_verifier.encode()).digest()
            )
            .rstrip(b"=")
            .decode()
        )

        client_id, client_secret, tenant_id = self._get_provider_credentials(req.provider)
        if not client_id or not client_secret:
            raise ValueError(
                f"OAuth credentials (client_id/secret) not configured in .env "
                f"for provider '{req.provider}'."
            )

        profile = get_profile(req.provider)
        if not profile:
            raise ValueError(f"Unknown OAuth provider '{req.provider}'.")

        auth_url_tmpl = profile.authorization_url_template
        token_url_tmpl = profile.token_url_template
        extra_params = dict(profile.extra_auth_params)

        auth_url = resolve_url(auth_url_tmpl, tenant_id)
        token_url = resolve_url(token_url_tmpl, tenant_id)

        if not auth_url:
            raise ValueError(
                f"Authorization URL is not configured for provider '{req.provider}'."
            )
        if not token_url:
            raise ValueError(
                f"Token URL is not configured for provider '{req.provider}'."
            )

        params: dict[str, str] = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": req.redirect_uri,
            "scope": profile.default_scope,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            **extra_params,
        }
        authorization_url = f"{auth_url}?{urllib.parse.urlencode(params)}"

        self._pending[state] = _PendingFlow(
            provider=req.provider,
            client_id=client_id,
            client_secret=client_secret,
            token_url=token_url,
            redirect_uri=req.redirect_uri,
            code_verifier=code_verifier,
            scope=profile.default_scope,
        )
        return OAuthStartResponse(
            state=state,
            authorization_url=authorization_url,
            redirect_uri=req.redirect_uri,
        )

    async def handle_callback(self, code: str, state: str) -> None:
        """Exchange authorization code for tokens (called from the OAuth callback route)."""
        pending = self._pending.pop(state, None)
        if pending is None:
            self._completed[state] = _CompletedFlow(
                status="failed",
                error=(
                    "Unknown or expired OAuth state. "
                    "Please click 'Launch OAuth' again to restart the flow."
                ),
            )
            return

        try:
            data: dict[str, str] = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": pending.redirect_uri,
                "client_id": pending.client_id,
                "client_secret": pending.client_secret,
                "code_verifier": pending.code_verifier,
            }
            headers = {"Accept": "application/json"}
            async with httpx.AsyncClient(timeout=self._request_timeout) as client:
                response = await client.post(
                    pending.token_url, data=data, headers=headers
                )
                response.raise_for_status()
                payload = response.json()

            access_token = str(payload.get("access_token") or "").strip()
            refresh_token = str(payload.get("refresh_token") or "").strip()
            if not access_token:
                raise RuntimeError(
                    f"Provider returned no access_token. "
                    f"Response keys: {list(payload.keys())}"
                )

            self._completed[state] = _CompletedFlow(
                status="completed",
                access_token=access_token,
                refresh_token=refresh_token,
            )
        except Exception as exc:
            self._completed[state] = _CompletedFlow(
                status="failed",
                error=str(exc),
            )

    def get_flow_status(self, state: str) -> OAuthStatusResponse:
        """Return the current status of an OAuth flow."""
        if state in self._pending:
            return OAuthStatusResponse(state=state, status="pending")

        completed = self._completed.get(state)
        if completed is None:
            return OAuthStatusResponse(
                state=state,
                status="failed",
                error="OAuth state not found or already consumed.",
            )

        preview = (
            (completed.access_token[:20] + "…") if completed.access_token else None
        )
        return OAuthStatusResponse(
            state=state,
            status=completed.status,
            refresh_token=completed.refresh_token or None,
            access_token_preview=preview,
            error=completed.error or None,
        )

    def consume_completed_flow(self, state: str) -> _CompletedFlow | None:
        """Pop and return a completed flow (removes it from memory)."""
        return self._completed.pop(state, None)

    # ── Model listing ─────────────────────────────────────────────────────────

    async def list_models(
        self,
        provider: str,
        state: str | None = None,
        base_url: str | None = None,
    ) -> list[dict]:
        """Fetch the list of available models for a provider.

        Uses the access token from a completed OAuth flow (identified by *state*) when
        available, otherwise falls back to client credentials.

        Returns a list of dicts with at least ``{"id": str, "name": str}``.
        """
        from src.application.models.oauth_provider_profiles import get_profile

        profile = get_profile(provider)
        if not profile:
            raise ValueError(f"Unknown OAuth provider '{provider}'.")

        # Determine the models endpoint
        models_url = profile.models_endpoint
        if not models_url and base_url:
            # Azure AD: derive from the user-supplied resource base URL
            models_url = f"{base_url.rstrip('/')}/openai/models?api-version=2024-05-01-preview"
        if not models_url:
            return []

        # Obtain access token
        access_token = ""
        if state:
            completed = self._completed.get(state)
            if completed and completed.status == "completed" and completed.access_token:
                access_token = completed.access_token

        if not access_token:
            # Try client credentials / refresh token using a dummy config-like object
            client_id, client_secret, tenant_id = self._get_provider_credentials(provider)
            if client_id and client_secret:
                token_url = resolve_url(profile.token_url_template, tenant_id)
                data: dict[str, str] = {
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret,
                }
                if profile.default_scope:
                    data["scope"] = profile.default_scope
                try:
                    access_token, _ = await self._post_token(token_url, data, provider)
                except Exception:
                    access_token = ""

        if not access_token:
            raise ValueError(
                f"No valid access token available for provider '{provider}'. "
                "Complete the OAuth authorization flow first."
            )

        # Build extra headers some providers need
        extra_headers: dict[str, str] = {}
        if provider == "github":
            extra_headers["Copilot-Integration-Id"] = "vscode-chat"
        elif provider == "google" and self._settings.oauth_google_project_id.strip():
            extra_headers["x-goog-user-project"] = self._settings.oauth_google_project_id.strip()

        async with httpx.AsyncClient(timeout=self._request_timeout) as client:
            resp = await client.get(
                models_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                    **extra_headers,
                },
            )
            resp.raise_for_status()
            payload = resp.json()

        raw_items = payload
        if profile.models_response_path:
            for key in profile.models_response_path.split("."):
                if isinstance(raw_items, dict):
                    raw_items = raw_items.get(key, [])

        if not isinstance(raw_items, list):
            return []

        results: list[dict] = []
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            model_id = str(item.get(profile.model_id_field or "id") or "").strip()
            if not model_id:
                continue
            # Google returns "models/gemini-2.0-flash" — strip the prefix for display/use
            display_id = model_id.split("/")[-1] if "/" in model_id else model_id
            name_field = profile.model_name_field
            model_name = str(item.get(name_field) or display_id).strip() if name_field else display_id
            results.append({"id": display_id, "raw_id": model_id, "name": model_name})

        return results

    # ── Grant implementations ─────────────────────────────────────────────────

    async def _acquire_token(self, config: "ModelConfigRecord") -> tuple[str, float]:
        """Select the appropriate grant type and return (access_token, expire_at)."""
        if getattr(config, "oauth_refresh_token", None):
            return await self._refresh_token_grant(config)
        return await self._client_credentials_grant(config)

    async def _client_credentials_grant(
        self, config: "ModelConfigRecord"
    ) -> tuple[str, float]:
        provider = str(config.oauth_provider or "").strip()
        if not provider:
            raise ValueError(f"oauth_provider is required for model '{config.name}'.")

        client_id, client_secret, tenant_id = self._get_provider_credentials(provider)
        profile = get_profile(provider)
        
        if not profile:
            raise ValueError(f"Unknown OAuth provider '{provider}' for model '{config.name}'.")
            
        endpoint = resolve_url(profile.token_url_template, tenant_id)
        scope = profile.default_scope

        if not endpoint:
            raise ValueError(
                f"OAuth token endpoint not configured for provider '{provider}'."
            )
        if not client_id or not client_secret:
            raise ValueError(
                f"OAuth credentials (client_id/secret) not configured in .env "
                f"for provider '{provider}'."
            )

        data: dict[str, str] = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }
        if scope:
            data["scope"] = scope

        return await self._post_token(endpoint, data, config.name)

    async def _refresh_token_grant(
        self, config: "ModelConfigRecord"
    ) -> tuple[str, float]:
        provider = str(config.oauth_provider or "").strip()
        if not provider:
            raise ValueError(f"oauth_provider is required for model '{config.name}'.")

        client_id, client_secret, tenant_id = self._get_provider_credentials(provider)
        profile = get_profile(provider)
        
        if not profile:
            raise ValueError(f"Unknown OAuth provider '{provider}' for model '{config.name}'.")
            
        endpoint = resolve_url(profile.token_url_template, tenant_id)
        refresh_token = str(getattr(config, "oauth_refresh_token", "") or "").strip()

        if not endpoint:
            raise ValueError(
                f"OAuth token endpoint not configured for provider '{provider}'."
            )
        if not refresh_token:
            raise ValueError(
                f"No oauth_refresh_token stored for model '{config.name}'."
            )

        data: dict[str, str] = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
        }
        if client_secret:
            data["client_secret"] = client_secret
        if profile.default_scope:
            data["scope"] = profile.default_scope

        return await self._post_token(endpoint, data, config.name)

    async def _post_token(
        self, url: str, data: dict[str, str], model_name: str
    ) -> tuple[str, float]:
        headers = {"Accept": "application/json"}
        async with httpx.AsyncClient(timeout=self._request_timeout) as client:
            response = await client.post(url, data=data, headers=headers)
            response.raise_for_status()
            payload = response.json()

        access_token = str(payload.get("access_token") or "").strip()
        if not access_token:
            raise RuntimeError(
                f"Token endpoint returned no access_token for model '{model_name}'. "
                f"Response keys: {list(payload.keys())}"
            )

        expires_in = int(payload.get("expires_in") or 3600)
        expire_at = time.monotonic() + expires_in
        return access_token, expire_at

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_provider_credentials(self, provider: str) -> tuple[str, str, str | None]:
        """Return (client_id, client_secret, tenant_id) from settings."""
        p = provider.lower()
        if p == "azure_ad":
            return (
                self._settings.oauth_azure_ad_client_id,
                self._settings.oauth_azure_ad_client_secret,
                self._settings.oauth_azure_ad_tenant_id,
            )
        if p == "google":
            return (
                self._settings.oauth_google_client_id,
                self._settings.oauth_google_client_secret,
                None,
            )
        if p == "github":
            return (
                self._settings.oauth_github_client_id,
                self._settings.oauth_github_client_secret,
                None,
            )
        if p == "codebuddy":
            return (
                self._settings.oauth_codebuddy_client_id,
                self._settings.oauth_codebuddy_client_secret,
                None,
            )
        if p == "trae":
            return (
                self._settings.oauth_trae_client_id,
                self._settings.oauth_trae_client_secret,
                None,
            )
        if p == "codex":
            return (
                self._settings.oauth_codex_client_id,
                self._settings.oauth_codex_client_secret,
                None,
            )
        return ("", "", None)

    def _get_lock(self, key: str) -> asyncio.Lock:
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]

    def _cleanup_expired_flows(self) -> None:
        now = time.monotonic()
        expired_p = [
            s for s, f in self._pending.items()
            if now - f.created_at > _FLOW_TTL_SECONDS
        ]
        for s in expired_p:
            del self._pending[s]
        expired_c = [
            s for s, f in self._completed.items()
            if now - f.completed_at > _FLOW_TTL_SECONDS
        ]
        for s in expired_c:
            del self._completed[s]
