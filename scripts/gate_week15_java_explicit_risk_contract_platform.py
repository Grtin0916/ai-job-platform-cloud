#!/usr/bin/env python3
import json
import re
from datetime import datetime, timezone
from pathlib import Path

JAVA_REPORT = Path("artifacts/manifests/week15_java_explicit_risk_contract_consumer_report.json")
CLOUD_ACTIONABILITY = Path("loadtest/reports/week15_temporal_alignment_eval_v1_actionability_gate.json")
OUT = Path("loadtest/reports/week15_temporal_alignment_java_explicit_risk_contract_platform_gate.json")
PROM = Path("observability/prometheus/week15_temporal_alignment_java_explicit_risk_contract_metrics.prom")

def safe_label(s):
    return re.sub(r"[^a-zA-Z0-9_:\-.]", "_", str(s))[:160]

java = json.loads(JAVA_REPORT.read_text(encoding="utf-8"))
cloud = json.loads(CLOUD_ACTIONABILITY.read_text(encoding="utf-8"))

j_summary = java.get("summary") or {}
j_actionable = j_summary.get("actionableRiskCandidateIds") or []
j_non_actionable = j_summary.get("nonActionableCandidateIds") or []
j_alert = j_summary.get("alertEligibleCandidateIds") or []

c_actionable = cloud.get("actionableRiskCandidateIds") or []
c_mentioned = cloud.get("nonActionableMentionedOnlyCandidateIds") or []

failures = []

if java.get("decision") != "PASS":
    failures.append("JAVA_EXPLICIT_CONTRACT_NOT_PASS")
if java.get("apiEndpoint") != "/api/week15/temporal-alignment/explicit-risk-contract":
    failures.append("JAVA_API_ENDPOINT_UNEXPECTED")
if j_actionable != ["procedural_v0_0004", "procedural_v0_0010"]:
    failures.append("JAVA_ACTIONABLE_SET_UNEXPECTED")
if j_alert != j_actionable:
    failures.append("JAVA_ALERT_ELIGIBLE_MISMATCH")
if c_actionable != j_actionable:
    failures.append("CLOUD_ACTIONABLE_SET_DIVERGES_FROM_JAVA")
if not set(c_mentioned).issubset(set(j_non_actionable)):
    failures.append("CLOUD_MENTIONED_ONLY_NOT_SUBSET_OF_JAVA_NON_ACTIONABLE")

decision = "PASS_JAVA_EXPLICIT_RISK_CONTRACT_PLATFORM_GATE" if not failures else "FAIL_JAVA_EXPLICIT_RISK_CONTRACT_PLATFORM_GATE"

report = {
    "schemaVersion": "week15.cloud.java_explicit_risk_contract_platform_gate.v1",
    "generatedAt": datetime.now(timezone.utc).isoformat(),
    "scope": "offline Cloud consumption of Java explicit risk contract; no live service or production SLO claim",
    "decision": decision,
    "failures": failures,
    "sourceJavaReport": str(JAVA_REPORT),
    "sourceCloudActionabilityGate": str(CLOUD_ACTIONABILITY),
    "javaApiEndpoint": java.get("apiEndpoint"),
    "sourceMode": "java_explicit_risk_contract",
    "summary": {
        "candidateTotal": j_summary.get("candidateTotal"),
        "actionableRiskCandidateIds": j_actionable,
        "alertEligibleCandidateIds": j_alert,
        "javaNonActionableCandidateIds": j_non_actionable,
        "cloudSuppressedMentionedOnlyCandidateIds": c_mentioned,
        "blockedClaims": j_summary.get("blockedClaims"),
    },
    "allowedClaims": [
        "Cloud can consume Java explicit risk contract evidence instead of inferring risk from text.",
        "Cloud actionable alert semantics match Java explicit contract output.",
    ],
    "blockedClaims": [
        "This gate does not establish live Java service availability.",
        "This gate does not establish live Grafana import.",
        "This gate does not establish production SLO.",
        "This gate does not establish human-review pass or semantic audio quality pass.",
    ],
    "nextAction": (
        "Use java_explicit_risk_contract as the preferred Cloud source mode for Week15 dashboard and alert evidence."
        if not failures
        else "Fix Java/Cloud explicit contract mismatch before claiming platform consumption."
    )
}

OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

lines = [
    "# HELP week15_temporal_alignment_java_explicit_risk_contract_platform_gate_pass Cloud gate pass flag for Java explicit risk contract consumption.",
    "# TYPE week15_temporal_alignment_java_explicit_risk_contract_platform_gate_pass gauge",
    f'week15_temporal_alignment_java_explicit_risk_contract_platform_gate_pass{{decision="{safe_label(decision)}",source_mode="java_explicit_risk_contract"}} {1 if not failures else 0}',
    "# HELP week15_temporal_alignment_java_explicit_risk_contract_actionable_total Actionable candidate count from Java explicit contract.",
    "# TYPE week15_temporal_alignment_java_explicit_risk_contract_actionable_total gauge",
    f"week15_temporal_alignment_java_explicit_risk_contract_actionable_total {len(j_actionable)}",
    "# HELP week15_temporal_alignment_java_explicit_risk_contract_non_actionable_total Non-actionable candidate count from Java explicit contract.",
    "# TYPE week15_temporal_alignment_java_explicit_risk_contract_non_actionable_total gauge",
    f"week15_temporal_alignment_java_explicit_risk_contract_non_actionable_total {len(j_non_actionable)}",
]
PROM.write_text("\n".join(lines) + "\n", encoding="utf-8")

print(json.dumps({
    "decision": decision,
    "failures": failures,
    "sourceMode": "java_explicit_risk_contract",
    "actionableRiskCandidateIds": j_actionable,
    "cloudSuppressedMentionedOnlyCandidateIds": c_mentioned,
    "out": str(OUT),
    "prom": str(PROM)
}, indent=2, ensure_ascii=False))

if failures:
    raise SystemExit("JAVA_EXPLICIT_RISK_CONTRACT_PLATFORM_GATE_FAIL")
