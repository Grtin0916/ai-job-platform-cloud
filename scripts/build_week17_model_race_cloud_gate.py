#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def git_head(path: str) -> str:
    try:
        p = subprocess.run(
            ["git", "-C", path, "rev-parse", "--short", "HEAD"],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return p.stdout.strip() if p.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def main() -> int:
    cloud_root = Path.cwd()
    mainbase = Path.home() / "work" / "grt_work" / "audio_engineering_repo_skeleton_v1"
    java = Path.home() / "work" / "grt_work" / "media-task-platform-java"

    base = cloud_root / "artifacts" / "demo" / "week17_model_race_cloud_gate"
    inputs = base / "inputs"

    demo_cases = read_json(inputs / "mainbase_demo_cases_inventory.json")
    media = read_json(inputs / "mainbase_case_media_materialization_report.json")
    race = read_json(inputs / "mainbase_control_seed_summary.json")
    repair = read_json(inputs / "mainbase_control_repair_summary.json")
    java_report = read_json(inputs / "java_model_race_seed_api_report.json")

    checks = {
        "case_count_ok": demo_cases.get("case_count") == 6,
        "event_total_ok": demo_cases.get("event_total", 0) >= 18,
        "media_ready_ok": media.get("case_count") == 6 and media.get("blocked_slots") == 0,
        "control_wav_ok": media.get("control_wav_count") == 6,
        "race_seed_ok": race.get("ranked_candidate_count") == 6 and race.get("missing_candidate_count") == 0,
        "repair_closed_ok": repair.get("decision") == "PASS_REPAIR_CLOSED_QUEUE",
        "java_api_ok": java_report.get("decision") == "PASS_JAVA_MODEL_RACE_SEED_API_READY",
        "java_counts_ok": java_report.get("model_race_result_count") == 6 and java_report.get("repair_result_count") == 1,
    }

    synthetic_v2a_slots = int(media.get("synthetic_v2a_slots", 0))
    all_core_ok = all(checks.values())

    if all_core_ok and synthetic_v2a_slots > 0:
        decision = "PASS_CLOUD_DEMO_GATE_READY_WITH_SYNTHETIC_VIDEO_LIMITATION"
    elif all_core_ok:
        decision = "PASS_CLOUD_DEMO_GATE_READY"
    else:
        decision = "FAIL_CLOUD_DEMO_GATE"

    k6_path = shutil.which("k6")
    promtool_path = shutil.which("promtool")

    runtime_boundary = {
        "k6_available": bool(k6_path),
        "k6_path": k6_path or "",
        "promtool_available": bool(promtool_path),
        "promtool_path": promtool_path or "",
        "k6_claim": "not_run_in_this_step",
        "prometheus_rule_claim": "generated_not_validated" if not promtool_path else "generated_validation_possible",
        "production_slo_claim": "not_claimed",
    }

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "source": "cloud",
        "repo_heads": {
            "mainbase": git_head(str(mainbase)),
            "java": git_head(str(java)),
            "cloud": git_head(str(cloud_root)),
        },
        "checks": checks,
        "business_summary": {
            "case_count": demo_cases.get("case_count"),
            "event_total": demo_cases.get("event_total"),
            "candidate_slot_count": media.get("ready_slots"),
            "control_wav_count": media.get("control_wav_count"),
            "ranked_candidate_count": race.get("ranked_candidate_count"),
            "repair_closed_count": repair.get("repaired_to_winner_count"),
            "java_endpoint_count": len(java_report.get("endpoints", [])),
            "synthetic_v2a_slots": synthetic_v2a_slots,
        },
        "limitations": [
            "Cloud gate aggregates committed artifacts; it is not a live production SLO.",
            "Synthetic placeholder videos validate pipeline mechanics but cannot prove real V2A semantic quality.",
            "k6/promtool are reported as runtime boundary unless executed and validated explicitly.",
        ],
        "runtime_boundary": runtime_boundary,
        "next_action": "Commit this Cloud demo gate, then optionally add alert rule validation or k6 HTTP smoke only if the local runtime is available.",
    }

    write_json(base / "week17_model_race_cloud_gate.json", summary)
    write_json(base / "week17_model_race_dashboard_ready.json", {
        "generated_at": summary["generated_at"],
        "decision": decision,
        "panels": [
            {"title": "Demo case count", "value": demo_cases.get("case_count")},
            {"title": "DSS event total", "value": demo_cases.get("event_total")},
            {"title": "Control candidates", "value": media.get("control_wav_count")},
            {"title": "Ranked candidates", "value": race.get("ranked_candidate_count")},
            {"title": "Repair closed", "value": repair.get("repaired_to_winner_count")},
            {"title": "Synthetic V2A slots", "value": synthetic_v2a_slots},
        ],
        "source_artifact": "artifacts/demo/week17_model_race_cloud_gate/week17_model_race_cloud_gate.json",
    })

    write_json(cloud_root / "loadtest" / "reports" / "week17_model_race_cloud_gate.json", summary)

    metrics = [
        f'week17_demo_case_count {demo_cases.get("case_count", 0)}',
        f'week17_dss_event_total {demo_cases.get("event_total", 0)}',
        f'week17_control_wav_count {media.get("control_wav_count", 0)}',
        f'week17_ranked_candidate_count {race.get("ranked_candidate_count", 0)}',
        f'week17_repair_closed_count {repair.get("repaired_to_winner_count", 0)}',
        f'week17_synthetic_v2a_slots {synthetic_v2a_slots}',
        f'week17_java_model_race_result_count {java_report.get("model_race_result_count", 0)}',
        f'week17_cloud_gate_pass {1 if decision.startswith("PASS") else 0}',
    ]
    (cloud_root / "loadtest" / "reports" / "week17_model_race_cloud_gate_metrics.prom").write_text(
        "\n".join(metrics) + "\n",
        encoding="utf-8",
    )

    alert_rules = """groups:
- name: week17_model_race_cloud_gate
  rules:
  - alert: Week17ModelRaceCloudGateFailed
    expr: week17_cloud_gate_pass == 0
    for: 1m
    labels:
      severity: warning
    annotations:
      summary: Week17 model race cloud gate failed
      description: Cloud aggregation reports a failed demo gate.
  - alert: Week17SyntheticV2AInputsPresent
    expr: week17_synthetic_v2a_slots > 0
    for: 1m
    labels:
      severity: info
    annotations:
      summary: Synthetic V2A inputs remain in Week17 demo
      description: Synthetic placeholder videos validate pipeline mechanics but not real V2A semantic quality.
"""
    (cloud_root / "observability" / "prometheus" / "week17_model_race_cloud_gate_rules.yml").write_text(
        alert_rules,
        encoding="utf-8",
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if decision.startswith("PASS") else 2


if __name__ == "__main__":
    raise SystemExit(main())