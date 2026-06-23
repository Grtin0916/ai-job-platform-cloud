from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

JAVA_RERUN_PLAN_REPORT = ROOT / "loadtest/reports/week16_java_temporal_alignment_rerun_plan_report.json"
FAULT_DRILL_JSON = ROOT / "loadtest/reports/week16_failure_taxonomy_fault_drill.json"
FAULT_DRILL_METRICS = ROOT / "observability/prometheus/week16_failure_taxonomy_fault_drill_metrics.prom"
DASHBOARD_JSON = ROOT / "observability/grafana/dashboards/week16_failure_taxonomy_dashboard.json"

EXPECTED_BLOCKED_CLAIMS = {
    "semantic_audio_quality_pass_not_verified",
    "human_review_pass_not_verified",
    "final_mix_readiness_not_verified",
    "live_java_service_availability_not_verified",
    "live_prometheus_or_grafana_import_not_verified",
    "production_slo_or_real_cloud_deployment_not_verified",
}


SCENARIOS = [
    {
        "scenarioId": "service_unavailable",
        "platformSignal": {
            "availability": 0.0,
            "errorRatio": 1.0,
            "p95LatencyMs": None,
            "sampleWindow": "synthetic_fault_drill",
        },
        "expectedAlert": "CRITICAL_SERVICE_UNAVAILABLE",
        "alertSeverity": "critical",
        "recommendedAction": "Preserve rerun-plan evidence, block automated rerun execution, and escalate service availability recovery.",
    },
    {
        "scenarioId": "high_error_ratio",
        "platformSignal": {
            "availability": 1.0,
            "errorRatio": 0.35,
            "p95LatencyMs": 850,
            "sampleWindow": "synthetic_fault_drill",
        },
        "expectedAlert": "WARN_HIGH_ERROR_RATIO",
        "alertSeverity": "warning",
        "recommendedAction": "Do not reclassify candidate failure buckets; inspect Java API error path and retry budget before rerun scheduling.",
    },
    {
        "scenarioId": "high_latency",
        "platformSignal": {
            "availability": 1.0,
            "errorRatio": 0.0,
            "p95LatencyMs": 2500,
            "sampleWindow": "synthetic_fault_drill",
        },
        "expectedAlert": "WARN_HIGH_LATENCY",
        "alertSeverity": "warning",
        "recommendedAction": "Preserve previous attempts and delay rerun scheduling until latency returns within local drill threshold.",
    },
]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing required input: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"expected object JSON at {path}")
    return data


def blocked_claims_from_report(report: dict[str, Any]) -> list[str]:
    summary_claims = report.get("summary", {}).get("blockedClaims", [])
    if isinstance(summary_claims, list) and summary_claims:
        return [str(x) for x in summary_claims]

    implementation_boundary = report.get("implementationBoundary", [])
    if isinstance(implementation_boundary, list):
        return [str(x) for x in implementation_boundary]

    return sorted(EXPECTED_BLOCKED_CLAIMS)


def scenario_decision(scenario: dict[str, Any], source_pass: bool) -> str:
    signal = scenario["platformSignal"]

    if not source_pass:
        return "BLOCKED_SOURCE_JAVA_RERUN_PLAN_NOT_PASS"

    if signal["availability"] <= 0.0:
        return "ALERT_CRITICAL_BLOCK_RERUN"

    if signal["errorRatio"] >= 0.30:
        return "ALERT_WARNING_HOLD_RERUN"

    p95 = signal["p95LatencyMs"]
    if p95 is not None and p95 >= 2000:
        return "ALERT_WARNING_DELAY_RERUN"

    return "NO_ALERT_CONTINUE_OBSERVE"


