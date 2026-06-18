#!/usr/bin/env python3
import json
import re
from datetime import datetime, timezone
from pathlib import Path

GATE = Path("loadtest/reports/week15_temporal_alignment_eval_v1_gate.json")
PROM = Path("observability/prometheus/week15_temporal_alignment_eval_v1_metrics.prom")
OUT = Path("loadtest/reports/week15_temporal_alignment_eval_v1_threshold_smoke.json")

EXPECTED_BLOCKED = {
    "HUMAN_REVIEW_PASS is not established.",
    "SEMANTIC_AUDIO_QUALITY_PASS is not established.",
    "FINAL_MIX_READINESS is not established.",
    "LIVE_GRAFANA_IMPORT is not established.",
    "PRODUCTION_SLO is not established.",
    "REAL_CLOUD_DEPLOYMENT is not established.",
}

def fail(name, detail):
    return {"name": name, "status": "FAIL", "detail": detail}

def ok(name, detail):
    return {"name": name, "status": "PASS", "detail": detail}

def warn(name, detail):
    return {"name": name, "status": "WARN", "detail": detail}

checks = []
warnings = []

if not GATE.exists():
    checks.append(fail("gate_exists", str(GATE)))
    gate = {}
else:
    gate = json.loads(GATE.read_text(encoding="utf-8"))
    checks.append(ok("gate_exists", str(GATE)))

if not PROM.exists():
    checks.append(fail("prom_exists", str(PROM)))
    prom = ""
else:
    prom = PROM.read_text(encoding="utf-8")
    checks.append(ok("prom_exists", str(PROM)))

decision = gate.get("gateDecision")
if decision == "PASS_EVAL_V1_PLATFORM_GATE_WITH_BLOCKED_CLAIMS":
    checks.append(ok("gate_decision", decision))
else:
    checks.append(fail("gate_decision", decision))

blockers = gate.get("blockers")
if blockers == []:
    checks.append(ok("blockers_empty", blockers))
else:
    checks.append(fail("blockers_empty", blockers))

blocked = set(gate.get("blockedClaims") or [])
missing_blocked = sorted(EXPECTED_BLOCKED - blocked)
extra_blocked = sorted(blocked - EXPECTED_BLOCKED)
if not missing_blocked:
    checks.append(ok("blocked_claims_complete", sorted(blocked)))
else:
    checks.append(fail("blocked_claims_complete", {"missing": missing_blocked, "extra": extra_blocked}))

risk_ids = gate.get("riskCandidateIds") or []
risk_count = gate.get("riskCandidateCount")
if risk_ids and risk_count == len(risk_ids):
    checks.append(ok("risk_candidate_count_consistent", {"riskCandidateCount": risk_count, "riskCandidateIds": risk_ids}))
else:
    checks.append(fail("risk_candidate_count_consistent", {"riskCandidateCount": risk_count, "riskCandidateIds": risk_ids}))

if len(risk_ids) > 2:
    warnings.append(warn(
        "risk_candidate_precision",
        "riskCandidateIds contains more than the known 0004/0010 remediation pair; treat it as proxy risk evidence, not final human-review failures."
    ))

required_prom_tokens = [
    "# HELP week15_temporal_alignment_eval_v1_gate_pass",
    "# TYPE week15_temporal_alignment_eval_v1_gate_pass gauge",
    "week15_temporal_alignment_eval_v1_gate_pass",
    "week15_temporal_alignment_eval_v1_blocked_claim_total 6",
    f"week15_temporal_alignment_eval_v1_risk_candidate_total {len(risk_ids)}",
]

missing_tokens = [x for x in required_prom_tokens if x not in prom]
if not missing_tokens:
    checks.append(ok("prometheus_text_tokens", required_prom_tokens))
else:
    checks.append(fail("prometheus_text_tokens", {"missing": missing_tokens}))

gate_pass_match = re.search(r"week15_temporal_alignment_eval_v1_gate_pass\{[^}]*\}\s+([0-9.]+)", prom)
if gate_pass_match and gate_pass_match.group(1) == "1":
    checks.append(ok("prom_gate_pass_value", gate_pass_match.group(1)))
else:
    checks.append(fail("prom_gate_pass_value", gate_pass_match.group(1) if gate_pass_match else None))

failures = [c for c in checks if c["status"] == "FAIL"]

report = {
    "schemaVersion": "week15.temporal_alignment.eval_v1_threshold_smoke.v1",
    "generatedAt": datetime.now(timezone.utc).isoformat(),
    "scope": "offline repository evidence threshold smoke; no live Grafana or production SLO claim",
    "decision": "PASS" if not failures else "FAIL",
    "checks": checks,
    "warnings": warnings,
    "failureCount": len(failures),
    "warningCount": len(warnings),
    "sourceGate": str(GATE),
    "sourceProm": str(PROM),
    "nextAction": (
        "Proceed to minimal Cloud runbook/weekly note or dashboard-ready index."
        if not failures
        else "Fix failed threshold checks before claiming Eval V1 platform gate readiness."
    )
}

OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps(report, indent=2, ensure_ascii=False))

if failures:
    raise SystemExit("EVAL_V1_THRESHOLD_SMOKE_FAIL")
