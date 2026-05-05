"""OAuth 2.0 Authorization Code flow endpoints.

Routes
──────
GET  /oauth/providers            → list all supported provider presets
POST /oauth/start                → initiate Auth Code + PKCE flow
GET  /oauth/callback             → receive authorization code from provider
GET  /oauth/status/{state}       → poll for flow completion
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse

from src.application.models.oauth_provider_profiles import list_profiles
from src.schemas.oauth import (
    OAuthModelItem,
    OAuthModelsResponse,
    OAuthProviderListResponse,
    OAuthStartRequest,
    OAuthStartResponse,
    OAuthStatusResponse,
)

router = APIRouter(prefix="/oauth", tags=["oauth"])

_SUCCESS_HTML = """
<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="UTF-8"/>
  <title>OAuth 授权成功</title>
  <style>
    body {{ font-family: system-ui, sans-serif; display: flex; align-items: center;
           justify-content: center; height: 100vh; margin: 0; background: #0f0f0f; color: #e5e5e5; }}
    .card {{ text-align: center; padding: 2rem 3rem; background: #1a1a1a;
             border-radius: 12px; border: 1px solid #333; }}
    .icon {{ font-size: 3rem; margin-bottom: 1rem; }}
    h2 {{ margin: 0 0 0.5rem; }}
    p  {{ color: #888; margin: 0; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">✅</div>
    <h2>OAuth 授权成功</h2>
    <p>您可以关闭此标签页，返回配置页面继续操作。</p>
  </div>
</body>
</html>
"""

_FAILURE_HTML = """
<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="UTF-8"/>
  <title>OAuth 授权失败</title>
  <style>
    body {{ font-family: system-ui, sans-serif; display: flex; align-items: center;
           justify-content: center; height: 100vh; margin: 0; background: #0f0f0f; color: #e5e5e5; }}
    .card {{ text-align: center; padding: 2rem 3rem; background: #1a1a1a;
             border-radius: 12px; border: 1px solid #333; }}
    .icon {{ font-size: 3rem; margin-bottom: 1rem; }}
    h2 {{ margin: 0 0 0.5rem; color: #f87171; }}
    p  {{ color: #888; margin: 0; }}
    code {{ display: block; margin-top: 1rem; background: #111; padding: 0.75rem 1rem;
            border-radius: 6px; font-size: 0.85rem; color: #fca5a5; text-align: left; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">❌</div>
    <h2>OAuth 授权失败</h2>
    <p>请关闭此标签页，返回配置页面重试。</p>
    <code>{error}</code>
  </div>
</body>
</html>
"""


@router.get("/providers", response_model=OAuthProviderListResponse)
async def list_oauth_providers():
    """Return all known OAuth provider presets."""
    return OAuthProviderListResponse(providers=list_profiles())


@router.post("/start", response_model=OAuthStartResponse)
async def start_oauth_flow(payload: OAuthStartRequest, request: Request):
    """Initiate an Authorization Code + PKCE flow.

    Returns the authorization URL the frontend should open in a new browser tab.
    Poll ``/oauth/status/{state}`` to detect completion.
    """
    oauth_svc = request.app.state.oauth_token_service
    try:
        return await oauth_svc.start_auth_code_flow(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/callback", response_class=HTMLResponse)
async def oauth_callback(request: Request):
    """Receive the authorization code from the OAuth provider.

    The OAuth provider redirects the user here after they approve the request.
    This endpoint exchanges the code for tokens and stores the result so the
    frontend can retrieve it via ``/oauth/status/{state}``.
    """
    params = dict(request.query_params)
    code = params.get("code", "").strip()
    state = params.get("state", "").strip()
    error = params.get("error", "").strip()
    error_description = params.get("error_description", "").strip()

    if error:
        detail = error_description or error
        oauth_svc = request.app.state.oauth_token_service
        # Store the failure so the frontend can surface it
        from src.application.models.oauth_token_service import _CompletedFlow
        oauth_svc._completed[state] = _CompletedFlow(
            status="failed",
            error=f"Provider rejected authorization: {detail}",
        )
        return HTMLResponse(
            content=_FAILURE_HTML.format(error=detail),
            status_code=200,
        )

    if not code or not state:
        return HTMLResponse(
            content=_FAILURE_HTML.format(
                error="Missing 'code' or 'state' parameter in callback URL."
            ),
            status_code=200,
        )

    oauth_svc = request.app.state.oauth_token_service
    await oauth_svc.handle_callback(code=code, state=state)

    result = oauth_svc._completed.get(state)
    if result and result.status == "failed":
        return HTMLResponse(
            content=_FAILURE_HTML.format(error=result.error),
            status_code=200,
        )

    return HTMLResponse(content=_SUCCESS_HTML, status_code=200)


@router.get("/models", response_model=OAuthModelsResponse)
async def list_oauth_models(
    request: Request,
    provider: str = Query(..., description="Provider key, e.g. google / github / codex"),
    state: str | None = Query(None, description="State from a completed OAuth flow"),
    base_url: str | None = Query(None, description="Azure resource base URL (azure_ad only)"),
):
    """List models available for an OAuth provider.

    If *state* is supplied and points to a completed OAuth flow, the associated
    access token is used. Otherwise falls back to client-credentials using the
    server-side .env credentials.
    """
    oauth_svc = request.app.state.oauth_token_service
    try:
        items = await oauth_svc.list_models(provider=provider, state=state, base_url=base_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Failed to fetch models: {exc}") from exc
    return OAuthModelsResponse(
        provider=provider,
        models=[OAuthModelItem(**item) for item in items],
    )


@router.get("/status/{state}", response_model=OAuthStatusResponse)
async def get_oauth_status(state: str, request: Request):
    """Poll for the result of an OAuth flow.

    - ``pending``   → user has not yet authorized (keep polling)
    - ``completed`` → tokens available; ``refresh_token`` field populated
    - ``failed``    → authorization failed; ``error`` field populated
    """
    oauth_svc = request.app.state.oauth_token_service
    return oauth_svc.get_flow_status(state)
