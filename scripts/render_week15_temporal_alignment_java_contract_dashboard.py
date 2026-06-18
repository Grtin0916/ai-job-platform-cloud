#!/usr/bin/env python3
import json
from datetime import datetime, timezone
from pathlib import Path

JAVA_GATE = Path("loadtest/reports/week15_temporal_alignment_java_explicit_risk_contract_platform_gate.json")
OLD_DASHBOARD_READY = Path("loadtest/reports/week15_temporal_alignment_eval_v1_dashboard_ready.json")

DASHBOARD = Path("observability/grafana/dashboards/week15_temporal_alignment_eval_v1_java_contract_dashboard.json")
REPORT = Path("loadtest/reports/week15_temporal_alignment_eval_v1_java_contract_dashboard_ready.json")
SOURCE_MODE_PROM = Path("observability/prometheus/week15_temporal_alignment_eval_v1_source_mode_metrics.prom")

def load(path):
    return json.loads(path.read_text(encoding="utf-8"))

java_gate = load(JAVA_GATE)
old_dashboard = load(OLD_DASHBOARD_READY) if OLD_DASHBOARD_READY.exists() else {}

summary = java_gate.get("summary") or {}
actionable = summary.get("actionableRiskCandidateIds") or []
non_actionable = summary.get("javaNonActionableCandidateIds") or []
suppressed = summary.get("cloudSuppressedMentionedOnlyCandidateIds") or []
blocked_claims = summary.get("blockedClaims") or []

failures = []
if java_gate.get("decision") != "PASS_JAVA_EXPLICIT_RISK_CONTRACT_PLATFORM_GATE":
    failures.append("JAVA_EXPLICIT_PLATFORM_GATE_NOT_PASS")
if java_gate.get("sourceMode") != "java_explicit_risk_contract":
    failures.append("SOURCE_MODE_NOT_JAVA_EXPLICIT")
if actionable != ["procedural_v0_0004", "procedural_v0_0010"]:
    failures.append("ACTIONABLE_SET_UNEXPECTED")
if len(non_actionable) != 8:
    failures.append("NON_ACTIONABLE_COUNT_UNEXPECTED")
if not OLD_DASHBOARD_READY.exists():
    failures.append("OLD_DASHBOARD_READY_MISSING_FOR_PROVENANCE")

dashboard = {
    "title": "Week15 Temporal Alignment Eval V1 - Java Explicit Contract",
    "uid": "week15-temporal-alignment-eval-v1-java-contract",
    "schemaVersion": 39,
    "version": 1,
    "refresh": False,
    "tags": ["week15", "temporal-alignment", "eval-v1", "java-explicit-contract", "local-evidence"],
    "timezone": "browser",
    "annotations": {"list": []},
    "templating": {"list": []},
    "time": {"from": "now-24h", "to": "now"},
    "panels": [
        {
            "id": 1,
            "type": "stat",
            "title": "Java Explicit Contract Gate",
            "description": "Preferred Cloud source mode. Offline repository evidence only.",
            "targets": [
                {
                    "expr": "week15_temporal_alignment_java_explicit_risk_contract_platform_gate_pass",
                    "legendFormat": "java contract gate"
                }
            ],
            "gridPos": {"h": 8, "w": 6, "x": 0, "y": 0}
        },
        {
            "id": 2,
            "type": "stat",
            "title": "Actionable Risk Candidates",
            "description": "Actionable candidates from Java explicit contract.",
            "targets": [
                {
                    "expr": "week15_temporal_alignment_java_explicit_risk_contract_actionable_total",
                    "legendFormat": "actionable"
                }
            ],
            "gridPos": {"h": 8, "w": 6, "x": 6, "y": 0}
        },
        {
            "id": 3,
            "type": "stat",
            "title": "Non-actionable Candidates",
            "description": "Non-actionable candidates from Java explicit contract.",
            "targets": [
                {
                    "expr": "week15_temporal_alignment_java_explicit_risk_contract_non_actionable_total",
                    "legendFormat": "non-actionable"
                }
            ],
            "gridPos": {"h": 8, "w": 6, "x": 12, "y": 0}
        },
        {
            "id": 4,
            "type": "stat",
            "title": "Preferred Source Mode",
            "description": "1 means Java explicit contract is the selected source of truth.",
            "targets": [
                {
                    "expr": "week15_temporal_alignment_eval_v1_preferred_source_mode{source_mode=\"java_explicit_risk_contract\"}",
                    "legendFormat": "java_explicit_risk_contract"
                }
            ],
            "gridPos": {"h": 8, "w": 6, "x": 18, "y": 0}
        },
        {
            "id": 5,
            "type": "text",
            "title": "Actionable Candidate IDs",
            "options": {
                "mode": "markdown",
                "content": "- actionable: procedural_v0_0004, procedural_v0_0010\n- source: Java explicit risk contract API snapshot\n- alertEligible equals actionable"
            },
            "gridPos": {"h": 8, "w": 12, "x": 0, "y": 8}
        },
        {
            "id": 6,
            "type": "text",
            "title": "Scope Boundaries",
            "options": {
                "mode": "markdown",
                "content": "Dashboard-ready only. No live Java service availability claim, no live Grafana import, no production SLO, no human-review pass, no semantic audio quality pass, no final mix readiness."
            },
            "gridPos": {"h": 8, "w": 12, "x": 12, "y": 8}
        }
    ]
}

