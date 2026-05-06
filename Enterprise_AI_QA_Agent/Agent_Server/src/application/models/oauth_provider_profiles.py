"""Known OAuth/login provider presets for model integrations."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class OAuthProviderProfile:
    key: str
    display_name: str
    authorization_url_template: str  # {tenant_id} replaced when present
    token_url_template: str
    default_scope: str
    extra_auth_params: dict[str, str] = field(default_factory=dict)
    notes: str = ""
    api_base_url: str = ""
    default_transport: str = "openai_chat_completions"
    models_endpoint: str = ""
    models_response_path: str = "data"
    model_id_field: str = "id"
    model_name_field: str = ""
    requires_base_url: bool = False
    auth_mode: str = "standard_oauth"
    supports_manual_model_name: bool = True
    is_enabled: bool = True


_PROFILES: dict[str, OAuthProviderProfile] = {
    "azure_ad": OAuthProviderProfile(
        key="azure_ad",
        display_name="Azure AD / Microsoft Entra ID",
        authorization_url_template=(
            "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize"
        ),
        token_url_template=(
            "https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
        ),
        default_scope="https://cognitiveservices.azure.com/.default offline_access",
        notes=(
            "Azure OpenAI Service. The resource endpoint (Base URL) is unique to your "
            "Azure deployment — fill it in below after authorizing."
        ),
        api_base_url="",
        default_transport="openai_chat_completions",
        models_endpoint="",
        models_response_path="data",
        model_id_field="id",
        requires_base_url=True,
        auth_mode="standard_oauth",
    ),
    "google": OAuthProviderProfile(
        key="google",
        display_name="Google OAuth 2.0 (Gemini / AI Studio)",
        authorization_url_template="https://accounts.google.com/o/oauth2/v2/auth",
        token_url_template="https://oauth2.googleapis.com/token",
        default_scope="https://www.googleapis.com/auth/generative-language.retriever",
        extra_auth_params={"access_type": "offline", "prompt": "consent"},
        notes=(
            "Google Gemini / AI Studio API. Register OAuth credentials in "
            "Google Cloud Console → APIs & Services → Credentials."
        ),
        api_base_url="https://generativelanguage.googleapis.com",
        default_transport="google_gemini_generate_content",
        models_endpoint="https://generativelanguage.googleapis.com/v1beta/models",
        models_response_path="models",
        model_id_field="name",
        model_name_field="displayName",
        auth_mode="standard_oauth",
        supports_manual_model_name=True,
    ),
    "github": OAuthProviderProfile(
        key="github",
        display_name="GitHub OAuth (Copilot API)",
        authorization_url_template="https://github.com/login/oauth/authorize",
        token_url_template="https://github.com/login/oauth/access_token",
        default_scope="user",
        notes=(
            "GitHub Copilot API access. Register your OAuth App at "
            "github.com/settings/developers and set the callback URL."
        ),
        api_base_url="https://api.githubcopilot.com",
        default_transport="openai_chat_completions",
        models_endpoint="https://api.githubcopilot.com/models",
        models_response_path="data",
        model_id_field="id",
        model_name_field="name",
        auth_mode="standard_oauth",
    ),
    "codebuddy": OAuthProviderProfile(
        key="codebuddy",
        display_name="CodeBuddy (腾讯云 IDE)",
        authorization_url_template="https://ide.cloud.tencent.com/oauth2/authorize",
        token_url_template="https://ide.cloud.tencent.com/oauth2/token",
        default_scope="openid profile",
        notes=(
            "Tencent CodeBuddy polling-login provider. Configure "
            "OAUTH_CODEBUDDY_CLIENT_ID / SECRET first. If you also configure "
            "OAUTH_CODEBUDDY_MODELS_ENDPOINT, the page can fetch the model list automatically; "
            "otherwise you can still authorize first and enter the model name manually."
        ),
        api_base_url="https://api.ai.qq.com/v1",
        default_transport="openai_chat_completions",
        models_endpoint="",
        auth_mode="polling_auth",
        is_enabled=True,
    ),
    "trae": OAuthProviderProfile(
        key="trae",
        display_name="Trae (字节跳动)",
        authorization_url_template="https://account.feishu.cn/open-apis/authen/v1/authorize",
        token_url_template="https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal",
        default_scope="openid",
        notes=(
            "ByteDance Trae / Lark open-platform OAuth skeleton. Verify the endpoint contracts "
            "against official documentation before enabling this provider."
        ),
        api_base_url="",
        default_transport="openai_chat_completions",
        models_endpoint="",
        requires_base_url=True,
        auth_mode="custom_callback",
        is_enabled=False,
    ),
    "codex": OAuthProviderProfile(
        key="codex",
        display_name="OpenAI / Codex",
        authorization_url_template="https://auth.openai.com/authorize",
        token_url_template="https://auth.openai.com/oauth/token",
        default_scope="openid offline_access",
        notes=(
            "OpenAI Codex provider skeleton. Configure OAUTH_CODEX_CLIENT_ID / SECRET and verify "
            "the current OAuth endpoints against official OpenAI documentation before enabling it."
        ),
        api_base_url="https://api.openai.com/v1",
        default_transport="openai_chat_completions",
        models_endpoint="https://api.openai.com/v1/models",
        models_response_path="data",
        model_id_field="id",
        auth_mode="custom_callback",
        is_enabled=False,
    ),
    "generic": OAuthProviderProfile(
        key="generic",
        display_name="通用 OAuth 2.0",
        authorization_url_template="",
        token_url_template="",
        default_scope="",
        notes="Manual configuration for any RFC 6749-compliant OAuth 2.0 provider.",
        requires_base_url=True,
        auth_mode="standard_oauth",
        is_enabled=False,
    ),
}


def get_profile(key: str) -> OAuthProviderProfile | None:
    return _PROFILES.get(key)


def resolve_url(template: str, tenant_id: str | None = None) -> str:
    if "{tenant_id}" in template:
        return template.replace("{tenant_id}", (tenant_id or "common").strip() or "common")
    return template


def list_profiles() -> list[dict]:
    return [
        {
            "key": p.key,
            "display_name": p.display_name,
            "authorization_url_template": p.authorization_url_template,
            "token_url_template": p.token_url_template,
            "default_scope": p.default_scope,
            "extra_auth_params": dict(p.extra_auth_params),
            "notes": p.notes,
            "api_base_url": p.api_base_url,
            "default_transport": p.default_transport,
            "has_model_listing": bool(p.models_endpoint),
            "requires_base_url": p.requires_base_url,
            "auth_mode": p.auth_mode,
            "supports_manual_model_name": p.supports_manual_model_name,
            "is_enabled": p.is_enabled,
        }
        for p in _PROFILES.values()
    ]
