from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CLOUD_ROOT = Path(".").resolve()
JAVA_ROOT = Path.home() / "work/grt_work/media-task-platform-java"
MAINBASE_ROOT = Path.home() / "work/grt_work/audio_engineering_repo_skeleton_v1"

JAVA_REPORT = JAVA_ROOT / "artifacts/manifests/week17_true_aware_result_card/week17_true_aware_result_card_api_report.json"
JAVA_BRIDGE = JAVA_ROOT / "artifacts/manifests/week17_true_aware_result_card/week17_true_aware_platform_bridge_payload_20260702.json"
JAVA_GUARD = JAVA_ROOT / "artifacts/manifests/week17_true_aware_result_card/week17_true_aware_claim_guard_20260702.json"
MAINBASE_BRIDGE = MAINBASE_ROOT / "reports/week17_true_aware_platform_bridge_payload_20260702.json"

OUT_DIR = CLOUD_ROOT / "artifacts/demo/week17_true_aware_result_card_cloud_gate"
INPUT_DIR = OUT_DIR / "inputs"

OUT_GATE = OUT_DIR / "week17_true_aware_result_card_cloud_gate.json"
OUT_DASHBOARD_READY = OUT_DIR / "week17_true_aware_result_card_dashboard_ready.json"
OUT_LOADTEST_REPORT = CLOUD_ROOT / "loadtest/reports/week17_true_aware_result_card_cloud_gate.json"
OUT_METRICS = CLOUD_ROOT / "loadtest/reports/week17_true_aware_result_card_metrics.prom"
OUT_PROM = CLOUD_ROOT / "observability/prometheus/week17_true_aware_result_card.prom"
OUT_RULES = CLOUD_ROOT / "observability/prometheus/week17_true_aware_result_card.rules.yml"
OUT_DASHBOARD = CLOUD_ROOT / "observability/grafana/dashboards/week17_true_aware_result_card_dashboard.json"
OUT_RUNBOOK = CLOUD_ROOT / "docs/runbooks/week17-true-aware-result-card-cloud-gate.md"


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return data


def copy_input(src: Path) -> str:
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    dst = INPUT_DIR / src.name
    shutil.copy2(src, dst)
    return str(dst)


def as_int(value: Any) -> int:
    try:
        if isinstance(value, bool):
            return 1 if value else 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def bool_metric(value: Any) -> int:
    return 1 if bool(value) else 0


def write_prometheus_metrics(metrics: dict[str, int]) -> str:
    lines = [
        "# HELP soundlayer_true_aware_single_success Whether one true MMAudio V2A candidate is safely available.",
        "# TYPE soundlayer_true_aware_single_success gauge",
        f"soundlayer_true_aware_single_success {metrics['single_success']}",
        "# HELP soundlayer_true_aware_safe_true_mmaudio_record_count Claim-safe true MMAudio artifact count.",
        "# TYPE soundlayer_true_aware_safe_true_mmaudio_record_count gauge",
        f"soundlayer_true_aware_safe_true_mmaudio_record_count {metrics['safe_true_count']}",
        "# HELP soundlayer_true_aware_raw_candidate_record_count Raw candidate context record count.",
        "# TYPE soundlayer_true_aware_raw_candidate_record_count gauge",
        f"soundlayer_true_aware_raw_candidate_record_count {metrics['raw_candidate_count']}",
        "# HELP soundlayer_true_aware_batch_success Whether true MMAudio batch success is verified.",
        "# TYPE soundlayer_true_aware_batch_success gauge",
        f"soundlayer_true_aware_batch_success {metrics['batch_success']}",
        "# HELP soundlayer_true_aware_full_ranking_available Whether full candidate ranking is verified.",
        "# TYPE soundlayer_true_aware_full_ranking_available gauge",
        f"soundlayer_true_aware_full_ranking_available {metrics['full_ranking']}",
        "# HELP soundlayer_true_aware_production_slo_verified Whether production SLO is verified.",
        "# TYPE soundlayer_true_aware_production_slo_verified gauge",
        f"soundlayer_true_aware_production_slo_verified {metrics['production_slo']}",
        "# HELP soundlayer_true_aware_k6_threshold_pass_verified Whether k6 threshold pass is verified.",
        "# TYPE soundlayer_true_aware_k6_threshold_pass_verified gauge",
        f"soundlayer_true_aware_k6_threshold_pass_verified {metrics['k6_pass']}",
        "",
    ]
    return "\n".join(lines)


