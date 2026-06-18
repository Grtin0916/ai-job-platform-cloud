#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

GATE = Path("loadtest/reports/week15_temporal_alignment_eval_v1_gate.json")
THRESHOLD = Path("loadtest/reports/week15_temporal_alignment_eval_v1_threshold_smoke.json")
TAXONOMY = Path("loadtest/reports/week15_temporal_alignment_eval_v1_risk_taxonomy.json")
ACTIONABILITY = Path("loadtest/reports/week15_temporal_alignment_eval_v1_actionability_gate.json")
ALERT_SIM = Path("loadtest/reports/week15_temporal_alignment_eval_v1_alert_simulation.json")

DASHBOARD = Path("observability/grafana/dashboards/week15_temporal_alignment_eval_v1_dashboard.json")
REPORT = Path("loadtest/reports/week15_temporal_alignment_eval_v1_dashboard_ready.json")

def load(path):
    return json.loads(path.read_text(encoding="utf-8"))

gate = load(GATE)
threshold = load(THRESHOLD)
taxonomy = load(TAXONOMY)
actionability = load(ACTIONABILITY)
alert_sim = load(ALERT_SIM)

failures = []

if gate.get("gateDecision") != "PASS_EVAL_V1_PLATFORM_GATE_WITH_BLOCKED_CLAIMS":
    failures.append("GATE_NOT_PASS")
if threshold.get("decision") != "PASS":
    failures.append("THRESHOLD_SMOKE_NOT_PASS")
if taxonomy.get("decision") != "PASS":
    failures.append("RISK_TAXONOMY_NOT_PASS")
if actionability.get("decision") != "PASS_ACTIONABILITY_GATE_WITH_PROXY_RISK_EXCLUDED":
    failures.append("ACTIONABILITY_GATE_NOT_PASS")
if alert_sim.get("decision") != "PASS":
    failures.append("ALERT_SIMULATION_NOT_PASS")

actionable = actionability.get("actionableRiskCandidateIds") or []
mentioned = actionability.get("nonActionableMentionedOnlyCandidateIds") or []
unknown = actionability.get("unknownRiskCandidateIds") or []
blocked_claims = gate.get("blockedClaims") or []
simulated_alerts = alert_sim.get("simulatedAlerts") or []

if actionable != ["procedural_v0_0004", "procedural_v0_0010"]:
    failures.append("ACTIONABLE_RISK_SET_UNEXPECTED")
if unknown:
    failures.append("UNKNOWN_RISK_EXISTS")

dashboard = {
    "title": "Week15 Temporal Alignment Eval V1",
    "uid": "week15-temporal-alignment-eval-v1",
    "schemaVersion": 39,
    "version": 1,
    "refresh": False,
    "tags": ["week15", "temporal-alignment", "eval-v1", "local-evidence"],
    "timezone": "browser",
    "annotations": {"list": []},
    "templating": {"list": []},
    "time": {"from": "now-24h", "to": "now"},
    "panels": [
        {
            "id": 1,
            "type": "stat",
            "title": "Eval V1 Gate Pass",
            "description": "Local repository evidence only; not production SLO.",
            "targets": [
                {
                    "expr": "week15_temporal_alignment_eval_v1_gate_pass",
                    "legendFormat": "gate"
                }
            ],
            "fieldConfig": {
                "defaults": {
                    "unit": "none",
                    "thresholds": {
                        "mode": "absolute",
                        "steps": [
                            {"color": "red", "value": None},
                            {"color": "green", "value": 1}
                        ]
                    }
                },
                "overrides": []
            },
            "gridPos": {"h": 8, "w": 6, "x": 0, "y": 0}
        },
        {
            "id": 2,
            "type": "bargauge",
            "title": "Risk Candidates by Actionability",
            "description": "Alert only on actionable remediation/drift candidates; mentioned_only is context.",
            "targets": [
                {
                    "expr": "week15_temporal_alignment_eval_v1_risk_candidate_by_actionability",
                    "legendFormat": "{{actionability}}"
                }
            ],
            "gridPos": {"h": 8, "w": 9, "x": 6, "y": 0}
        },
        {
            "id": 3,
            "type": "stat",
            "title": "Blocked Claims",
            "description": "Claims intentionally blocked to avoid overstatement.",
            "targets": [
                {
                    "expr": "week15_temporal_alignment_eval_v1_blocked_claim_total",
                    "legendFormat": "blocked claims"
                }
            ],
            "gridPos": {"h": 8, "w": 6, "x": 15, "y": 0}
        },
        {
            "id": 4,
            "type": "stat",
            "title": "Actionability Gate Pass",
            "description": "Proxy risk is excluded from alerting.",
            "targets": [
                {
                    "expr": "week15_temporal_alignment_eval_v1_actionability_gate_pass",
                    "legendFormat": "actionability"
                }
            ],
            "gridPos": {"h": 8, "w": 6, "x": 0, "y": 8}
        },
        {
            "id": 5,
            "type": "timeseries",
            "title": "Actionable Risk Alert",
            "description": "Would fire when actionable risk count > 0.",
            "targets": [
                {
                    "expr": "week15_temporal_alignment_eval_v1_risk_candidate_by_actionability{actionability=\"actionable\"}",
                    "legendFormat": "actionable"
                }
            ],
            "gridPos": {"h": 8, "w": 9, "x": 6, "y": 8}
        },
        {
            "id": 6,
            "type": "text",
            "title": "Scope Boundaries",
            "options": {
                "mode": "markdown",
                "content": "Dashboard-ready only. No live Grafana import, no production SLO, no human-review pass, no semantic audio quality pass, no final mix readiness, no real cloud deployment."
            },
            "gridPos": {"h": 8, "w": 9, "x": 15, "y": 8}
        }
    ]
}