def build_metrics(report: dict[str, Any], scenarios: list[dict[str, Any]], decision: str) -> str:
    summary = report.get("summary", {})
    lines: list[str] = []

    def metric_help_type(name: str, help_text: str, metric_type: str = "gauge") -> None:
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} {metric_type}")

    metric_help_type(
        "week16_failure_taxonomy_fault_drill_decision",
        "Week16 failure taxonomy fault drill decision, 1 means pass.",
    )
    lines.append(
        f'week16_failure_taxonomy_fault_drill_decision{{decision="{decision}"}} {1 if decision.startswith("PASS") else 0}'
    )

    metric_help_type(
        "week16_failure_taxonomy_fault_drill_source_candidate_total",
        "Candidate total inherited from Java rerun-plan report.",
    )
    lines.append(
        f'week16_failure_taxonomy_fault_drill_source_candidate_total {int(summary.get("candidateTotal", 0))}'
    )

    metric_help_type(
        "week16_failure_taxonomy_fault_drill_source_p1_rerun_fixture_total",
        "P1 actionable rerun fixture total inherited from Java rerun-plan report.",
    )
    lines.append(
        f'week16_failure_taxonomy_fault_drill_source_p1_rerun_fixture_total {int(summary.get("p1RegressionFixtureTotal", 0))}'
    )

    metric_help_type(
        "week16_failure_taxonomy_fault_drill_scenario_total",
        "Total number of synthetic fault drill scenarios.",
    )
    lines.append(f"week16_failure_taxonomy_fault_drill_scenario_total {len(scenarios)}")

    metric_help_type(
        "week16_failure_taxonomy_fault_drill_alert_total",
        "Fault drill alert count by alert severity.",
    )

    severity_counts: dict[str, int] = {}
    for scenario in scenarios:
        severity = scenario["alertSeverity"]
        severity_counts[severity] = severity_counts.get(severity, 0) + 1

    for severity, count in sorted(severity_counts.items()):
        lines.append(
            f'week16_failure_taxonomy_fault_drill_alert_total{{severity="{severity}"}} {count}'
        )

    metric_help_type(
        "week16_failure_taxonomy_fault_drill_scenario_signal",
        "Synthetic platform signal values by scenario and signal type.",
    )

    for scenario in scenarios:
        sid = scenario["scenarioId"]
        signal = scenario["platformSignal"]
        lines.append(
            f'week16_failure_taxonomy_fault_drill_scenario_signal{{scenario="{sid}",signal="availability"}} {float(signal["availability"])}'
        )
        lines.append(
            f'week16_failure_taxonomy_fault_drill_scenario_signal{{scenario="{sid}",signal="error_ratio"}} {float(signal["errorRatio"])}'
        )
        p95 = signal["p95LatencyMs"]
        if p95 is not None:
            lines.append(
                f'week16_failure_taxonomy_fault_drill_scenario_signal{{scenario="{sid}",signal="p95_latency_ms"}} {float(p95)}'
            )

    return "\n".join(lines) + "\n"


def build_dashboard(report: dict[str, Any], scenarios: list[dict[str, Any]], decision: str) -> dict[str, Any]:
    return {
        "schemaVersion": 39,
        "title": "Week16 Failure Taxonomy Fault Drill",
        "tags": ["week16", "failure-taxonomy", "fault-drill", "dashboard-ready"],
        "timezone": "browser",
        "editable": True,
        "panels": [
            {
                "id": 1,
                "type": "stat",
                "title": "Fault Drill Decision",
                "description": "Dashboard-ready only; not imported into live Grafana.",
                "targets": [
                    {
                        "expr": "week16_failure_taxonomy_fault_drill_decision",
                        "legendFormat": "{{decision}}",
                    }
                ],
            },
            {
                "id": 2,
                "type": "stat",
                "title": "Source Candidate Total",
                "targets": [
                    {
                        "expr": "week16_failure_taxonomy_fault_drill_source_candidate_total",
                        "legendFormat": "candidate_total",
                    }
                ],
            },
            {
                "id": 3,
                "type": "timeseries",
                "title": "Fault Drill Scenario Signals",
                "targets": [
                    {
                        "expr": "week16_failure_taxonomy_fault_drill_scenario_signal",
                        "legendFormat": "{{scenario}}/{{signal}}",
                    }
                ],
            },
            {
                "id": 4,
                "type": "bargauge",
                "title": "Alert Count by Severity",
                "targets": [
                    {
                        "expr": "week16_failure_taxonomy_fault_drill_alert_total",
                        "legendFormat": "{{severity}}",
                    }
                ],
            },
        ],
        "annotations": {
            "list": [
                {
                    "name": "Boundary",
                    "enable": True,
                    "type": "dashboard",
                    "text": "dashboard-ready artifact only; no live Grafana import or production SLO claim",
                }
            ]
        },
        "week16Source": {
            "sourceJavaDecision": report.get("decision"),
            "sourceMainbaseDecision": report.get("sourceMainbaseDecision"),
            "sourceClassificationMode": report.get("sourceClassificationMode"),
            "sourceSummary": report.get("summary"),
            "scenarioIds": [s["scenarioId"] for s in scenarios],
            "decision": decision,
        },
    }