def write_alert_rules() -> str:
    return """groups:
  - name: week17_true_aware_result_card
    rules:
      - alert: Week17TrueAwareSingleCandidateMissing
        expr: soundlayer_true_aware_single_success < 1
        for: 0m
        labels:
          severity: warning
          scope: demo-gate
        annotations:
          summary: "Week17 true-aware single candidate is not available"
          description: "The Cloud demo gate requires one claim-safe true MMAudio candidate before Friday demo packaging."

      - alert: Week17TrueAwareClaimInflationRisk
        expr: soundlayer_true_aware_batch_success > 0 or soundlayer_true_aware_full_ranking_available > 0
        for: 0m
        labels:
          severity: critical
          scope: claim-boundary
        annotations:
          summary: "Week17 true-aware claim boundary was inflated"
          description: "This gate must not claim true MMAudio batch success or full candidate ranking availability."
"""


def write_dashboard(metrics: dict[str, int]) -> dict[str, Any]:
    return {
        "title": "Week17 True-aware Result Card Gate",
        "uid": "week17-true-aware-result-card",
        "schemaVersion": 39,
        "version": 1,
        "refresh": "30s",
        "tags": ["week17", "true-aware", "demo-gate", "soundlayer"],
        "panels": [
            {
                "type": "stat",
                "title": "Single true MMAudio available",
                "gridPos": {"x": 0, "y": 0, "w": 6, "h": 4},
                "targets": [{"expr": "soundlayer_true_aware_single_success"}],
            },
            {
                "type": "stat",
                "title": "Safe true count",
                "gridPos": {"x": 6, "y": 0, "w": 6, "h": 4},
                "targets": [{"expr": "soundlayer_true_aware_safe_true_mmaudio_record_count"}],
            },
            {
                "type": "stat",
                "title": "Raw candidate context",
                "gridPos": {"x": 12, "y": 0, "w": 6, "h": 4},
                "targets": [{"expr": "soundlayer_true_aware_raw_candidate_record_count"}],
            },
            {
                "type": "stat",
                "title": "Forbidden batch claim",
                "gridPos": {"x": 18, "y": 0, "w": 6, "h": 4},
                "targets": [{"expr": "soundlayer_true_aware_batch_success"}],
            },
        ],
        "week17SeedValues": metrics,
        "boundary": "Dashboard seed only. No live Grafana import, no production SLO, no k6 threshold pass claimed.",
    }


