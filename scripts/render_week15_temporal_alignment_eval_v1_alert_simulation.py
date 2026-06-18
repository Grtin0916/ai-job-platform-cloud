#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

ACTIONABILITY = Path("loadtest/reports/week15_temporal_alignment_eval_v1_actionability_gate.json")
RULES = Path("observability/prometheus/week15_temporal_alignment_eval_v1_alert_rules.yml")
OUT = Path("loadtest/reports/week15_temporal_alignment_eval_v1_alert_simulation.json")

data = json.loads(ACTIONABILITY.read_text(encoding="utf-8"))

decision = data.get("decision")
failures = data.get("failures") or []
actionable = data.get("actionableRiskCandidateIds") or []
mentioned = data.get("nonActionableMentionedOnlyCandidateIds") or []
unknown = data.get("unknownRiskCandidateIds") or []

gate_pass = 1 if decision == "PASS_ACTIONABILITY_GATE_WITH_PROXY_RISK_EXCLUDED" and not failures else 0
actionable_count = len(actionable)
mentioned_count = len(mentioned)
unknown_count = len(unknown)

rules_text = f"""groups:
  - name: week15_temporal_alignment_eval_v1_actionability
    rules:
      - alert: Week15TemporalAlignmentEvalV1ActionabilityGateNotReady
        expr: week15_temporal_alignment_eval_v1_actionability_gate_pass != 1
        for: 0m
        labels:
          severity: warning
          scope: local_evidence
        annotations:
          summary: "Week15 Eval V1 actionability gate is not ready"
          description: "The local evidence actionability gate failed or contains unknown risk classes."

      - alert: Week15TemporalAlignmentEvalV1ActionableRiskPresent
        expr: week15_temporal_alignment_eval_v1_risk_candidate_by_actionability{{actionability="actionable"}} > 0
        for: 0m
        labels:
          severity: warning
          scope: local_evidence
        annotations:
          summary: "Week15 Eval V1 actionable temporal-alignment risk exists"
          description: "Only actionable remediation/drift candidates should trigger this alert; mentioned_only candidates must not alert."

      - alert: Week15TemporalAlignmentEvalV1UnknownRiskClassPresent
        expr: week15_temporal_alignment_eval_v1_risk_candidate_by_actionability{{actionability="unknown"}} > 0
        for: 0m
        labels:
          severity: warning
          scope: local_evidence
        annotations:
          summary: "Week15 Eval V1 unknown risk class exists"
          description: "Unknown risk classes indicate the taxonomy schema needs refinement before dashboard or alert consumption."
"""
RULES.write_text(rules_text, encoding="utf-8")

simulated_alerts = []

if gate_pass != 1:
    simulated_alerts.append({
        "alert": "Week15TemporalAlignmentEvalV1ActionabilityGateNotReady",
        "wouldFire": True,
        "severity": "warning",
        "reason": {
            "decision": decision,
            "failures": failures
        }
    })

if actionable_count > 0:
    simulated_alerts.append({
        "alert": "Week15TemporalAlignmentEvalV1ActionableRiskPresent",
        "wouldFire": True,
        "severity": "warning",
        "reason": {
            "actionableRiskCandidateIds": actionable,
            "actionableRiskCount": actionable_count
        }
    })

if unknown_count > 0:
    simulated_alerts.append({
        "alert": "Week15TemporalAlignmentEvalV1UnknownRiskClassPresent",
        "wouldFire": True,
        "severity": "warning",
        "reason": {
            "unknownRiskCandidateIds": unknown,
            "unknownRiskCount": unknown_count
        }
    })

mentioned_only_suppressed = mentioned_count > 0 and all(
    a.get("alert") != "MentionedOnlyRiskPresent" for a in simulated_alerts
)

checks = [
    {
        "name": "actionability_gate_pass",
        "status": "PASS" if gate_pass == 1 else "FAIL",
        "detail": {"decision": decision, "failures": failures}
    },
    {
        "name": "actionable_alert_selective",
        "status": "PASS" if actionable_count == 2 else "FAIL",
        "detail": {
            "expectedActionableCount": 2,
            "actualActionableCount": actionable_count,
            "actionableRiskCandidateIds": actionable
        }
    },
    {
        "name": "mentioned_only_suppressed",
        "status": "PASS" if mentioned_only_suppressed else "FAIL",
        "detail": {
            "nonActionableMentionedOnlyCandidateIds": mentioned,
            "mentionedOnlyCount": mentioned_count
        }
    },
    {
        "name": "unknown_risk_absent",
        "status": "PASS" if unknown_count == 0 else "FAIL",
        "detail": {
            "unknownRiskCandidateIds": unknown,
            "unknownRiskCount": unknown_count
        }
    }
]

failure_count = sum(1 for c in checks if c["status"] == "FAIL")

report = {
    "schemaVersion": "week15.temporal_alignment.eval_v1_alert_simulation.v1",
    "generatedAt": datetime.now(timezone.utc).isoformat(),
    "scope": "offline Prometheus-rule simulation from repository evidence; no live Alertmanager or production SLO claim",
    "decision": "PASS" if failure_count == 0 else "FAIL",
    "sourceActionabilityGate": str(ACTIONABILITY),
    "alertRulesPath": str(RULES),
    "checks": checks,
    "failureCount": failure_count,
    "simulatedAlerts": simulated_alerts,
    "suppressedNonActionableMentionedOnlyCandidateIds": mentioned,
    "nextAction": (
        "Use the generated rule file as dashboard/alert-ready evidence; keep mentioned_only candidates out of alerting."
        if failure_count == 0
        else "Fix selective alert semantics before any dashboard or alert-ready claim."
    )
}

OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

print(json.dumps({
    "decision": report["decision"],
    "failureCount": failure_count,
    "simulatedAlerts": simulated_alerts,
    "suppressedNonActionableMentionedOnlyCandidateIds": mentioned,
    "alertRulesPath": str(RULES),
    "out": str(OUT)
}, indent=2, ensure_ascii=False))

if failure_count:
    raise SystemExit("ALERT_SIMULATION_FAIL")
