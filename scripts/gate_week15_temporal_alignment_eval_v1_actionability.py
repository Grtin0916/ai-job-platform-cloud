#!/usr/bin/env python3
import json
import re
from datetime import datetime, timezone
from pathlib import Path

TAXONOMY = Path("loadtest/reports/week15_temporal_alignment_eval_v1_risk_taxonomy.json")
OUT = Path("loadtest/reports/week15_temporal_alignment_eval_v1_actionability_gate.json")
PROM = Path("observability/prometheus/week15_temporal_alignment_eval_v1_actionability_metrics.prom")

def safe_label(s):
    return re.sub(r"[^a-zA-Z0-9_:\-.]", "_", str(s))[:160]

data = json.loads(TAXONOMY.read_text(encoding="utf-8"))
candidates = data.get("candidates") or []

actionable = []
non_actionable = []
unknown = []

for c in candidates:
    cid = c.get("candidateId")
    primary = c.get("primaryRiskClass")
    classes = c.get("riskClasses") or []

    if primary == "remediation_or_drift":
        actionable.append(cid)
    elif primary == "mentioned_only":
        non_actionable.append(cid)
    else:
        unknown.append(cid)

failures = []
if data.get("decision") != "PASS":
    failures.append("SOURCE_TAXONOMY_NOT_PASS")
if not actionable:
    failures.append("NO_ACTIONABLE_RISK_CANDIDATES")
if unknown:
    failures.append("UNKNOWN_RISK_ACTIONABILITY_CLASS")

decision = (
    "PASS_ACTIONABILITY_GATE_WITH_PROXY_RISK_EXCLUDED"
    if not failures
    else "FAIL_ACTIONABILITY_GATE"
)

report = {
    "schemaVersion": "week15.temporal_alignment.eval_v1_actionability_gate.v1",
    "generatedAt": datetime.now(timezone.utc).isoformat(),
    "scope": "offline repository evidence actionability gate; no human-review or production alert claim",
    "decision": decision,
    "failures": failures,
    "sourceTaxonomy": str(TAXONOMY),
    "actionableRiskCandidateIds": actionable,
    "nonActionableMentionedOnlyCandidateIds": non_actionable,
    "unknownRiskCandidateIds": unknown,
    "actionableRiskCount": len(actionable),
    "nonActionableMentionedOnlyCount": len(non_actionable),
    "unknownRiskCount": len(unknown),
    "policy": {
        "remediation_or_drift": "actionable",
        "mentioned_only": "non_actionable_context",
        "other": "unknown_requires_schema_refinement"
    },
    "nextAction": (
        "Use actionability metrics as dashboard dimensions; do not alert on mentioned_only candidates."
        if not failures
        else "Refine risk taxonomy schema before dashboard consumption."
    )
}

OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

lines = [
    "# HELP week15_temporal_alignment_eval_v1_actionability_gate_pass Actionability gate pass flag.",
    "# TYPE week15_temporal_alignment_eval_v1_actionability_gate_pass gauge",
    f'week15_temporal_alignment_eval_v1_actionability_gate_pass{{decision="{safe_label(decision)}"}} {1 if not failures else 0}',
    "# HELP week15_temporal_alignment_eval_v1_risk_candidate_by_actionability Candidate risk count by actionability.",
    "# TYPE week15_temporal_alignment_eval_v1_risk_candidate_by_actionability gauge",
    f'week15_temporal_alignment_eval_v1_risk_candidate_by_actionability{{actionability="actionable"}} {len(actionable)}',
    f'week15_temporal_alignment_eval_v1_risk_candidate_by_actionability{{actionability="non_actionable_mentioned_only"}} {len(non_actionable)}',
    f'week15_temporal_alignment_eval_v1_risk_candidate_by_actionability{{actionability="unknown"}} {len(unknown)}',
]

PROM.write_text("\n".join(lines) + "\n", encoding="utf-8")

print(json.dumps({
    "decision": decision,
    "failures": failures,
    "actionableRiskCandidateIds": actionable,
    "nonActionableMentionedOnlyCandidateIds": non_actionable,
    "unknownRiskCandidateIds": unknown,
    "out": str(OUT),
    "prom": str(PROM)
}, indent=2, ensure_ascii=False))

if failures:
    raise SystemExit("ACTIONABILITY_GATE_FAIL")
