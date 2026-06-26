"""Local failure analysis helpers for performance testing."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class PerfFailureAnalysis:
    failure_category: str
    root_cause: str
    retryable: bool
    suggested_fix: str
    suggested_degradation: dict[str, Any] | None = None

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


class PerfFailureAnalyzer:
    """Heuristic fallback analyzer used when no failure analyst agent is available."""

    def analyze(self, payload: dict[str, Any]) -> PerfFailureAnalysis:
        text = " ".join(str(v) for v in payload.values()).lower()

        if any(sig in text for sig in ["401", "403", "unauthorized", "forbidden"]):
            return PerfFailureAnalysis(
                failure_category="auth_failure",
                root_cause="目标返回认证或授权失败。",
                retryable=False,
                suggested_fix="补充有效 token、cookie 或认证配置后重新执行。",
            )

        if any(sig in text for sig in ["connection refused", "connectex", "econnrefused"]):
            return PerfFailureAnalysis(
                failure_category="connection_refused",
                root_cause="目标主机或端口拒绝连接。",
                retryable=False,
                suggested_fix="确认服务已启动、端口可达、Docker localhost 重写配置正确。",
            )

        if any(sig in text for sig in ["no such host", "name resolution", "dns"]):
            return PerfFailureAnalysis(
                failure_category="dns_resolve",
                root_cause="目标域名无法解析。",
                retryable=False,
                suggested_fix="检查目标 URL、DNS、VPN 或容器网络配置。",
            )

        if any(sig in text for sig in ["timeout", "timed out", "context deadline"]):
            return PerfFailureAnalysis(
                failure_category="timeout",
                root_cause="执行超时或目标响应超时。",
                retryable=True,
                suggested_fix="降低负载或延长超时时间后重试。",
                suggested_degradation={"target_rate_rps_factor": 0.5, "virtual_users_factor": 0.5},
            )

        if any(sig in text for sig in ["syntaxerror", "referenceerror", "xml", "jmx"]):
            return PerfFailureAnalysis(
                failure_category="script_error",
                root_cause="性能测试脚本或 JMX 文件存在生成/解析错误。",
                retryable=False,
                suggested_fix="修复脚本生成逻辑后重新执行。",
            )

        if any(sig in text for sig in ["out of memory", "oom", "too many open files", "resource"]):
            return PerfFailureAnalysis(
                failure_category="resource_exhausted",
                root_cause="压测执行端或目标端资源不足。",
                retryable=True,
                suggested_fix="降低 VU/RPS 或增加 runner 资源后重试。",
                suggested_degradation={"target_rate_rps_factor": 0.5, "virtual_users_factor": 0.5},
            )

        if "allowlist" in text or "护栏" in text or "禁止" in text:
            return PerfFailureAnalysis(
                failure_category="guard_blocked",
                root_cause="安全护栏阻止了本次压测。",
                retryable=False,
                suggested_fix="确认目标范围并配置 allowlist，或降低超过硬上限的负载参数。",
            )

        return PerfFailureAnalysis(
            failure_category="unknown",
            root_cause="未能从现有日志中确定明确失败原因。",
            retryable=True,
            suggested_fix="保留原始 stdout/stderr，建议人工确认后重试。",
        )
