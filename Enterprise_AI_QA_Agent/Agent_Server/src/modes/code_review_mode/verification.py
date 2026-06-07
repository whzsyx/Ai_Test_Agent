from __future__ import annotations

CODE_REVIEW_VERIFICATION = {
    "policy": "governance_score_and_debated_structured_findings_required",
    "required_governance_metadata": ["decision", "risk_score", "findings", "changed_files"],
    "required_result_sections": ["serious_issue", "defect", "risk", "feasible", "excellent"],
    "required_metadata": ["proposer_agent", "supporting_agents", "challenging_agents", "evidence_refs"],
}
