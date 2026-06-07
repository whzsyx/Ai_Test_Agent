from __future__ import annotations

CODE_REVIEW_EVALUATION = {
    "policy": "governance_prescan_plus_debate_resolution",
    "stages": [
        "governance_prescan",
        "independent_findings",
        "cross_review",
        "summary_resolution",
        "risk_scoring",
        "approval_decision",
    ],
    "blocking_policy": {
        "minimum_score": 80,
        "block_on_critical": True,
        "block_on_high_security": True,
        "block_on_secret": True,
    },
}
