"""Security Testing Mode agent key constants."""
from __future__ import annotations


# Primary orchestrator
SECURITY_TESTING_AGENT_KEY = "security-testing-agent"

# Specialist workers
SECURITY_DOC_ANALYST_KEY = "security-doc-analyst"
ATTACK_SURFACE_PLANNER_KEY = "attack-surface-planner"
SECURITY_RECON_WORKER_KEY = "security-recon-worker"
SECURITY_AUTH_WORKER_KEY = "security-auth-worker"
SECURITY_WEB_VERIFIER_KEY = "security-web-verifier"
SECURITY_API_VERIFIER_KEY = "security-api-verifier"
SECURITY_HOST_VERIFIER_KEY = "security-host-verifier"
SECURITY_EXPLOIT_CODER_KEY = "security-exploit-coder"
SECURITY_FAILURE_ANALYST_KEY = "security-failure-analyst"

# Surface type to worker mapping
SURFACE_WORKER_MAP: dict[str, str] = {
    "network": SECURITY_RECON_WORKER_KEY,
    "host": SECURITY_HOST_VERIFIER_KEY,
    "web": SECURITY_WEB_VERIFIER_KEY,
    "api": SECURITY_API_VERIFIER_KEY,
    "credential": SECURITY_AUTH_WORKER_KEY,
    "service": SECURITY_HOST_VERIFIER_KEY,
}


__all__ = [
    "SECURITY_TESTING_AGENT_KEY",
    "SECURITY_DOC_ANALYST_KEY",
    "ATTACK_SURFACE_PLANNER_KEY",
    "SECURITY_RECON_WORKER_KEY",
    "SECURITY_AUTH_WORKER_KEY",
    "SECURITY_WEB_VERIFIER_KEY",
    "SECURITY_API_VERIFIER_KEY",
    "SECURITY_HOST_VERIFIER_KEY",
    "SECURITY_EXPLOIT_CODER_KEY",
    "SECURITY_FAILURE_ANALYST_KEY",
    "SURFACE_WORKER_MAP",
]
