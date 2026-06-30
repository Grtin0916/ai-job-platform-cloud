#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


ROOT = Path(__file__).resolve().parents[1]
GATE_DIR = ROOT / "artifacts" / "demo" / "week17_mmaudio_baseline_cloud_gate"
LOADTEST_DIR = ROOT / "loadtest" / "reports"
PROM_DIR = ROOT / "observability" / "prometheus"


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"INPUT_NOT_FOUND: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def b01(value: Any) -> int:
    return 1 if bool(value) else 0


def prom_line(name: str, value: Any, labels: Dict[str, str] | None = None) -> str:
    label_text = ""
    if labels:
        parts = [f'{k}="{v}"' for k, v in labels.items()]
        label_text = "{" + ",".join(parts) + "}"
    if isinstance(value, bool):
        value = b01(value)
    return f"{name}{label_text} {value}"


def main() -> int:
    GATE_DIR.mkdir(parents=True, exist_ok=True)
    LOADTEST_DIR.mkdir(parents=True, exist_ok=True)
    PROM_DIR.mkdir(parents=True, exist_ok=True)

    mainbase_boundary = read_json(GATE_DIR / "mainbase_mmaudio_baseline_boundary.json")
    mainbase_payload = read_json(GATE_DIR / "mainbase_mmaudio_baseline_java_seed_payload.json")
    java_report = read_json(GATE_DIR / "java_mmaudio_baseline_api_report.json")

    claim = mainbase_boundary.get("claim_boundary", {})

    checks = {
        "mainbase_case_count_6": mainbase_boundary.get("case_count") == 6,
        "mainbase_candidate_count_12": mainbase_boundary.get("candidate_count") == 12,
        "mainbase_winner_count_6": mainbase_boundary.get("winner_count") == 6,
        "mainbase_repair_queue_count_6": mainbase_boundary.get("repair_queue_count") == 6,
        "mainbase_bad_prompt_count_0": mainbase_boundary.get("bad_prompt_count") == 0,
        "mainbase_boundary_honest_no_true_mmaudio": claim.get("can_claim_true_mmaudio_v2a_success") is False,
        "java_api_ready": java_report.get("status") == "PASS_JAVA_MMAUDIO_BASELINE_API_READY",
        "java_endpoint_count_5": len(java_report.get("endpoints", [])) == 5,
        "java_matches_mainbase_case_count": java_report.get("case_count") == mainbase_boundary.get("case_count"),
        "java_matches_mainbase_candidate_count": java_report.get("candidate_count") == mainbase_boundary.get("candidate_count"),
        "java_matches_mainbase_winner_count": java_report.get("winner_count") == mainbase_boundary.get("winner_count"),
        "repair_queue_payload_consistent": len(mainbase_payload.get("repair_queue", [])) == mainbase_boundary.get("repair_queue_count"),
        "winner_payload_consistent": len(mainbase_payload.get("winners", [])) == mainbase_boundary.get("winner_count"),
    }

    pass_count = sum(1 for v in checks.values() if v)
    fail_count = sum(1 for v in checks.values() if not v)

    # Honest decision: this is a fallback baseline gate, not a production or true-V2A gate.
    if fail_count == 0 and mainbase_boundary.get("true_mmaudio_generated_count") == 0:
        status = "PASS_CLOUD_MMAUDIO_BASELINE_GATE_READY_WITH_FALLBACK_BOUNDARY"
    elif fail_count == 0:
        status = "PASS_CLOUD_MMAUDIO_BASELINE_GATE_READY"
    else:
        status = "FAIL_CLOUD_MMAUDIO_BASELINE_GATE"

    gate = {
        "status": status,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "mainbase_boundary": "artifacts/demo/week17_mmaudio_baseline_cloud_gate/mainbase_mmaudio_baseline_boundary.json",
            "mainbase_payload": "artifacts/demo/week17_mmaudio_baseline_cloud_gate/mainbase_mmaudio_baseline_java_seed_payload.json",
            "java_api_report": "artifacts/demo/week17_mmaudio_baseline_cloud_gate/java_mmaudio_baseline_api_report.json",
        },
        "checks": checks,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "case_count": mainbase_boundary.get("case_count"),
        "candidate_count": mainbase_boundary.get("candidate_count"),
        "winner_count": mainbase_boundary.get("winner_count"),
        "rejected_count": mainbase_boundary.get("rejected_count"),
        "repair_queue_count": mainbase_boundary.get("repair_queue_count"),
        "bad_prompt_count": mainbase_boundary.get("bad_prompt_count"),
        "true_mmaudio_generated_count": mainbase_boundary.get("true_mmaudio_generated_count"),
        "all_outputs_are_fallback": mainbase_boundary.get("all_outputs_are_fallback"),
        "java_endpoint_count": len(java_report.get("endpoints", [])),
        "claim_boundary": {
            "cloud_can_claim_demo_gate_ready": fail_count == 0,
            "cloud_can_claim_java_api_consumed": java_report.get("status") == "PASS_JAVA_MMAUDIO_BASELINE_API_READY",
            "cloud_can_claim_readable_candidate_audio": claim.get("can_claim_readable_candidate_audio"),
            "cloud_can_claim_dss_conditioned_control_baseline": claim.get("can_claim_dss_conditioned_control_baseline"),
            "cloud_can_claim_true_mmaudio_v2a_success": False,
            "cloud_can_claim_video_synchronized_quality": False,
            "cloud_can_claim_k6_threshold_pass": False,
            "cloud_can_claim_production_slo": False,
        },
        "boundary_note": (
            "Cloud gate consumes Mainbase fallback baseline and Java API report. "
            "Current state is demo-gate-ready with fallback boundary; it is not true MMAudio V2A, not k6 threshold pass, and not production SLO."
        ),
    }

    gate_json = GATE_DIR / "week17_mmaudio_baseline_cloud_gate.json"
    dashboard_json = GATE_DIR / "week17_mmaudio_baseline_dashboard_ready.json"
    loadtest_json = LOADTEST_DIR / "week17_mmaudio_baseline_cloud_gate.json"
    prom_path = PROM_DIR / "week17_mmaudio_baseline_cloud_gate.prom"
    rules_path = PROM_DIR / "week17_mmaudio_baseline_cloud_gate_rules.yml"

    gate_json.write_text(json.dumps(gate, indent=2, ensure_ascii=False), encoding="utf-8")
    loadtest_json.write_text(json.dumps(gate, indent=2, ensure_ascii=False), encoding="utf-8")

    dashboard = {
        "status": "DASHBOARD_READY",
        "title": "Week17 MMAudio Baseline Cloud Gate",
        "panels": [
            {"name": "case_count", "value": gate["case_count"]},
            {"name": "candidate_count", "value": gate["candidate_count"]},
            {"name": "winner_count", "value": gate["winner_count"]},
            {"name": "repair_queue_count", "value": gate["repair_queue_count"]},
            {"name": "true_mmaudio_generated_count", "value": gate["true_mmaudio_generated_count"]},
            {"name": "java_endpoint_count", "value": gate["java_endpoint_count"]},
            {"name": "fallback_boundary", "value": gate["all_outputs_are_fallback"]},
        ],
        "boundary_note": gate["boundary_note"],
    }
    dashboard_json.write_text(json.dumps(dashboard, indent=2, ensure_ascii=False), encoding="utf-8")

    labels = {"system": "soundlayer", "week": "17", "component": "cloud_gate"}
    prom_lines = [
        "# HELP week17_mmaudio_baseline_cloud_gate_ready Whether the cloud gate is ready under fallback boundary.",
        "# TYPE week17_mmaudio_baseline_cloud_gate_ready gauge",
        prom_line("week17_mmaudio_baseline_cloud_gate_ready", fail_count == 0, labels),
        "# HELP week17_mmaudio_baseline_candidate_count Number of candidate audio files in baseline.",
        "# TYPE week17_mmaudio_baseline_candidate_count gauge",
        prom_line("week17_mmaudio_baseline_candidate_count", gate["candidate_count"], labels),
        "# HELP week17_mmaudio_baseline_winner_count Number of selected winners.",
        "# TYPE week17_mmaudio_baseline_winner_count gauge",
        prom_line("week17_mmaudio_baseline_winner_count", gate["winner_count"], labels),
        "# HELP week17_mmaudio_baseline_repair_queue_count Number of repair targets.",
        "# TYPE week17_mmaudio_baseline_repair_queue_count gauge",
        prom_line("week17_mmaudio_baseline_repair_queue_count", gate["repair_queue_count"], labels),
        "# HELP week17_mmaudio_baseline_true_mmaudio_generated_count Number of true MMAudio generated candidates.",
        "# TYPE week17_mmaudio_baseline_true_mmaudio_generated_count gauge",
        prom_line("week17_mmaudio_baseline_true_mmaudio_generated_count", gate["true_mmaudio_generated_count"], labels),
        "# HELP week17_mmaudio_baseline_java_endpoint_count Number of Java endpoints exposed for this baseline.",
        "# TYPE week17_mmaudio_baseline_java_endpoint_count gauge",
        prom_line("week17_mmaudio_baseline_java_endpoint_count", gate["java_endpoint_count"], labels),
        "# HELP week17_mmaudio_baseline_can_claim_true_v2a Whether true MMAudio V2A success can be claimed.",
        "# TYPE week17_mmaudio_baseline_can_claim_true_v2a gauge",
        prom_line("week17_mmaudio_baseline_can_claim_true_v2a", False, labels),
        "",
    ]
    prom_path.write_text("\n".join(prom_lines), encoding="utf-8")

    rules = """groups:
- name: week17_mmaudio_baseline_cloud_gate
  rules:
  - alert: Week17MmaudioBaselineCloudGateNotReady
    expr: week17_mmaudio_baseline_cloud_gate_ready{system="soundlayer",week="17",component="cloud_gate"} < 1
    for: 0m
    labels:
      severity: warning
    annotations:
      summary: "Week17 MMAudio baseline cloud gate is not ready"
      description: "Cloud gate failed at least one consistency check."
  - alert: Week17MmaudioTrueV2aStillMissing
    expr: week17_mmaudio_baseline_true_mmaudio_generated_count{system="soundlayer",week="17",component="cloud_gate"} < 1
    for: 0m
    labels:
      severity: info
    annotations:
      summary: "True MMAudio V2A output is still missing"
      description: "Current baseline is fallback control audio. Do not claim true V2A success."
"""
    rules_path.write_text(rules, encoding="utf-8")

    result = {
        "status": status,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "outputs": {
            "gate_json": str(gate_json.relative_to(ROOT)),
            "dashboard_json": str(dashboard_json.relative_to(ROOT)),
            "loadtest_json": str(loadtest_json.relative_to(ROOT)),
            "prometheus_metrics": str(prom_path.relative_to(ROOT)),
            "prometheus_rules": str(rules_path.relative_to(ROOT)),
        },
        "claim_boundary": gate["claim_boundary"],
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())