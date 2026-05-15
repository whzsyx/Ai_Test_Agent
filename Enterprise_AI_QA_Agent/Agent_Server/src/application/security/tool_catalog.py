"""Security Tool Catalog.

Maps PentAGI tool families to system runner keys and command profiles.
"""
from __future__ import annotations

from src.application.security.command_profiles import get_profile_registry


# Surface type → recommended tool families
SURFACE_FAMILY_MAP: dict[str, list[str]] = {
    "network": ["network_recon"],
    "host": ["network_recon", "service_audit"],
    "web": ["web_scan", "service_audit"],
    "api": ["web_scan"],
    "credential": ["credential_attack"],
    "service": ["service_audit", "network_recon"],
}

# Tool family → runner key
FAMILY_RUNNER_MAP: dict[str, str] = {
    "network_recon": "network-recon-runner",
    "web_scan": "web-scan-runner",
    "service_audit": "service-audit-runner",
    "credential_attack": "credential-attack-runner",
    "traffic_analysis": "traffic-analysis-runner",
    "exploit": "exploit-workbench-runner",
    "general_scan": "security-scan-runner",
}


class SecurityToolCatalog:
    """Catalog of security tools and their profiles."""

    def list_profiles(self, tool_family: str) -> list[dict]:
        registry = get_profile_registry()
        profiles = registry.list_by_family(tool_family)
        return [
            {
                "profile_key": p.profile_key,
                "tool_name": p.tool_name,
                "description": p.description,
                "risk_level": p.risk_level,
                "requires_approval": p.requires_approval,
                "timeout_seconds": p.timeout_seconds,
            }
            for p in profiles
        ]

    def get_profile(self, profile_key: str):
        return get_profile_registry().get(profile_key)

    def resolve_family_for_surface(self, surface_type: str) -> list[str]:
        return SURFACE_FAMILY_MAP.get(surface_type, ["general_scan"])

    def resolve_runner_for_family(self, tool_family: str) -> str:
        return FAMILY_RUNNER_MAP.get(tool_family, "security-scan-runner")

    def suggest_profiles_for_target(
        self, surface_type: str, target: str
    ) -> list[str]:
        """Suggest profile keys for a given surface type and target."""
        families = self.resolve_family_for_surface(surface_type)
        registry = get_profile_registry()
        suggestions: list[str] = []
        for family in families:
            profiles = registry.list_by_family(family)
            for p in profiles:
                if not p.requires_approval:
                    suggestions.append(p.profile_key)
        return suggestions


__all__ = ["SecurityToolCatalog", "SURFACE_FAMILY_MAP", "FAMILY_RUNNER_MAP"]