DASHBOARD.parent.mkdir(parents=True, exist_ok=True)
REPORT.parent.mkdir(parents=True, exist_ok=True)
SOURCE_MODE_PROM.parent.mkdir(parents=True, exist_ok=True)

DASHBOARD.write_text(json.dumps(dashboard, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

source_mode_lines = [
    "# HELP week15_temporal_alignment_eval_v1_preferred_source_mode Preferred source mode for Eval V1 dashboard and alert evidence.",
    "# TYPE week15_temporal_alignment_eval_v1_preferred_source_mode gauge",
    'week15_temporal_alignment_eval_v1_preferred_source_mode{source_mode="java_explicit_risk_contract"} 1',
    'week15_temporal_alignment_eval_v1_preferred_source_mode{source_mode="cloud_inferred_taxonomy"} 0',
]
SOURCE_MODE_PROM.write_text("\n".join(source_mode_lines) + "\n", encoding="utf-8")

report = {
    "schemaVersion": "week15.temporal_alignment.eval_v1.java_contract_dashboard_ready.v1",
    "generatedAt": datetime.now(timezone.utc).isoformat(),
    "scope": "dashboard-ready repository evidence; no live Grafana import, no live Java service, no production SLO claim",
    "decision": "PASS" if not failures else "FAIL",
    "failures": failures,
    "preferredSourceMode": "java_explicit_risk_contract",
    "legacySourceMode": "cloud_inferred_taxonomy",
    "dashboardPath": str(DASHBOARD),
    "sourceModeMetricsPath": str(SOURCE_MODE_PROM),
    "sourceReports": {
        "javaExplicitRiskContractPlatformGate": str(JAVA_GATE),
        "previousDashboardReadyProvenance": str(OLD_DASHBOARD_READY)
    },
    "summary": {
        "javaGateDecision": java_gate.get("decision"),
        "javaApiEndpoint": java_gate.get("javaApiEndpoint"),
        "candidateTotal": summary.get("candidateTotal"),
        "actionableRiskCandidateIds": actionable,
        "alertEligibleCandidateIds": summary.get("alertEligibleCandidateIds"),
        "javaNonActionableCandidateIds": non_actionable,
        "cloudSuppressedMentionedOnlyCandidateIds": suppressed,
        "blockedClaims": blocked_claims,
        "previousDashboardDecision": old_dashboard.get("decision")
    },
    "dashboardPanels": [
        "Java Explicit Contract Gate",
        "Actionable Risk Candidates",
        "Non-actionable Candidates",
        "Preferred Source Mode",
        "Actionable Candidate IDs",
        "Scope Boundaries"
    ],
    "allowedClaims": [
        "Java explicit risk contract is the preferred Cloud source mode for Week15 Eval V1 dashboard evidence.",
        "Dashboard-ready JSON uses Java explicit risk contract metrics as primary panels.",
        "Legacy Cloud inferred taxonomy is retained only as provenance."
    ],
    "blockedClaims": [
        "No live Java service availability claim.",
        "No live Grafana import claim.",
        "No production SLO claim.",
        "No human-review pass claim.",
        "No semantic audio quality pass claim.",
        "No final mix readiness claim."
    ],
    "nextAction": (
        "Commit Java-contract-first dashboard-ready artifact, then run a final three-repo Week15 closure index."
        if not failures
        else "Fix Java-contract dashboard source-mode failures before commit."
    )
}

REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

print(json.dumps({
    "decision": report["decision"],
    "failures": failures,
    "preferredSourceMode": report["preferredSourceMode"],
    "dashboardPath": str(DASHBOARD),
    "sourceModeMetricsPath": str(SOURCE_MODE_PROM),
    "actionableRiskCandidateIds": actionable,
    "nextAction": report["nextAction"]
}, indent=2, ensure_ascii=False))

if failures:
    raise SystemExit("JAVA_CONTRACT_DASHBOARD_READY_FAIL")