def main() -> None:
    java_report = load_json(JAVA_RERUN_PLAN_REPORT)

    source_pass = java_report.get("decision") == "PASS_WEEK16_JAVA_RERUN_PLAN_IT"
    summary = java_report.get("summary", {})
    blocked_claims = blocked_claims_from_report(java_report)

    scenarios = []
    for item in SCENARIOS:
        scenario = dict(item)
        scenario["decision"] = scenario_decision(scenario, source_pass)
        scenario["blockedClaims"] = blocked_claims
        scenario["sourceBoundary"] = java_report.get("implementationBoundary", [])
        scenarios.append(scenario)

    decision_errors: list[str] = []
    if not source_pass:
        decision_errors.append("source Java rerun-plan report is not PASS")
    if int(summary.get("candidateTotal", 0)) != 10:
        decision_errors.append("candidateTotal expected 10")
    if int(summary.get("p1RegressionFixtureTotal", 0)) != 2:
        decision_errors.append("p1RegressionFixtureTotal expected 2")
    if int(summary.get("thresholdFixtureTotal", 0)) != 1:
        decision_errors.append("thresholdFixtureTotal expected 1")
    if int(summary.get("passControlTotal", 0)) != 7:
        decision_errors.append("passControlTotal expected 7")
    if int(summary.get("evidenceGapFixtureTotal", -1)) != 0:
        decision_errors.append("evidenceGapFixtureTotal expected 0")

    scenario_ids = {s["scenarioId"] for s in scenarios}
    if scenario_ids != {"service_unavailable", "high_error_ratio", "high_latency"}:
        decision_errors.append(f"unexpected scenario ids: {sorted(scenario_ids)}")

    if not EXPECTED_BLOCKED_CLAIMS.issubset(set(blocked_claims)):
        decision_errors.append("blocked claims boundary is incomplete")

    if not all(s["decision"].startswith("ALERT_") for s in scenarios):
        decision_errors.append("each synthetic scenario must produce an alert decision")

    decision = "PASS_WEEK16_FAILURE_TAXONOMY_FAULT_DRILL" if not decision_errors else "FAIL_WEEK16_FAILURE_TAXONOMY_FAULT_DRILL"

    out = {
        "schemaVersion": "week16.failure_taxonomy_fault_drill.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "decisionErrors": decision_errors,
        "sourceJavaReport": str(JAVA_RERUN_PLAN_REPORT.relative_to(ROOT)),
        "sourceJavaDecision": java_report.get("decision"),
        "sourceJavaApiEndpoint": java_report.get("apiEndpoint"),
        "sourceMainbaseDecision": java_report.get("sourceMainbaseDecision"),
        "sourceClassificationMode": java_report.get("sourceClassificationMode"),
        "summary": {
            "candidateTotal": int(summary.get("candidateTotal", 0)),
            "p1RegressionFixtureTotal": int(summary.get("p1RegressionFixtureTotal", 0)),
            "thresholdFixtureTotal": int(summary.get("thresholdFixtureTotal", 0)),
            "passControlTotal": int(summary.get("passControlTotal", 0)),
            "evidenceGapFixtureTotal": int(summary.get("evidenceGapFixtureTotal", 0)),
            "scenarioTotal": len(scenarios),
            "criticalAlertTotal": sum(1 for s in scenarios if s["alertSeverity"] == "critical"),
            "warningAlertTotal": sum(1 for s in scenarios if s["alertSeverity"] == "warning"),
            "blockedClaimTotal": len(blocked_claims),
            "blockedClaims": blocked_claims,
        },
        "scenarios": scenarios,
        "boundary": [
            "synthetic local fault drill only",
            "no live Java service availability claim",
            "no live Prometheus scrape claim",
            "no live Grafana import claim",
            "no production SLO or real cloud deployment claim",
            "no async rerun worker execution claim",
        ],
        "artifacts": {
            "faultDrillReport": str(FAULT_DRILL_JSON.relative_to(ROOT)),
            "prometheusMetrics": str(FAULT_DRILL_METRICS.relative_to(ROOT)),
            "grafanaDashboard": str(DASHBOARD_JSON.relative_to(ROOT)),
        },
    }

    FAULT_DRILL_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    FAULT_DRILL_METRICS.write_text(build_metrics(java_report, scenarios, decision), encoding="utf-8")
    DASHBOARD_JSON.write_text(json.dumps(build_dashboard(java_report, scenarios, decision), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"decision={decision}")
    print(f"decisionErrors={decision_errors}")
    print(f"sourceJavaDecision={out['sourceJavaDecision']}")
    print(f"sourceMainbaseDecision={out['sourceMainbaseDecision']}")
    print(f"sourceClassificationMode={out['sourceClassificationMode']}")
    print(f"summary={out['summary']}")

    for scenario in scenarios:
        print(
            f"scenario={scenario['scenarioId']} alertSeverity={scenario['alertSeverity']} "
            f"decision={scenario['decision']} expectedAlert={scenario['expectedAlert']}"
        )

    if decision_errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()