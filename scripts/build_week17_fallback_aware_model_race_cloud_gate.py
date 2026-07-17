#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(".")
JAVA = Path.home() / "work" / "grt_work" / "media-task-platform-java"

JAVA_DIR = JAVA / "artifacts" / "manifests" / "week17_fallback_aware_model_race"
JAVA_REPORT = JAVA_DIR / "week17_fallback_aware_model_race_api_report.json"
JAVA_PAYLOAD = JAVA_DIR / "mainbase_week17_model_race_java_payload_20260701.json"

OUT_DIR = ROOT / "artifacts" / "demo" / "week17_fallback_aware_model_race_cloud_gate"
INPUT_DIR = OUT_DIR / "inputs"
GATE_JSON = OUT_DIR / "week17_fallback_aware_model_race_cloud_gate.json"
DASHBOARD_JSON = OUT_DIR / "week17_fallback_aware_model_race_dashboard_ready.json"
LOADTEST_JSON = ROOT / "loadtest" / "reports" / "week17_fallback_aware_model_race_cloud_gate.json"
PROM_METRICS = ROOT / "loadtest" / "reports" / "week17_fallback_aware_model_race_metrics.prom"
ALERT_RULES = ROOT / "observability" / "prometheus" / "week17_fallback_aware_model_race.rules.yml"


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(path)
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOADTEST_JSON.parent.mkdir(parents=True, exist_ok=True)
    ALERT_RULES.parent.mkdir(parents=True, exist_ok=True)

    java_report = load_json(JAVA_REPORT)
    java_payload = load_json(JAVA_PAYLOAD)

    shutil.copy2(JAVA_REPORT, INPUT_DIR / JAVA_REPORT.name)
    shutil.copy2(JAVA_PAYLOAD, INPUT_DIR / JAVA_PAYLOAD.name)

    checks = {
        "java_api_finalized": java_report.get("status") == "finalized",
        "java_it_passed": java_report.get("test_status") == "passed",
        "artifact_type_ok": java_report.get("artifact_type") == "week17_fallback_aware_model_race_result",
        "true_mmaudio_blocked_declared": java_report.get("true_mmaudio_status") == "blocked_by_torch_torchaudio_abi",
        "case_count_ok": int(java_report.get("case_count", 0)) == 6,
        "winner_count_ok": int(java_report.get("winner_count", 0)) == 6,
        "canonical_candidate_count_ok": int(java_report.get("canonical_candidate_count", 0)) >= 24,
        "payload_item_count_ok": len(java_payload.get("items", [])) == 6,
    }

    gate_ready = all(checks.values())

    generated_at = datetime.now(timezone.utc).isoformat()
    gate = {
        "generated_at": generated_at,
        "status": "GREEN_FALLBACK_AWARE_CLOUD_GATE_READY" if gate_ready else "RED_FALLBACK_AWARE_CLOUD_GATE_BLOCKED",
        "gate_ready": gate_ready,
        "source": "java_week17_fallback_aware_model_race_api_report",
        "checks": checks,
        "summary": {
            "case_count": java_report.get("case_count"),
            "winner_count": java_report.get("winner_count"),
            "canonical_candidate_count": java_report.get("canonical_candidate_count"),
            "true_mmaudio_status": java_report.get("true_mmaudio_status"),
            "java_test_status": java_report.get("test_status"),
        },
        "claim_boundary": {
            "true_mmaudio_v2a_success": False,
            "fallback_aware_reranker_ready": gate_ready,
            "java_consumer_verified": checks["java_it_passed"],
            "cloud_dashboard_ready": gate_ready,
            "k6_threshold_pass": False,
            "production_slo_claim": False,
        },
        "inputs": {
            "java_report": str(INPUT_DIR / JAVA_REPORT.name),
            "java_payload": str(INPUT_DIR / JAVA_PAYLOAD.name),
        },
        "outputs": {
            "gate_json": str(GATE_JSON),
            "dashboard_json": str(DASHBOARD_JSON),
            "loadtest_json": str(LOADTEST_JSON),
            "prom_metrics": str(PROM_METRICS),
            "alert_rules": str(ALERT_RULES),
        },
    }

    dashboard = {
        "generated_at": generated_at,
        "dashboard_ready": gate_ready,
        "title": "Week17 fallback-aware model race cloud gate",
        "panels": [
            {
                "title": "Model race winners",
                "metric": "week17_model_race_winner_count",
                "value": java_report.get("winner_count"),
            },
            {
                "title": "Canonical candidates",
                "metric": "week17_model_race_canonical_candidate_count",
                "value": java_report.get("canonical_candidate_count"),
            },
            {
                "title": "True MMAudio success",
                "metric": "week17_true_mmaudio_success",
                "value": 0,
                "note": "blocked_by_torch_torchaudio_abi",
            },
            {
                "title": "Java consumer IT",
                "metric": "week17_java_consumer_it_pass",
                "value": 1 if checks["java_it_passed"] else 0,
            },
        ],
    }

    prom = "\n".join([
        "# HELP week17_model_race_case_count Number of demo cases in fallback-aware model race.",
        "# TYPE week17_model_race_case_count gauge",
        f"week17_model_race_case_count {int(java_report.get('case_count', 0))}",
        "# HELP week17_model_race_winner_count Number of selected winners.",
        "# TYPE week17_model_race_winner_count gauge",
        f"week17_model_race_winner_count {int(java_report.get('winner_count', 0))}",
        "# HELP week17_model_race_canonical_candidate_count Canonical candidate count after deduplication.",
        "# TYPE week17_model_race_canonical_candidate_count gauge",
        f"week17_model_race_canonical_candidate_count {int(java_report.get('canonical_candidate_count', 0))}",
        "# HELP week17_true_mmaudio_success Whether true MMAudio V2A succeeded.",
        "# TYPE week17_true_mmaudio_success gauge",
        "week17_true_mmaudio_success 0",
        "# HELP week17_java_consumer_it_pass Whether Java RANDOM_PORT consumer IT passed.",
        "# TYPE week17_java_consumer_it_pass gauge",
        f"week17_java_consumer_it_pass {1 if checks['java_it_passed'] else 0}",
        "# HELP week17_fallback_aware_cloud_gate_ready Whether Cloud fallback-aware gate is ready.",
        "# TYPE week17_fallback_aware_cloud_gate_ready gauge",
        f"week17_fallback_aware_cloud_gate_ready {1 if gate_ready else 0}",
        "",
    ])

    rules = """groups:
- name: week17_fallback_aware_model_race
  rules:
  - alert: Week17FallbackAwareCloudGateNotReady
    expr: week17_fallback_aware_cloud_gate_ready < 1
    for: 1m
    labels:
      severity: warning
      project: soundlayer
    annotations:
      summary: "Week17 fallback-aware cloud gate is not ready"
      description: "Java consumer or model race payload failed the fallback-aware gate."
  - alert: Week17TrueMmaudioStillBlocked
    expr: week17_true_mmaudio_success < 1
    for: 1m
    labels:
      severity: info
      project: soundlayer
    annotations:
      summary: "True MMAudio remains blocked"
      description: "This is an honest runtime boundary, not a production failure claim."
"""

    GATE_JSON.write_text(json.dumps(gate, indent=2, ensure_ascii=False), encoding="utf-8")
    DASHBOARD_JSON.write_text(json.dumps(dashboard, indent=2, ensure_ascii=False), encoding="utf-8")
    LOADTEST_JSON.write_text(json.dumps(gate, indent=2, ensure_ascii=False), encoding="utf-8")
    PROM_METRICS.write_text(prom, encoding="utf-8")
    ALERT_RULES.write_text(rules, encoding="utf-8")

    print(json.dumps(gate, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()