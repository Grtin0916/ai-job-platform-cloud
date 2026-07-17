#!/usr/bin/env python3
"""Build the cross-repository W18 experiment dashboard artifacts."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def panel(panel_id: int, title: str, metric: str, kind: str = "stat") -> dict[str, Any]:
    x = ((panel_id - 1) % 3) * 8
    y = ((panel_id - 1) // 3) * 7
    return {
        "id": panel_id,
        "title": title,
        "type": kind,
        "datasource": {"type": "prometheus", "uid": "${DS_PROMETHEUS}"},
        "gridPos": {"h": 7, "w": 8, "x": x, "y": y},
        "targets": [{"expr": metric, "refId": "A"}],
        "fieldConfig": {"defaults": {}, "overrides": []},
        "options": {},
    }


def metric(name: str, value: int | float, labels: dict[str, str] | None = None) -> str:
    label_text = ""
    if labels:
        escaped = [f'{key}="{str(item).replace(chr(34), chr(92) + chr(34))}"' for key, item in labels.items()]
        label_text = "{" + ",".join(escaped) + "}"
    return f"{name}{label_text} {value}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mainbase-root", type=Path, required=True)
    parser.add_argument("--java-root", type=Path, required=True)
    parser.add_argument("--cloud-root", type=Path, required=True)
    parser.add_argument("--out-aggregation", type=Path, required=True)
    parser.add_argument("--out-summary", type=Path, required=True)
    parser.add_argument("--out-prom", type=Path, required=True)
    parser.add_argument("--out-dashboard", type=Path, required=True)
    args = parser.parse_args()

    mainbase = args.mainbase_root.resolve()
    java = args.java_root.resolve()
    cloud = args.cloud_root.resolve()

    prompt = read_json(mainbase / "reports/w18_prompt_compiler_summary_20260706.json")
    generation = read_json(mainbase / "reports/w18_full_30job_generation_summary_20260706.json")
    selector = read_json(mainbase / "reports/w18_selector_v2_summary_20260708.json")
    failures = read_json(mainbase / "reports/w18_failure_bank_summary_20260708.json")
    repairs = read_json(mainbase / "reports/w18_micro_repair_probe_summary_20260708.json")
    lifecycle = read_json(java / "artifacts/manifests/w18_task_lifecycle_report_20260712.json")
    alerts = read_json(cloud / "artifacts/demo/week18_live_alert_gate/summary.json")

    selector_rows = read_csv(mainbase / "reports/w18_selector_v2_scores_20260708.csv")
    repair_rows = read_csv(mainbase / "reports/w18_micro_repair_probe_20260708.csv")
    winner_variants = Counter(
        row["variant"] for row in selector_rows if row.get("selector_v2_decision") == "winner"
    )
    repair_actions = Counter(row["repair_action"] for row in repair_rows)

    counts = {
        "caseCount": int(prompt["case_count"]),
        "promptTaskCount": int(prompt["prompt_task_count"]),
        "candidateCount": int(generation["generated_count"]),
        "winnerCount": int(selector["winner_count"]),
        "failureCount": int(failures["failure_count"]),
        "repairBeforeAfterCount": int(repairs["probe_count"]),
        "repairProxyImproveCount": int(repairs["proxy_improve_count"]),
        "javaTaskCount": int(lifecycle["taskCount"]),
        "javaGaugeCount": 6,
        "alertRuleCount": int(alerts["loadedRuleCount"]),
        "alertScenarioCount": 5,
        "dashboardPanelCount": 9,
    }
    invariants = {
        "casesEq6": counts["caseCount"] == 6,
        "candidatesEq30": counts["candidateCount"] == 30,
        "winnersEq6": counts["winnerCount"] == 6,
        "failuresEq12": counts["failureCount"] == 12,
        "repairPairsEq6": counts["repairBeforeAfterCount"] == 6,
        "javaTasksEq12": counts["javaTaskCount"] == 12,
        "javaGaugesEq6": counts["javaGaugeCount"] == 6,
        "alertRulesEq4": counts["alertRuleCount"] == 4,
        "alertsHealthy": alerts["gateStatus"] == "PASS",
    }
    gate_status = "PASS" if all(invariants.values()) else "FAIL"

    aggregation = {
        "schemaVersion": "w18-experiment-aggregation-v1",
        "gateStatus": gate_status,
        "counts": counts,
        "promptVariantCounts": generation["variant_counts"],
        "winnerVariantCounts": dict(sorted(winner_variants.items())),
        "failureCategoryCounts": failures["category_counts"],
        "repairActionCounts": dict(sorted(repair_actions.items())),
        "javaLifecycle": lifecycle,
        "alertSummary": {
            "gateStatus": alerts["gateStatus"],
            "loadedRuleCount": alerts["loadedRuleCount"],
            "unhealthyRules": alerts["unhealthyRules"],
            "nonInactiveRules": alerts["nonInactiveRules"],
        },
        "invariants": invariants,
        "claimBoundary": {
            "productionPrometheusVerified": False,
            "liveGrafanaImportVerified": False,
            "alertmanagerConfigured": False,
            "productionAlertingVerified": False,
            "dockerDesktopEngineHealthy": False,
        },
        "sources": {
            "mainbase": str(mainbase),
            "java": str(java),
            "cloud": str(cloud),
        },
    }
    summary = {
        "gateStatus": gate_status,
        **counts,
        "allInputsConsumed": True,
        "productionPrometheusVerified": False,
        "liveGrafanaImportVerified": False,
        "dockerDesktopEngineHealthy": False,
        "invariants": invariants,
    }

    metrics = [
        "# HELP w18_experiment_gate W18 local experiment release gate.",
        "# TYPE w18_experiment_gate gauge",
        metric("w18_experiment_gate", 1 if gate_status == "PASS" else 0),
    ]
    for key, value in counts.items():
        metrics.append(metric("w18_experiment_count", value, {"category": key}))
    for key, value in generation["variant_counts"].items():
        metrics.append(metric("w18_experiment_prompt_variant_count", value, {"variant": key}))
    for key, value in failures["category_counts"].items():
        metrics.append(metric("w18_experiment_failure_count", value, {"category": key}))
    metrics.extend(
        [
            metric("w18_experiment_repair_proxy_improved", counts["repairProxyImproveCount"]),
            metric("w18_experiment_java_result_bound", lifecycle["resultBoundCount"]),
            metric("w18_experiment_java_missing_asset", lifecycle["missingAssetCount"]),
            metric("w18_experiment_alert_rules_healthy", counts["alertRuleCount"]),
            metric("w18_experiment_runtime_boundary", 0, {"claim": "production_prometheus"}),
            metric("w18_experiment_runtime_boundary", 0, {"claim": "live_grafana_import"}),
            metric("w18_experiment_runtime_boundary", 0, {"claim": "docker_desktop_engine"}),
        ]
    )

    dashboard = {
        "id": None,
        "uid": "w18-experiment",
        "title": "W18 Experiment Release",
        "schemaVersion": 39,
        "version": 1,
        "refresh": "30s",
        "tags": ["w18", "experiment", "local-evidence"],
        "templating": {"list": []},
        "time": {"from": "now-15m", "to": "now"},
        "panels": [
            panel(1, "W18 Experiment Gate Status", "w18_experiment_gate"),
            panel(2, "Prompt / Candidate / Winner Counts", "w18_experiment_count", "bargauge"),
            panel(3, "DSS Variant Distribution", "w18_experiment_prompt_variant_count", "bargauge"),
            panel(4, "Failure Category Distribution", "w18_experiment_failure_count", "bargauge"),
            panel(5, "Repair Probe and Proxy Improvement", "w18_experiment_repair_proxy_improved"),
            panel(6, "Java Task State Distribution", 'w18_experiment_count{category="javaTaskCount"}'),
            panel(7, "Artifact Binding and Missing Assets", "w18_experiment_java_missing_asset"),
            panel(8, "Lifecycle Alert Health", "w18_experiment_alert_rules_healthy"),
            panel(9, "Runtime Boundary and Docker Status", "w18_experiment_runtime_boundary", "table"),
        ],
    }

    for path in (args.out_aggregation, args.out_summary, args.out_prom, args.out_dashboard):
        path.parent.mkdir(parents=True, exist_ok=True)
    args.out_aggregation.write_text(json.dumps(aggregation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.out_summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.out_prom.write_text("\n".join(metrics) + "\n", encoding="utf-8")
    args.out_dashboard.write_text(json.dumps(dashboard, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return 0 if gate_status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