def main() -> None:
    java_report = load_json(JAVA_REPORT)
    java_bridge = load_json(JAVA_BRIDGE)
    java_guard = load_json(JAVA_GUARD)
    mainbase_bridge = load_json(MAINBASE_BRIDGE)

    strict = java_report.get("strict_boundary", {})
    card = java_report.get("platform_result_card", {})

    single_success = strict.get("true_mmaudio_single_success") is True
    safe_true_count = as_int(card.get("safe_true_mmaudio_record_count"))
    raw_candidate_count = as_int(card.get("raw_candidate_record_count"))
    batch_success = strict.get("true_mmaudio_batch_success") is True
    full_ranking = strict.get("full_candidate_ranking_available") is True
    production_slo = strict.get("production_slo_verified") is True
    k6_pass = strict.get("k6_threshold_pass_verified") is True

    ready_for_friday_demo_pack = (
        single_success
        and safe_true_count == 1
        and raw_candidate_count >= 1
        and not batch_success
        and not full_ranking
        and not production_slo
        and not k6_pass
    )

    copied_inputs = {
        "java_api_report": copy_input(JAVA_REPORT),
        "java_bridge": copy_input(JAVA_BRIDGE),
        "java_claim_guard": copy_input(JAVA_GUARD),
        "mainbase_bridge": copy_input(MAINBASE_BRIDGE),
    }

    gate = {
        "schema_version": "week17.true_aware.cloud_gate.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_repo_role": "cloud",
        "input_contracts": copied_inputs,
        "decision": {
            "readyForFridayDemoPack": ready_for_friday_demo_pack,
            "cloudGateSeedReady": True,
            "javaResultCardApiReady": card.get("status") == "consumer_ready",
            "singleTrueMmaudioAvailable": single_success,
            "safeTrueMmaudioRecordCount": safe_true_count,
            "rawCandidateRecordCount": raw_candidate_count,
            "trueMmaudioBatchSuccess": batch_success,
            "fullCandidateRankingAvailable": full_ranking,
            "productionSloVerified": production_slo,
            "k6ThresholdPassVerified": k6_pass,
        },
        "runtime_boundary": {
            "dashboardSeedOnly": True,
            "prometheusMetricsSampleOnly": True,
            "liveGrafanaImportVerified": False,
            "promtoolVerifiedInThisRun": False,
            "k6ThresholdExecutedInThisRun": False,
            "productionSloClaimAllowed": False,
        },
        "claim_guard": java_guard,
        "java_api_report_summary": {
            "endpoints": java_report.get("endpoints", []),
            "strict_boundary": strict,
            "platform_result_card": card,
        },
        "mainbase_bridge_status": mainbase_bridge.get("platform_result_card", {}).get("status"),
        "next_step": "Build Friday demo pack using single=true, batch=false, fullRanking=false.",
    }

    metrics = {
        "single_success": bool_metric(single_success),
        "safe_true_count": safe_true_count,
        "raw_candidate_count": raw_candidate_count,
        "batch_success": bool_metric(batch_success),
        "full_ranking": bool_metric(full_ranking),
        "production_slo": bool_metric(production_slo),
        "k6_pass": bool_metric(k6_pass),
    }

    dashboard_ready = {
        "schema_version": "week17.true_aware.dashboard_ready.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "dashboard_ready": True,
        "dashboard_path": str(OUT_DASHBOARD),
        "metrics_path": str(OUT_METRICS),
        "rules_path": str(OUT_RULES),
        "seed_values": metrics,
        "boundary": "Ready as seed artifacts only; no live dashboard import or production SLO verification claimed.",
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_LOADTEST_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_METRICS.parent.mkdir(parents=True, exist_ok=True)
    OUT_PROM.parent.mkdir(parents=True, exist_ok=True)
    OUT_RULES.parent.mkdir(parents=True, exist_ok=True)
    OUT_DASHBOARD.parent.mkdir(parents=True, exist_ok=True)
    OUT_RUNBOOK.parent.mkdir(parents=True, exist_ok=True)

    OUT_GATE.write_text(json.dumps(gate, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_DASHBOARD_READY.write_text(json.dumps(dashboard_ready, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_LOADTEST_REPORT.write_text(json.dumps(gate, ensure_ascii=False, indent=2), encoding="utf-8")

    prom_text = write_prometheus_metrics(metrics)
    OUT_METRICS.write_text(prom_text, encoding="utf-8")
    OUT_PROM.write_text(prom_text, encoding="utf-8")
    OUT_RULES.write_text(write_alert_rules(), encoding="utf-8")
    OUT_DASHBOARD.write_text(json.dumps(write_dashboard(metrics), ensure_ascii=False, indent=2), encoding="utf-8")

    OUT_RUNBOOK.write_text(
        """# Week17 True-aware Result Card Cloud Gate

This gate consumes the Java true-aware result-card API report and converts the claim-safe single true MMAudio result into Cloud demo-gate seed artifacts.

## Decision

- `readyForFridayDemoPack=true` means the Friday demo pack can proceed with one true video-conditioned candidate.
- It does not mean true MMAudio batch success.
- It does not mean full candidate ranking availability.
- It does not mean production SLO verification.
- It does not mean k6 threshold pass.

## Generated artifacts

- `artifacts/demo/week17_true_aware_result_card_cloud_gate/week17_true_aware_result_card_cloud_gate.json`
- `loadtest/reports/week17_true_aware_result_card_cloud_gate.json`
- `loadtest/reports/week17_true_aware_result_card_metrics.prom`
- `observability/prometheus/week17_true_aware_result_card.prom`
- `observability/prometheus/week17_true_aware_result_card.rules.yml`
- `observability/grafana/dashboards/week17_true_aware_result_card_dashboard.json`
""",
        encoding="utf-8",
    )

    if not ready_for_friday_demo_pack:
        raise RuntimeError("Cloud gate generated but readyForFridayDemoPack=false")

    print("WROTE", OUT_GATE)
    print("WROTE", OUT_DASHBOARD_READY)
    print("WROTE", OUT_LOADTEST_REPORT)
    print("WROTE", OUT_METRICS)
    print("WROTE", OUT_PROM)
    print("WROTE", OUT_RULES)
    print("WROTE", OUT_DASHBOARD)
    print("WROTE", OUT_RUNBOOK)
    print("READY_FOR_FRIDAY_DEMO_PACK=", ready_for_friday_demo_pack)
    print("SAFE_TRUE_MMAUDIO_RECORD_COUNT=", safe_true_count)
    print("RAW_CANDIDATE_RECORD_COUNT=", raw_candidate_count)


if __name__ == "__main__":
    main()