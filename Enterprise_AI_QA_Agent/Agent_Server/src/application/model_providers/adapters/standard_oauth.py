from __future__ import annotations

import base64
import hashlib
import os
import secrets
import time
import urllib.parse
from typing import TYPE_CHECKING

import httpx

from src.application.model_providers.models import AuthStartResult, CompletedAuthFlow, PendingAuthFlow
from src.application.model_providers.provider_base import ModelProviderAdapter
from src.application.models.oauth_provider_profiles import get_profile, resolve_url
from src.schemas.oauth import OAuthStartRequest, OAuthStatusResponse

if TYPE_CHECKING:
    from src.schemas.model_config import ModelConfigRecord


class StandardOAuthProviderAdapter(ModelProviderAdapter):
    async def start_auth(self, request: OAuthStartRequest) -> AuthStartResult:
        state = secrets.token_urlsafe(32)
        code_verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
        code_challenge = (
            base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )

        client_id, client_secret, tenant_id = self._get_provider_credentials()
        if not client_id or not client_secret:
            raise ValueError(
                f"OAuth credentials (client_id/secret) not configured in .env for provider '{self.provider_key}'."
            )

        profile = self._get_profile()
        auth_url = resolve_url(profile.authorization_url_template, tenant_id)
        token_url = resolve_url(profile.token_url_template, tenant_id)
        if not auth_url or not token_url:
            raise ValueError(f"OAuth endpoints are not configured for provider '{self.provider_key}'.")

        params: dict[str, str] = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": request.redirect_uri,
            "scope": profile.default_scope,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            **dict(profile.extra_auth_params),
        }
        authorization_url = f"{auth_url}?{urllib.parse.urlencode(params)}"

        self._flow_store.set_pending(
            state,
            PendingAuthFlow(
                provider=self.provider_key,
                client_id=client_id,
                client_secret=client_secret,
                token_url=token_url,
                redirect_uri=request.redirect_uri,
                code_verifier=code_verifier,
                scope=profile.default_scope,
            ),
        )
        return AuthStartResult(state=state, authorization_url=authorization_url, redirect_uri=request.redirect_uri)

    async def handle_callback(
        self,
        *,
        code: str,
        state: str,
        error: str | None = None,
    ) -> None:
        if error:
            self._flow_store.mark_failed(state, error)
            return

        pending = self._flow_store.pop_pending(state)
        if pending is None:
            self._flow_store.mark_failed(
                state,
                "Unknown or expired OAuth state. Please click 'Launch OAuth' again to restart the flow.",
            )
            return

        try:
            token_data: dict[str, str] = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": pending.redirect_uri,
                "client_id": pending.client_id,
                "client_secret": pending.client_secret,
                "code_verifier": pending.code_verifier,
            }
            access_token, refresh_token, _ = await self._post_token_request(pending.token_url, token_data)
            self._flow_store.set_completed(
                state,
                CompletedAuthFlow(
                    provider=self.provider_key,
                    status="completed",
                    access_token=access_token,
                    refresh_token=refresh_token,
                ),
            )
        except Exception as exc:
            self._flow_store.mark_failed(state, str(exc))

    def get_flow_status(self, state: str) -> OAuthStatusResponse:
        self._flow_store.cleanup_expired()
        if self._flow_store.get_pending(state) is not None:
            return OAuthStatusResponse(state=state, status="pending")

        completed = self._flow_store.get_completed(state)
        if completed is None:
            return OAuthStatusResponse(
                state=state,
                status="failed",
                error="OAuth state not found or already consumed.",
            )

        preview = (completed.access_token[:20] + "...") if completed.access_token else None
        return OAuthStatusResponse(
            state=state,
            status=completed.status,
            refresh_token=completed.refresh_token or None,
            access_token_preview=preview,
            error=completed.error or None,
        )

    async def list_models(
        self,
        *,
        state: str | None = None,
        base_url: str | None = None,
    ) -> list[dict]:
        profile = self._get_profile()

        models_url = profile.models_endpoint
        if not models_url and base_url:
            models_url = f"{base_url.rstrip('/')}/openai/models?api-version=2024-05-01-preview"
        if not models_url:
            return []

        access_token = ""
        if state:
            completed = self._flow_store.get_completed(state)
            if completed and completed.status == "completed" and completed.access_token:
                access_token = completed.access_token

        if not access_token:
            client_id, client_secret, tenant_id = self._get_provider_credentials()
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
                    access_token, _, _ = await self._post_token_request(token_url, data)
                except Exception:
                    access_token = ""

        if not access_token:
            raise ValueError(
                f"No valid access token available for provider '{self.provider_key}'. Complete the OAuth authorization flow first."
            )

        async with httpx.AsyncClient(timeout=self._request_timeout) as client:
            response = await client.get(
                models_url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                    **self._build_model_list_headers(),
                },
            )
            response.raise_for_status()
            payload = response.json()

        raw_items = payload
        if profile.models_response_path:
            for key in profile.models_response_path.split("."):
                if isinstance(raw_items, dict):
                    raw_items = raw_items.get(key, [])

        if not isinstance(raw_items, list):
            return []

        results: list[dict] = []
        id_field = profile.model_id_field or "id"
        name_field = profile.model_name_field
        for item in raw_items:
            if not isinstance(item, dict):
                continue
            model_id = str(item.get(id_field) or "").strip()
            if not model_id:
                continue
            display_id = model_id.split("/")[-1] if "/" in model_id else model_id
            model_name = str(item.get(name_field) or display_id).strip() if name_field else display_id
            results.append({"id": display_id, "raw_id": model_id, "name": model_name})
        return results

    async def get_runtime_token(self, config: "ModelConfigRecord") -> str:
        if getattr(config, "oauth_refresh_token", None):
            access_token, _, _ = await self._refresh_token_grant(config)
            return access_token
        access_token, _, _ = await self._client_credentials_grant()
        return access_token

    async def _client_credentials_grant(self) -> tuple[str, str, float]:
        client_id, client_secret, tenant_id = self._get_provider_credentials()
        profile = self._get_profile()
        token_url = resolve_url(profile.token_url_template, tenant_id)
        if not token_url or not client_id or not client_secret:
            raise ValueError(f"OAuth client credentials are not configured for provider '{self.provider_key}'.")

        data: dict[str, str] = {
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        }
        if profile.default_scope:
            data["scope"] = profile.default_scope
        return await self._post_token_request(token_url, data)

    async def _refresh_token_grant(self, config: "ModelConfigRecord") -> tuple[str, str, float]:
        client_id, client_secret, tenant_id = self._get_provider_credentials()
        profile = self._get_profile()
        token_url = resolve_url(profile.token_url_template, tenant_id)
        refresh_token = str(getattr(config, "oauth_refresh_token", "") or "").strip()
        if not token_url or not refresh_token:
            raise ValueError(f"No refresh-token flow is available for provider '{self.provider_key}'.")

        data: dict[str, str] = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
        }
        if client_secret:
            data["client_secret"] = client_secret
        if profile.default_scope:
            data["scope"] = profile.default_scope
        return await self._post_token_request(token_url, data)

    async def _post_token_request(self, url: str, data: dict[str, str]) -> tuple[str, str, float]:
        headers = {"Accept": "application/json"}
        async with httpx.AsyncClient(timeout=self._request_timeout) as client:
            response = await client.post(url, data=data, headers=headers)
            response.raise_for_status()
            payload = response.json()

        access_token = str(payload.get("access_token") or "").strip()
        refresh_token = str(payload.get("refresh_token") or "").strip()
        if not access_token:
            raise RuntimeError(
                f"Token endpoint returned no access_token for provider '{self.provider_key}'. Response keys: {list(payload.keys())}"
            )
        expires_in = int(payload.get("expires_in") or 3600)
        expire_at = time.monotonic() + expires_in
        return access_token, refresh_token, expire_at

    def _get_profile(self):
        profile = get_profile(self.provider_key)
        if not profile:
            raise ValueError(f"Unknown OAuth provider '{self.provider_key}'.")
        return profile

    def _build_model_list_headers(self) -> dict[str, str]:
        return {}

    def _get_provider_credentials(self) -> tuple[str, str, str | None]:
        raise NotImplementedError
