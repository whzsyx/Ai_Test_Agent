"""Severity Evaluator for security findings.

Computes a unified severity level based on impact, exploitability,
confidence, and contextual factors.
"""
from __future__ import annotations

from src.modes.security_testing_mode.campaign_state import FindingRecord
from src.modes.security_testing_mode.contracts import (
    RISK_CRITICAL,
    RISK_HIGH,
    RISK_INFO,
    RISK_LOW,
    RISK_MEDIUM,
    SEVERITY_ORDER,
)


class SeverityEvaluator:
    """Evaluate and assign severity levels to security findings."""

    def evaluate(self, finding: FindingRecord) -> dict[str, any]:
        """Evaluate a finding and return severity details.

        Returns a dict with:
            - severity: final severity level
            - score: numeric score (0-10)
            - impact_score: impact component
            - exploitability_score: exploitability component
            - confidence_score: confidence component
            - rationale: explanation
        """
        impact = self._score_impact(finding)
        exploitability = self._score_exploitability(finding)
        confidence = self._score_confidence(finding)

        # Weighted composite score
        raw_score = (impact * 0.45) + (exploitability * 0.35) + (confidence * 0.20)

        # If CVSS is provided, blend with it
        if finding.cvss_score is not None and finding.cvss_score > 0:
            raw_score = (raw_score * 0.4) + (finding.cvss_score * 0.6)

        severity = self._score_to_severity(raw_score)
        rationale = self._build_rationale(finding, impact, exploitability, confidence, raw_score)

        return {
            "severity": severity,
            "score": round(raw_score, 1),
            "impact_score": round(impact, 1),
            "exploitability_score": round(exploitability, 1),
            "confidence_score": round(confidence, 1),
            "rationale": rationale,
        }

    def _score_impact(self, finding: FindingRecord) -> float:
        """Score the potential impact (0-10)."""
        score = 3.0  # baseline

        # Category-based impact
        category_scores = {
            "vulnerability": 6.0,
            "weak_credential": 7.0,
            "misconfiguration": 4.0,
            "information_disclosure": 3.0,
            "missing_control": 4.5,
            "outdated_software": 5.0,
        }
        score = category_scores.get(finding.category, score)

        # Adjust by surface type
        if finding.surface_type in ("web", "api"):
            score += 1.0
        elif finding.surface_type == "credential":
            score += 1.5

        # Adjust by keywords in title/description
        high_impact_keywords = [
            "rce", "remote code execution", "sql injection", "authentication bypass",
            "privilege escalation", "arbitrary file", "command injection",
            "deserialization", "ssrf", "xxe",
        ]
        text = f"{finding.title} {finding.description}".lower()
        for keyword in high_impact_keywords:
            if keyword in text:
                score += 1.5
                break

        medium_impact_keywords = [
            "xss", "cross-site", "csrf", "open redirect", "path traversal",
            "directory listing", "information leak", "sensitive data",
        ]
        for keyword in medium_impact_keywords:
            if keyword in text:
                score += 0.8
                break

        return min(10.0, max(0.0, score))

    def _score_exploitability(self, finding: FindingRecord) -> float:
        """Score how easy it is to exploit (0-10)."""
        score = 5.0  # baseline

        # If verified, it's clearly exploitable
        if finding.verified:
            score += 2.0

        # Remote vs local
        text = f"{finding.title} {finding.description}".lower()
        if "remote" in text or "unauthenticated" in text:
            score += 1.5
        if "authenticated" in text or "local" in text:
            score -= 1.0

        # Complexity indicators
        if "no authentication" in text or "default credential" in text:
            score += 2.0
        if "complex" in text or "race condition" in text:
            score -= 1.5

        # Has reproduction steps
        if finding.reproduction_steps:
            score += 1.0

        return min(10.0, max(0.0, score))

    def _score_confidence(self, finding: FindingRecord) -> float:
        """Score confidence in the finding (0-10)."""
        confidence_map = {
            "confirmed": 9.0,
            "high": 8.0,
            "medium": 6.0,
            "low": 3.0,
        }
        score = confidence_map.get(finding.confidence, 5.0)

        # Verified findings get a boost
        if finding.verified:
            score = max(score, 8.5)

        # False positive flag
        if finding.false_positive:
            score = 1.0

        # Has evidence
        if finding.evidence_summary:
            score += 0.5
        if finding.raw_evidence:
            score += 0.5

        return min(10.0, max(0.0, score))

    def _score_to_severity(self, score: float) -> str:
        """Convert numeric score to severity level."""
        if score >= 9.0:
            return RISK_CRITICAL
        elif score >= 7.0:
            return RISK_HIGH
        elif score >= 4.0:
            return RISK_MEDIUM
        elif score >= 2.0:
            return RISK_LOW
        else:
            return RISK_INFO

    def _build_rationale(
        self,
        finding: FindingRecord,
        impact: float,
        exploitability: float,
        confidence: float,
        score: float,
    ) -> str:
        """Build a human-readable rationale for the severity."""
        parts = []
        parts.append(f"综合评分 {score:.1f}/10")
        parts.append(f"影响 {impact:.1f}")
        parts.append(f"可利用性 {exploitability:.1f}")
        parts.append(f"置信度 {confidence:.1f}")
        if finding.cvss_score:
            parts.append(f"CVSS {finding.cvss_score}")
        if finding.verified:
            parts.append("已验证")
        return " | ".join(parts)

    def evaluate_batch(self, findings: list[FindingRecord]) -> list[FindingRecord]:
        """Evaluate and update severity for a batch of findings."""
        for finding in findings:
            result = self.evaluate(finding)
            finding.severity = result["severity"]
        return findings


__all__ = ["SeverityEvaluator"]
