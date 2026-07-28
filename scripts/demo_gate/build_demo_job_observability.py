#!/usr/bin/env python3
"""Build low-cardinality metrics, rules, dashboard, and a verification report."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from cloud_job_ledger import CloudJobLedger
from common import dump_json, load_json


PANELS = [
    ("Imported Jobs", "demo_cloud_job_records"),
    ("Execution Status", "demo_cloud_jobs_by_execution_status"),
    ("Publish Decision", "demo_cloud_jobs_by_publish_decision"),
    ("Provisional vs Final", "demo_cloud_release_records"),
    ("Replay vs Blocked", "demo_cloud_job_records"),
    ("Artifact Objects", "demo_cloud_artifact_objects"),
    ("Integrity Failures", "demo_cloud_artifact_integrity_failures"),
    ("Lease Contention", "demo_cloud_lease_conflicts_total"),
    ("Lease Recovery", "demo_cloud_expired_lease_takeovers_total"),
    ("Stale Fence Reject", "demo_cloud_stale_fence_rejections_total"),
    ("k6 Gate", "demo_cloud_k6_gate_pass"),
    ("Release Readiness", "demo_cloud_release_ready"),
]


def metric(name: str, value: int | float, labels: dict[str, str] | None = None) -> str:
    suffix = ""
    if labels:
        suffix = "{" + ",".join(f'{key}="{value}"' for key, value in sorted(labels.items())) + "}"
    return f"{name}{suffix} {value}"


def build(
    db: Path,
    artifact_index_path: Path,
    lease_report_path: Path,
    k6_exit_path: Path,
    k6_summary_path: Path,
    metrics_path: Path,
    rules_path: Path,
    rules_test_path: Path,
    dashboard_path: Path,
    provider_path: Path,
    report_path: Path,
) -> dict:
    ledger = CloudJobLedger(db)
    jobs = ledger.rows("jobs")
    attempts = ledger.rows("attempts")
    releases = ledger.rows("releases")
    counts = ledger.counts()
    ledger.close()
    artifacts = load_json(artifact_index_path)
    lease = load_json(lease_report_path)
    k6_exit = load_json(k6_exit_path) if k6_exit_path.is_file() else {"exitCode": 127}
    k6_summary = load_json(k6_summary_path) if k6_summary_path.is_file() else {}
    k6_executed = bool(k6_exit.get("executed", False))
    k6_passed = k6_executed and k6_exit.get("exitCode") == 0
    status_counts = Counter(item["execution_status"] for item in jobs)
    decision_counts = Counter(item["publish_decision"] for item in jobs)

    samples = [
        metric("demo_cloud_job_records", len(jobs)),
        metric("demo_cloud_job_attempts", len(attempts)),
        *[
            metric("demo_cloud_jobs_by_execution_status", count, {"status": status.lower()})
            for status, count in sorted(status_counts.items())
        ],
        *[
            metric("demo_cloud_jobs_by_publish_decision", count, {"decision": decision.lower()})
            for decision, count in sorted(decision_counts.items())
        ],
        metric("demo_cloud_release_records", len(releases)),
        metric("demo_cloud_artifact_objects", artifacts["uniqueObjectCount"]),
        metric("demo_cloud_artifact_integrity_failures", artifacts["integrityFailureCount"]),
        metric("demo_cloud_host_path_leaks", artifacts["hostPathLeakCount"]),
        metric("demo_cloud_lease_conflicts_total", int(lease["leaseContentionVerified"])),
        metric(
            "demo_cloud_expired_lease_takeovers_total",
            int(lease["expiredLeaseTakeoverVerified"]),
        ),
        metric("demo_cloud_stale_fence_rejections_total", int(lease["staleFenceRejected"])),
        metric("demo_cloud_k6_gate_pass", int(k6_passed)),
        metric("demo_cloud_release_ready", int(k6_passed and lease["verified"])),
        metric("demo_cloud_human_gate_ready", 0),
    ]
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.write_text("\n".join(samples) + "\n", encoding="utf-8")

    rules = """groups:
  - name: w20-demo-job-recording
    rules:
      - record: demo:execution_success_ratio
        expr: sum(demo_cloud_jobs_by_execution_status{status="succeeded"}) / clamp_min(sum(demo_cloud_jobs_by_execution_status), 1)
      - record: demo:artifact_integrity_ratio
        expr: 1 - (demo_cloud_artifact_integrity_failures / clamp_min(demo_cloud_artifact_objects, 1))
      - record: demo:lease_recovery_ratio
        expr: demo_cloud_expired_lease_takeovers_total / clamp_min(demo_cloud_lease_conflicts_total, 1)
      - record: demo:k6_gate_ready
        expr: demo_cloud_k6_gate_pass
      - record: demo:release_readiness
        expr: demo_cloud_release_ready
  - name: w20-demo-job-alerts
    rules:
      - alert: DemoArtifactIntegrityFailure
        expr: demo_cloud_artifact_integrity_failures > 0
      - alert: DemoContractDrift
        expr: demo_cloud_host_path_leaks > 0
      - alert: DemoLeaseStuck
        expr: demo_cloud_lease_conflicts_total > 0 and demo_cloud_expired_lease_takeovers_total == 0
      - alert: DemoStaleFenceWriteAttempt
        expr: demo_cloud_stale_fence_rejections_total > 0
      - alert: DemoK6GateFailure
        expr: demo_cloud_k6_gate_pass == 0
      - alert: DemoReleaseManifestBroken
        expr: demo_cloud_release_ready == 0