DASHBOARD.parent.mkdir(parents=True, exist_ok=True)
REPORT.parent.mkdir(parents=True, exist_ok=True)

DASHBOARD.write_text(json.dumps(dashboard, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

report = {
    "schemaVersion": "week15.temporal_alignment.eval_v1_dashboard_ready.v1",
    "generatedAt": datetime.now(timezone.utc).isoformat(),
    "scope": "dashboard-ready repository evidence; no live Grafana import or production SLO claim",
    "decision": "PASS" if not failures else "FAIL",
    "failures": failures,
    "dashboardPath": str(DASHBOARD),
    "sourceReports": {
        "gate": str(GATE),
        "threshold": str(THRESHOLD),
        "taxonomy": str(TAXONOMY),
        "actionability": str(ACTIONABILITY),
        "alertSimulation": str(ALERT_SIM)
    },
    "summary": {
        "gateDecision": gate.get("gateDecision"),
        "thresholdDecision": threshold.get("decision"),
        "taxonomyDecision": taxonomy.get("decision"),
        "actionabilityDecision": actionability.get("decision"),
        "alertSimulationDecision": alert_sim.get("decision"),
        "actionableRiskCandidateIds": actionable,
        "nonActionableMentionedOnlyCandidateIds": mentioned,
        "unknownRiskCandidateIds": unknown,
        "blockedClaimCount": len(blocked_claims),
        "simulatedAlerts": simulated_alerts
    },
    "dashboardPanels": [
        "Eval V1 Gate Pass",
        "Risk Candidates by Actionability",
        "Blocked Claims",
        "Actionability Gate Pass",
        "Actionable Risk Alert",
        "Scope Boundaries"
    ],
    "allowedClaims": [
        "Dashboard JSON is ready for local Grafana import or platform rendering.",
        "Actionable risk count can be displayed separately from mentioned_only candidates.",
        "Alert-ready semantics suppress non-actionable mentioned_only candidates."
    ],
    "blockedClaims": blocked_claims,
    "nextAction": (
        "Run JSON validation and commit dashboard-ready artifact."
        if not failures
        else "Fix dashboard-ready source failures before committing."
    )
}

REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

print(json.dumps({
    "decision": report["decision"],
    "failures": failures,
    "dashboardPath": str(DASHBOARD),
    "reportPath": str(REPORT),
    "actionableRiskCandidateIds": actionable,
    "nonActionableMentionedOnlyCandidateIds": mentioned,
    "simulatedAlerts": simulated_alerts
}, indent=2, ensure_ascii=False))

if failures:
    raise SystemExit("DASHBOARD_READY_FAIL")
