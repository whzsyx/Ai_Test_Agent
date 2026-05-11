"""Map endpoints to coarse business capabilities.

Deterministic rules first (method + path + summary keywords), falling back
to ``unknown`` when no rule fires. A future extension can call the LLM for
ambiguous cases, but the first version stays rule-based to keep behavior
predictable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from src.modes.api_testing_mode.campaign_state import EndpointCandidate


# ---------------------------------------------------------------------------
# Capability inventory
# ---------------------------------------------------------------------------

CAP_LOGIN = "login"
CAP_LOGOUT = "logout"
CAP_REFRESH_TOKEN = "refresh_token"
CAP_REGISTER = "register"
CAP_LIST = "list"
CAP_DETAIL = "detail"
CAP_SEARCH = "search"
CAP_CREATE = "create"
CAP_UPDATE = "update"
CAP_DELETE = "delete"
CAP_PAY = "pay"
CAP_CANCEL = "cancel"
CAP_APPROVE = "approve"
CAP_EXPORT = "export"
CAP_UPLOAD = "upload"
CAP_DOWNLOAD = "download"
CAP_UNKNOWN = "unknown"


# Capabilities considered "core" (included by default under core_only scope).
CORE_CAPABILITIES = frozenset(
    {
        CAP_LOGIN,
        CAP_LIST,
        CAP_DETAIL,
        CAP_CREATE,
        CAP_SEARCH,
    }
)


# Capabilities that typically create or mutate state.
WRITE_CAPABILITIES = frozenset(
    {
        CAP_LOGIN,
        CAP_LOGOUT,
        CAP_REFRESH_TOKEN,
        CAP_REGISTER,
        CAP_CREATE,
        CAP_UPDATE,
        CAP_DELETE,
        CAP_PAY,
        CAP_CANCEL,
        CAP_APPROVE,
        CAP_UPLOAD,
    }
)


_PATH_PATTERNS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"/(login|sign[_-]?in)(/|$)", re.IGNORECASE), "POST", CAP_LOGIN),
    (re.compile(r"/(login|sign[_-]?in)(/|$)", re.IGNORECASE), "PUT", CAP_LOGIN),
    (re.compile(r"/(logout|sign[_-]?out)(/|$)", re.IGNORECASE), "", CAP_LOGOUT),
    (re.compile(r"/(register|signup|sign[_-]?up)(/|$)", re.IGNORECASE), "", CAP_REGISTER),
    (re.compile(r"/(refresh[_-]?token|token/refresh|auth/refresh)", re.IGNORECASE), "", CAP_REFRESH_TOKEN),
    (re.compile(r"/(oauth|token)(/|$)", re.IGNORECASE), "POST", CAP_LOGIN),
    (re.compile(r"/pay(ment)?(/|$)", re.IGNORECASE), "", CAP_PAY),
    (re.compile(r"/cancel(/|$)", re.IGNORECASE), "", CAP_CANCEL),
    (re.compile(r"/approve(/|$)", re.IGNORECASE), "", CAP_APPROVE),
    (re.compile(r"/export(/|$)", re.IGNORECASE), "", CAP_EXPORT),
    (re.compile(r"/upload(/|$)", re.IGNORECASE), "", CAP_UPLOAD),
    (re.compile(r"/download(/|$)", re.IGNORECASE), "", CAP_DOWNLOAD),
    (re.compile(r"/search(/|$)", re.IGNORECASE), "", CAP_SEARCH),
    (re.compile(r"/(query|find|filter)(/|$)", re.IGNORECASE), "GET", CAP_SEARCH),
]


_SUMMARY_KEYWORDS: list[tuple[str, str]] = [
    ("登录", CAP_LOGIN),
    ("退出", CAP_LOGOUT),
    ("登出", CAP_LOGOUT),
    ("注册", CAP_REGISTER),
    ("刷新", CAP_REFRESH_TOKEN),
    ("新增", CAP_CREATE),
    ("创建", CAP_CREATE),
    ("提交", CAP_CREATE),
    ("下单", CAP_CREATE),
    ("修改", CAP_UPDATE),
    ("更新", CAP_UPDATE),
    ("编辑", CAP_UPDATE),
    ("删除", CAP_DELETE),
    ("取消", CAP_CANCEL),
    ("审批", CAP_APPROVE),
    ("支付", CAP_PAY),
    ("付款", CAP_PAY),
    ("导出", CAP_EXPORT),
    ("上传", CAP_UPLOAD),
    ("下载", CAP_DOWNLOAD),
    ("查询", CAP_SEARCH),
    ("搜索", CAP_SEARCH),
    ("列表", CAP_LIST),
    ("详情", CAP_DETAIL),
]


@dataclass
class MappedEndpoint:
    endpoint: EndpointCandidate
    capability: str
    is_core: bool
    is_write: bool
    is_auth: bool


class CapabilityMapper:
    """Classify endpoints into coarse business capabilities."""

    def map_many(self, endpoints: Iterable[EndpointCandidate]) -> list[MappedEndpoint]:
        return [self.map_single(endpoint) for endpoint in endpoints]

    def map_single(self, endpoint: EndpointCandidate) -> MappedEndpoint:
        capability = self._detect_capability(endpoint)
        endpoint.capability = capability
        is_core = capability in CORE_CAPABILITIES
        is_write = capability in WRITE_CAPABILITIES or endpoint.method.upper() in {
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
        }
        is_auth = capability in {CAP_LOGIN, CAP_REFRESH_TOKEN}
        return MappedEndpoint(
            endpoint=endpoint,
            capability=capability,
            is_core=is_core,
            is_write=is_write,
            is_auth=is_auth,
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _detect_capability(self, endpoint: EndpointCandidate) -> str:
        method = endpoint.method.upper()
        path = endpoint.path or ""

        # 1. Path-based rules
        for pattern, required_method, capability in _PATH_PATTERNS:
            if required_method and required_method.upper() != method:
                continue
            if pattern.search(path):
                return capability

        # 2. Summary keyword rules
        summary_lower = (endpoint.summary or "").lower()
        for keyword, capability in _SUMMARY_KEYWORDS:
            if keyword.lower() in summary_lower:
                return capability

        # 3. Method + path shape heuristics
        if method == "GET":
            if re.search(r"\{[a-zA-Z_]+\}", path) or re.search(r"/\d+(/|$)", path):
                return CAP_DETAIL
            return CAP_LIST
        if method == "POST":
            return CAP_CREATE
        if method in {"PUT", "PATCH"}:
            return CAP_UPDATE
        if method == "DELETE":
            return CAP_DELETE
        return CAP_UNKNOWN


__all__ = [
    "CapabilityMapper",
    "MappedEndpoint",
    "CORE_CAPABILITIES",
    "WRITE_CAPABILITIES",
    "CAP_LOGIN",
    "CAP_LOGOUT",
    "CAP_REFRESH_TOKEN",
    "CAP_REGISTER",
    "CAP_LIST",
    "CAP_DETAIL",
    "CAP_SEARCH",
    "CAP_CREATE",
    "CAP_UPDATE",
    "CAP_DELETE",
    "CAP_PAY",
    "CAP_CANCEL",
    "CAP_APPROVE",
    "CAP_EXPORT",
    "CAP_UPLOAD",
    "CAP_DOWNLOAD",
    "CAP_UNKNOWN",
]
