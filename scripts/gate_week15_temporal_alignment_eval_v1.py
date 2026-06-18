#!/usr/bin/env python3
import json
import re
from datetime import datetime, timezone
from pathlib import Path

OUT_GATE = Path("loadtest/reports/week15_temporal_alignment_eval_v1_gate.json")
OUT_PROM = Path("observability/prometheus/week15_temporal_alignment_eval_v1_metrics.prom")

SOURCES = {
    "scoreSummary": [
        "loadtest/reports/week15_temporal_alignment_score_summary_platform_index.json"
    ],
    "reviewStateRegistryBacked": [
        "loadtest/reports/week15_temporal_alignment_review_state_registry_backed_platform_gate.json",
        "loadtest/reports/week15_temporal_alignment_review_state_registry_backed_platform_index.json"
    ],
    "signalAssessment": [
        "loadtest/reports/week15_temporal_alignment_signal_assessment_platform_gate.json",
        "loadtest/reports/week15_temporal_alignment_signal_assessment_platform_index.json"
    ],
    "legacyThreeRepoClosure": [
        "loadtest/reports/week15_temporal_alignment_three_repo_signal_review_chain_closure.json"
    ]
}

ALLOWED = [
    "Temporal Alignment Eval V1 can be consumed as a local repository evidence gate.",
    "Cloud metrics-ready evidence can represent alignment gate state.",
    "Java registry-backed review state is consumable by Cloud evidence aggregation.",
    "Mainbase signal assessment can be used as quantitative timing/signal risk evidence."
]

BLOCKED = [
    "HUMAN_REVIEW_PASS is not established.",
    "SEMANTIC_AUDIO_QUALITY_PASS is not established.",
    "FINAL_MIX_READINESS is not established.",
    "LIVE_GRAFANA_IMPORT is not established.",
    "PRODUCTION_SLO is not established.",
    "REAL_CLOUD_DEPLOYMENT is not established."
]

def load_first(paths):
    for s in paths:
        p = Path(s)
        if p.exists():
            raw = p.read_text(encoding="utf-8")
            try:
                return p, json.loads(raw), raw, None
            except Exception as e:
                return p, None, raw, f"{type(e).__name__}: {e}"
    return None, None, "", "missing"

def label(s):
    return re.sub(r"[^a-zA-Z0-9_:\-.]", "_", str(s))[:160]

sources = {}
blockers = []
raw_all = ""

for name, paths in SOURCES.items():
    p, data, raw, err = load_first(paths)
    raw_all += "\n" + raw
    sources[name] = {
        "path": str(p) if p else None,
        "exists": p is not None,
        "parseOk": data is not None,
        "error": err,
        "topLevelKeys": sorted(data.keys()) if isinstance(data, dict) else []
    }

for name in ["scoreSummary", "reviewStateRegistryBacked", "signalAssessment"]:
    if not sources[name]["exists"]:
        blockers.append(f"MISSING_REQUIRED_SOURCE:{name}")
    elif not sources[name]["parseOk"]:
        blockers.append(f"UNPARSEABLE_REQUIRED_SOURCE:{name}:{sources[name]['error']}")

risk_ids = sorted(set(re.findall(r"procedural_v0_\d+", raw_all)))
if not risk_ids:
    blockers.append("MISSING_RISK_CANDIDATE_IDS")

decision = (
    "PASS_EVAL_V1_PLATFORM_GATE_WITH_BLOCKED_CLAIMS"
    if not blockers
    else "BLOCKED_EVAL_V1_PLATFORM_GATE_INCOMPLETE_EVIDENCE"
)

gate = {
    "schemaVersion": "week15.temporal_alignment.eval_v1_gate.v1",
    "generatedAt": datetime.now(timezone.utc).isoformat(),
    "scope": "local Docker Desktop / repository evidence only",
    "gateDecision": decision,
    "blockers": blockers,
    "allowedClaims": ALLOWED,
    "blockedClaims": BLOCKED,
    "riskCandidateIds": risk_ids,
    "riskCandidateCount": len(risk_ids),
    "sourceReports": sources,
    "nextAction": (
        "Run Eval V1 offline threshold smoke, then proceed to minimal Cloud runbook or weekly evidence."
        if not blockers
        else "Inspect missing or unparseable required source reports."
    )
}

OUT_GATE.write_text(json.dumps(gate, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

prom = [
    "# HELP week15_temporal_alignment_eval_v1_gate_pass Eval V1 platform gate pass flag.",
    "# TYPE week15_temporal_alignment_eval_v1_gate_pass gauge",
    f'week15_temporal_alignment_eval_v1_gate_pass{{decision="{label(decision)}",scope="local_evidence"}} {1 if not blockers else 0}',
    "# HELP week15_temporal_alignment_eval_v1_blocked_claim_total Blocked claim count.",
    "# TYPE week15_temporal_alignment_eval_v1_blocked_claim_total gauge",
    f"week15_temporal_alignment_eval_v1_blocked_claim_total {len(BLOCKED)}",
    "# HELP week15_temporal_alignment_eval_v1_risk_candidate_total Risk candidate count.",
    "# TYPE week15_temporal_alignment_eval_v1_risk_candidate_total gauge",
    f"week15_temporal_alignment_eval_v1_risk_candidate_total {len(risk_ids)}"
]
OUT_PROM.write_text("\n".join(prom) + "\n", encoding="utf-8")

print(json.dumps({
    "gateDecision": decision,
    "blockers": blockers,
    "riskCandidateIds": risk_ids,
    "outGate": str(OUT_GATE),
    "outProm": str(OUT_PROM)
}, indent=2, ensure_ascii=False))
