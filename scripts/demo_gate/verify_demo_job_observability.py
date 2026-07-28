#!/usr/bin/env python3
"""Validate generated metrics, rules, dashboard, and claim flags."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

from common import dump_json, load_json


FORBIDDEN_LABELS = ("jobId", "attemptId", "caseId", "sha256", "path")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--rules", type=Path, required=True)
    parser.add_argument("--rules-test", type=Path, required=True)
    parser.add_argument("--dashboard", type=Path, required=True)
    parser.add_argument("--build-report", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    metrics = args.metrics.read_text(encoding="utf-8")
    rules = args.rules.read_text(encoding="utf-8")
    dashboard = load_json(args.dashboard)
    build_report = load_json(args.build_report)
    metric_lines = [line for line in metrics.splitlines() if line and not line.startswith("#")]
    malformed = [
        line
        for line in metric_lines
        if not re.fullmatch(r"[a-zA-Z_:][a-zA-Z0-9_:]*(\{[^}]+\})? -?[0-9.]+", line)
    ]
    forbidden = [label for label in FORBIDDEN_LABELS if f"{label}=" in metrics]
    promtool = shutil.which("promtool")
    promtool_metrics = promtool_rules = promtool_tests = False
    outputs = {}
    if promtool:
        for key, command in {
            "metrics": [promtool, "check", "metrics"],
            "rules": [promtool, "check", "rules", str(args.rules)],
            "tests": [promtool, "test", "rules", str(args.rules_test)],
        }.items():
            result = subprocess.run(
                command,
                input=metrics if key == "metrics" else None,
                text=True,
                capture_output=True,
            )
            outputs[key] = {"exitCode": result.returncode, "output": result.stdout + result.stderr}
            if key == "metrics":
                promtool_metrics = result.returncode == 0
            elif key == "rules":
                promtool_rules = result.returncode == 0
            else:
                promtool_tests = result.returncode == 0
    report = {
        "verified": not malformed
        and not forbidden
        and len(dashboard.get("panels", [])) == 12
        and rules.count("- record:") == 5
        and rules.count("- alert:") == 6
        and build_report["productionWorkflowVerified"] is False,
        "metricSampleCount": len(metric_lines),
        "malformedMetricCount": len(malformed),
        "forbiddenHighCardinalityLabelCount": len(forbidden),
        "recordingRuleCount": rules.count("- record:"),
        "alertRuleCount": rules.count("- alert:"),
        "dashboardPanelCount": len(dashboard.get("panels", [])),
        "promtoolAvailable": bool(promtool),
        "promtoolMetricsVerified": promtool_metrics,
        "promtoolRulesVerified": promtool_rules,
        "promtoolRuleTestsVerified": promtool_tests,
        "liveGrafanaImportVerified": False,
        "productionPrometheusVerified": False,
        "productionAlertingVerified": False,
        "promtoolOutputs": outputs,
    }
    dump_json(args.out, report)
    print(json.dumps(report, sort_keys=True))
    raise SystemExit(0 if report["verified"] else 1)


if __name__ == "__main__":
    main()
