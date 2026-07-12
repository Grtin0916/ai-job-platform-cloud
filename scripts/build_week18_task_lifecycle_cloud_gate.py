#!/usr/bin/env python3
"""Build a Cloud gate from the Java Week18 lifecycle report."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


COUNT_KEYS = (
    "taskCount",
    "repairRequiredCount",
    "succeededCount",
    "repairAppliedCount",
    "resultBoundCount",
    "winnerCount",
    "repairProbeCount",
    "missingAssetCount",
    "orchestratedWinnerTaskCount",
    "orchestratedRepairTaskCount",
    "orchestratedTaskCount",
)


class GateInputError(ValueError):
    """Raised when a lifecycle report is structurally invalid."""


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise GateInputError(f"Input report does not exist: {path}")

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise GateInputError(
            f"Input report is not valid JSON: {path}"
        ) from exc

    if not isinstance(value, dict):
        raise GateInputError("Input report root must be an object")

    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def require_nonnegative_int(
    report: dict[str, Any],
    key: str,
) -> int:
    value = report.get(key)

    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
    ):
        raise GateInputError(
            f"{key} must be a non-negative integer, got {value!r}"
        )

    return value


def add_check(
    checks: list[dict[str, Any]],
    name: str,
    passed: bool,
    actual: Any,
    expected: Any,
) -> None:
    checks.append(
        {
            "name": name,
            "passed": bool(passed),
            "actual": actual,
            "expected": expected,
        }
    )


def build_gate_summary(
    report: dict[str, Any],
    input_path: Path,
) -> dict[str, Any]:
    counts = {
        key: require_nonnegative_int(report, key)
        for key in COUNT_KEYS
    }

    source_contract_sha256 = report.get(
        "sourceContractSha256",
        "",
    )

    sha256_is_valid = (
        isinstance(source_contract_sha256, str)
        and re.fullmatch(
            r"[0-9a-f]{64}",
            source_contract_sha256,
        )
        is not None
    )

    winner_expected = counts["winnerCount"]
    repair_expected = counts["repairProbeCount"]
    task_expected = winner_expected + repair_expected

    checks: list[dict[str, Any]] = []

    add_check(
        checks,
        "batch_orchestrated",
        report.get("batchOrchestrated") is True,
        report.get("batchOrchestrated"),
        True,
    )
    add_check(
        checks,
        "first_run_report_not_replayed",
        report.get("replayed") is False,
        report.get("replayed"),
        False,
    )
    add_check(
        checks,
        "winner_orchestration_matches_contract",
        counts["orchestratedWinnerTaskCount"]
        == winner_expected,
        counts["orchestratedWinnerTaskCount"],
        winner_expected,
    )
    add_check(
        checks,
        "winner_success_matches_contract",
        counts["succeededCount"] == winner_expected,
        counts["succeededCount"],
        winner_expected,
    )
    add_check(
        checks,
        "repair_orchestration_matches_contract",
        counts["orchestratedRepairTaskCount"]
        == repair_expected,
        counts["orchestratedRepairTaskCount"],
        repair_expected,
    )
    add_check(
        checks,
        "repair_required_matches_contract",
        counts["repairRequiredCount"] == repair_expected,
        counts["repairRequiredCount"],
        repair_expected,
    )
    add_check(
        checks,
        "repair_applied_matches_contract",
        counts["repairAppliedCount"] == repair_expected,
        counts["repairAppliedCount"],
        repair_expected,
    )
    add_check(
        checks,
        "task_total_matches_contract",
        counts["taskCount"] == task_expected,
        counts["taskCount"],
        task_expected,
    )
    add_check(
        checks,
        "orchestrated_total_matches_contract",
        counts["orchestratedTaskCount"] == task_expected,
        counts["orchestratedTaskCount"],
        task_expected,
    )
    add_check(
        checks,
        "all_results_bound",
        counts["resultBoundCount"] == counts["taskCount"],
        counts["resultBoundCount"],
        counts["taskCount"],
    )
    add_check(
        checks,
        "missing_assets_zero",
        counts["missingAssetCount"] == 0,
        counts["missingAssetCount"],
        0,
    )
    add_check(
        checks,
        "source_contract_sha256_valid",
        sha256_is_valid,
        source_contract_sha256,
        "64 lowercase hexadecimal characters",
    )
    add_check(
        checks,
        "production_slo_claim_preserved",
        report.get("productionSloVerified") is False,
        report.get("productionSloVerified"),
        False,
    )
    add_check(
        checks,
        "live_service_claim_preserved",
        report.get("liveServiceAvailabilityClaim") is False,
        report.get("liveServiceAvailabilityClaim"),
        False,
    )

    failed_checks = [
        item["name"]
        for item in checks
        if not item["passed"]
    ]

    gate_status = "PASS" if not failed_checks else "FAIL"

    return {
        "schemaVersion": "1.0",
        "gateName": "week18_task_lifecycle_cloud_gate",
        "generatedAtUtc": datetime.now(
            timezone.utc
        ).isoformat(),
        "gateStatus": gate_status,
        "inputReportPath": str(input_path),
        "inputReportSha256": sha256_file(input_path),
        "sourceContractSha256": source_contract_sha256,
        "counts": counts,
        "checks": checks,
        "failedChecks": failed_checks,
        "boundaries": {
            "productionSloVerified": False,
            "liveServiceAvailabilityClaim": False,
            "liveGrafanaImported": False,
        },
        "prometheusSampleReady": True,
        "dashboardReady": True,
    }


def render_metrics(summary: dict[str, Any]) -> str:
    counts = summary["counts"]
    gate_value = 1 if summary["gateStatus"] == "PASS" else 0

    categories = {
        "task_total": counts["taskCount"],
        "winner_succeeded": counts["succeededCount"],
        "repair_required": counts["repairRequiredCount"],
        "repair_applied": counts["repairAppliedCount"],
        "result_bound": counts["resultBoundCount"],
        "missing_asset": counts["missingAssetCount"],
    }

    lines = [
        "# HELP week18_task_lifecycle_gate_pass "
        "Whether the Java lifecycle artifact passed the Cloud gate.",
        "# TYPE week18_task_lifecycle_gate_pass gauge",
        f"week18_task_lifecycle_gate_pass {gate_value}",
        "# HELP week18_task_lifecycle_snapshot_tasks "
        "Task counts from the Java lifecycle artifact snapshot.",
        "# TYPE week18_task_lifecycle_snapshot_tasks gauge",
    ]

    for category, value in categories.items():
        lines.append(
            "week18_task_lifecycle_snapshot_tasks"
            f'{{category="{category}"}} {value}'
        )

    lines.extend(
        [
            "# HELP week18_task_lifecycle_boundary "
            "Claim-boundary flags preserved by the Cloud gate.",
            "# TYPE week18_task_lifecycle_boundary gauge",
            'week18_task_lifecycle_boundary'
            '{claim="production_slo_verified"} 0',
            'week18_task_lifecycle_boundary'
            '{claim="live_service_availability"} 0',
            'week18_task_lifecycle_boundary'
            '{claim="live_grafana_imported"} 0',
        ]
    )

    return "\n".join(lines) + "\n"


def stat_panel(
    panel_id: int,
    title: str,
    expression: str,
    x: int,
    y: int,
) -> dict[str, Any]:
    datasource = {
        "type": "prometheus",
        "uid": "${DS_PROMETHEUS}",
    }

    return {
        "id": panel_id,
        "type": "stat",
        "title": title,
        "datasource": datasource,
        "gridPos": {
            "h": 7,
            "w": 8,
            "x": x,
            "y": y,
        },
        "fieldConfig": {
            "defaults": {
                "mappings": [],
                "thresholds": {
                    "mode": "absolute",
                    "steps": [
                        {
                            "color": "red",
                            "value": None,
                        },
                        {
                            "color": "green",
                            "value": 1,
                        },
                    ],
                },
            },
            "overrides": [],
        },
        "options": {
            "colorMode": "value",
            "graphMode": "none",
            "justifyMode": "auto",
            "orientation": "auto",
            "reduceOptions": {
                "calcs": ["lastNotNull"],
                "fields": "",
                "values": False,
            },
            "textMode": "auto",
            "wideLayout": True,
        },
        "targets": [
            {
                "datasource": datasource,
                "editorMode": "code",
                "expr": expression,
                "legendFormat": title,
                "range": True,
                "refId": "A",
            }
        ],
    }


def build_dashboard() -> dict[str, Any]:
    panel_specs = [
        (
            1,
            "Lifecycle Gate",
            "week18_task_lifecycle_gate_pass",
            0,
            0,
        ),
        (
            2,
            "Tasks",
            'week18_task_lifecycle_snapshot_tasks'
            '{category="task_total"}',
            8,
            0,
        ),
        (
            3,
            "Winner Succeeded",
            'week18_task_lifecycle_snapshot_tasks'
            '{category="winner_succeeded"}',
            16,
            0,
        ),
        (
            4,
            "Repair Required",
            'week18_task_lifecycle_snapshot_tasks'
            '{category="repair_required"}',
            0,
            7,
        ),
        (
            5,
            "Repair Applied",
            'week18_task_lifecycle_snapshot_tasks'
            '{category="repair_applied"}',
            8,
            7,
        ),
        (
            6,
            "Results Bound",
            'week18_task_lifecycle_snapshot_tasks'
            '{category="result_bound"}',
            16,
            7,
        ),
    ]

    panels = [
        stat_panel(*spec)
        for spec in panel_specs
    ]

    return {
        "annotations": {
            "list": [],
        },
        "editable": True,
        "graphTooltip": 0,
        "panels": panels,
        "refresh": "30s",
        "schemaVersion": 39,
        "tags": [
            "week18",
            "task-lifecycle",
            "artifact-backed",
        ],
        "templating": {
            "list": [
                {
                    "name": "DS_PROMETHEUS",
                    "label": "Prometheus",
                    "type": "datasource",
                    "query": "prometheus",
                    "refresh": 1,
                    "multi": False,
                    "includeAll": False,
                    "options": [],
                }
            ]
        },
        "time": {
            "from": "now-15m",
            "to": "now",
        },
        "timezone": "browser",
        "title": "Week18 Task Lifecycle",
        "uid": "week18-task-lifecycle",
        "version": 1,
    }


def write_json(
    path: Path,
    value: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def build_gate_artifacts(
    input_path: Path,
    summary_path: Path,
    metrics_path: Path,
    dashboard_path: Path,
) -> dict[str, Any]:
    report = load_json(input_path)
    summary = build_gate_summary(report, input_path)

    write_json(summary_path, summary)

    metrics_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    metrics_path.write_text(
        render_metrics(summary),
        encoding="utf-8",
    )

    write_json(
        dashboard_path,
        build_dashboard(),
    )

    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--input",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--summary",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--metrics",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--dashboard",
        type=Path,
        required=True,
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    summary = build_gate_artifacts(
        input_path=args.input,
        summary_path=args.summary,
        metrics_path=args.metrics,
        dashboard_path=args.dashboard,
    )

    print(
        json.dumps(
            {
                "gateStatus": summary["gateStatus"],
                "failedChecks": summary["failedChecks"],
                "taskCount": summary["counts"]["taskCount"],
                "resultBoundCount": (
                    summary["counts"]["resultBoundCount"]
                ),
            },
            sort_keys=True,
        )
    )

    return 0 if summary["gateStatus"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())