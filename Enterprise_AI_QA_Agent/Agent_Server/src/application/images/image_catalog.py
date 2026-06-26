"""Image capability catalog for controlled image management.

Images are structured as capability units, not raw strings.
The model selects high-level capabilities; the resolver maps
them to concrete Docker images via this catalog.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ImageConstraints:
    requires_gui: bool = False
    supports_complex_recording: bool = False
    supports_data_csv: bool = False
    supports_correlation: bool = False


@dataclass(frozen=True)
class CatalogImageEntry:
    """A single image entry in the controlled catalog."""

    image_key: str
    image: str
    version: str = "latest"
    domain: str = "performance"
    engine_keys: list[str] = field(default_factory=list)
    scenarios: list[str] = field(default_factory=list)
    description: str = ""
    capabilities: list[str] = field(default_factory=list)
    constraints: ImageConstraints = field(default_factory=ImageConstraints)
    risk_level: str = "low"
    pull_policy: str = "if_not_present"
    enabled: bool = True
    priority: int = 0
    fallback_keys: list[str] = field(default_factory=list)

    def matches_scenario(self, scenario: str) -> bool:
        scenario_lower = scenario.lower().strip()
        return any(scenario_lower == s.lower() or scenario_lower in s.lower() or s.lower() in scenario_lower
                    for s in self.scenarios)

    def matches_engine(self, engine: str | None) -> bool:
        if not engine:
            return True
        return engine.lower() in [e.lower() for e in self.engine_keys]

    def model_dump(self) -> dict[str, Any]:
        return {
            "image_key": self.image_key,
            "image": self.image,
            "version": self.version,
            "domain": self.domain,
            "engine_keys": list(self.engine_keys),
            "scenarios": list(self.scenarios),
            "description": self.description,
            "capabilities": list(self.capabilities),
            "constraints": {
                "requires_gui": self.constraints.requires_gui,
                "supports_complex_recording": self.constraints.supports_complex_recording,
                "supports_data_csv": self.constraints.supports_data_csv,
                "supports_correlation": self.constraints.supports_correlation,
            },
            "risk_level": self.risk_level,
            "pull_policy": self.pull_policy,
            "enabled": self.enabled,
            "priority": self.priority,
            "fallback_keys": list(self.fallback_keys),
        }


def _default_catalog() -> list[CatalogImageEntry]:
    """Build the default controlled image catalog."""
    return [
        CatalogImageEntry(
            image_key="perf_k6_default",
            image="grafana/k6:latest",
            version="latest",
            domain="performance",
            engine_keys=["k6"],
            scenarios=["api_baseline", "api_regression", "ci_load", "smoke", "probe"],
            description="适合 API 基线、回归和 CI 自动化，轻量、快速、原生 threshold 支持",
            capabilities=["http_load", "thresholds", "summary_export", "abort_on_fail", "data_csv"],
            constraints=ImageConstraints(
                requires_gui=False,
                supports_complex_recording=False,
                supports_data_csv=True,
                supports_correlation=False,
            ),
            risk_level="low",
            pull_policy="if_not_present",
            enabled=True,
            priority=100,
            fallback_keys=[],
        ),
        CatalogImageEntry(
            image_key="perf_jmeter_default",
            image="alpine/jmeter:5.6.3",
            version="5.6.3",
            domain="performance",
            engine_keys=["jmeter"],
            scenarios=["complex_flow", "jmx_reuse", "multi_transaction", "spike", "soak"],
            description="适合复杂业务流程、JMX 资产复用和多事务混合压测",
            capabilities=["http_load", "thresholds", "html_report", "data_csv", "correlation", "beanshell"],
            constraints=ImageConstraints(
                requires_gui=False,
                supports_complex_recording=True,
                supports_data_csv=True,
                supports_correlation=True,
            ),
            risk_level="low",
            pull_policy="if_not_present",
            enabled=True,
            priority=90,
            fallback_keys=[],
        ),
        CatalogImageEntry(
            image_key="helper_http_probe",
            image="curlimages/curl:8.8.0",
            version="8.8.0",
            domain="helper",
            engine_keys=[],
            scenarios=["connectivity_check", "health_probe", "response_header_check", "pre_check"],
            description="连通性检查、健康探针、响应头检查的 helper 镜像",
            capabilities=["http_get", "http_post", "headers", "timeout"],
            constraints=ImageConstraints(),
            risk_level="low",
            pull_policy="if_not_present",
            enabled=True,
            priority=50,
            fallback_keys=[],
        ),
        CatalogImageEntry(
            image_key="helper_mock_target",
            image="hashicorp/http-echo:1.0.0",
            version="1.0.0",
            domain="helper",
            engine_keys=[],
            scenarios=["local_link_verify", "mock_target", "circuit_validation"],
            description="本地 mock target、压测链路验证的临时 HTTP 回显靶机",
            capabilities=["http_echo", "custom_response"],
            constraints=ImageConstraints(),
            risk_level="low",
            pull_policy="if_not_present",
            enabled=True,
            priority=40,
            fallback_keys=[],
        ),
    ]


class ImageCatalog:
    """Controlled image catalog with domain/scenario filtering and fallback."""

    def __init__(self, entries: list[CatalogImageEntry] | None = None) -> None:
        self._entries: dict[str, CatalogImageEntry] = {}
        for entry in (entries or _default_catalog()):
            self._entries[entry.image_key] = entry

    def get(self, image_key: str) -> CatalogImageEntry | None:
        return self._entries.get(image_key)

    def list_entries(self, domain: str | None = None) -> list[CatalogImageEntry]:
        entries = [e for e in self._entries.values() if e.enabled]
        if domain:
            entries = [e for e in entries if e.domain == domain]
        return sorted(entries, key=lambda e: e.priority, reverse=True)

    def find_by_scenario(
        self,
        scenario: str,
        *,
        domain: str | None = None,
        engine: str | None = None,
    ) -> list[CatalogImageEntry]:
        candidates = self.list_entries(domain=domain)
        matched = [e for e in candidates if e.matches_scenario(scenario) and e.matches_engine(engine)]
        if not matched and engine:
            matched = [e for e in candidates if e.matches_scenario(scenario)]
        return sorted(matched, key=lambda e: e.priority, reverse=True)

    def find_fallbacks(self, image_key: str) -> list[CatalogImageEntry]:
        entry = self.get(image_key)
        if not entry:
            return []
        result: list[CatalogImageEntry] = []
        for fk in entry.fallback_keys:
            fe = self.get(fk)
            if fe and fe.enabled:
                result.append(fe)
        return result

    def validate(self) -> list[str]:
        errors: list[str] = []
        for entry in self._entries.values():
            if not entry.image_key:
                errors.append(f"entry missing image_key: {entry}")
            if not entry.scenarios:
                errors.append(f"entry {entry.image_key} has no scenarios")
            if not entry.description:
                errors.append(f"entry {entry.image_key} has no description")
        return errors