"""
    rules_path.parent.mkdir(parents=True, exist_ok=True)
    rules_path.write_text(rules, encoding="utf-8")
    rules_test_path.write_text(
        """rule_files:
  - w20_demo_job_rules.yml
evaluation_interval: 1m
tests:
  - interval: 1m
    input_series:
      - series: demo_cloud_artifact_integrity_failures
        values: 0
      - series: demo_cloud_artifact_objects
        values: 20
    promql_expr_test:
      - expr: demo:artifact_integrity_ratio
        eval_time: 0m
        exp_samples:
          - value: 1
""",
        encoding="utf-8",
    )

    dashboard = {
        "uid": "w20-demo-job-gate",
        "title": "W20 Durable Demo Job Gate",
        "schemaVersion": 39,
        "version": 1,
        "refresh": "30s",
        "panels": [
            {
                "id": number,
                "title": title,
                "type": "stat" if number not in (2, 3, 5) else "timeseries",
                "gridPos": {
                    "h": 8,
                    "w": 6,
                    "x": ((number - 1) % 4) * 6,
                    "y": ((number - 1) // 4) * 8,
                },
                "targets": [{"refId": "A", "expr": expression}],
            }
            for number, (title, expression) in enumerate(PANELS, 1)
        ],
    }
    dump_json(dashboard_path, dashboard)
    provider_path.parent.mkdir(parents=True, exist_ok=True)
    provider_path.write_text(
        """apiVersion: 1
providers:
  - name: w20-demo-job-gate
    type: file
    updateIntervalSeconds: 30
    options:
      path: /var/lib/grafana/dashboards/w20-demo-job-gate.json
""",
        encoding="utf-8",
    )
    report = {
        "jobCount": len(jobs),
        "attemptCount": len(attempts),
        "artifactObjectCount": artifacts["uniqueObjectCount"],
        "integrityFailureCount": artifacts["integrityFailureCount"],
        "hostPathLeakCount": artifacts["hostPathLeakCount"],
        "leaseRecoveryVerified": lease["verified"],
        "k6Executed": k6_executed,
        "k6ExitCode": k6_exit.get("exitCode"),
        "k6ThresholdPassed": k6_passed,
        "k6SummaryPresent": bool(k6_summary),
        "dashboardPanelCount": len(PANELS),
        "lowCardinalityMetricDesign": True,
        "productionPrometheusVerified": False,
        "productionAlertingVerified": False,
        "liveGrafanaImportVerified": False,
        "humanGateReady": False,
        "finalSelectionReady": False,
        "productionWorkflowVerified": False,
        "ledgerCounts": counts,
    }
    dump_json(report_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    for name in (
        "db",
        "artifact-index",
        "lease-report",
        "k6-exit",
        "k6-summary",
        "metrics",
        "rules",
        "rules-test",
        "dashboard",
        "provider",
        "report",
    ):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    report = build(
        args.db,
        args.artifact_index,
        args.lease_report,
        args.k6_exit,
        args.k6_summary,
        args.metrics,
        args.rules,
        args.rules_test,
        args.dashboard,
        args.provider,
        args.report,
    )
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
