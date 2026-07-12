#!/usr/bin/env python3
"""Tests for the Week18 lifecycle Cloud gate."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "scripts"
    / "build_week18_task_lifecycle_cloud_gate.py"
)

SPEC = importlib.util.spec_from_file_location(
    "week18_lifecycle_gate",
    SCRIPT,
)

if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load script: {SCRIPT}")

MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def valid_report() -> dict:
    return {
        "taskCount": 12,
        "repairRequiredCount": 6,
        "succeededCount": 6,
        "repairAppliedCount": 6,
        "resultBoundCount": 12,
        "winnerCount": 6,
        "repairProbeCount": 6,
        "missingAssetCount": 0,
        "sourceContractSha256": "a" * 64,
        "productionSloVerified": False,
        "liveServiceAvailabilityClaim": False,
        "batchOrchestrated": True,
        "replayed": False,
        "orchestratedWinnerTaskCount": 6,
        "orchestratedRepairTaskCount": 6,
        "orchestratedTaskCount": 12,
    }


class Week18LifecycleCloudGateTest(unittest.TestCase):

    def build(
        self,
        report: dict,
    ) -> tuple[dict, Path, Path]:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)

        root = Path(temp_dir.name)
        input_path = root / "input.json"
        summary_path = root / "summary.json"
        metrics_path = root / "metrics.prom"
        dashboard_path = root / "dashboard.json"

        input_path.write_text(
            json.dumps(report),
            encoding="utf-8",
        )

        summary = MODULE.build_gate_artifacts(
            input_path=input_path,
            summary_path=summary_path,
            metrics_path=metrics_path,
            dashboard_path=dashboard_path,
        )

        return summary, metrics_path, dashboard_path

    def test_valid_report_builds_pass_artifacts(self) -> None:
        summary, metrics_path, dashboard_path = self.build(
            valid_report()
        )

        self.assertEqual("PASS", summary["gateStatus"])
        self.assertEqual([], summary["failedChecks"])
        self.assertEqual(12, summary["counts"]["taskCount"])
        self.assertEqual(
            12,
            summary["counts"]["resultBoundCount"],
        )

        metrics = metrics_path.read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "week18_task_lifecycle_gate_pass 1",
            metrics,
        )
        self.assertIn(
            'category="repair_applied"} 6',
            metrics,
        )

        dashboard = json.loads(
            dashboard_path.read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(
            "week18-task-lifecycle",
            dashboard["uid"],
        )
        self.assertEqual(6, len(dashboard["panels"]))

    def test_missing_asset_produces_fail_gate(self) -> None:
        report = valid_report()
        report["missingAssetCount"] = 1

        summary, metrics_path, _ = self.build(report)

        self.assertEqual("FAIL", summary["gateStatus"])
        self.assertIn(
            "missing_assets_zero",
            summary["failedChecks"],
        )

        metrics = metrics_path.read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "week18_task_lifecycle_gate_pass 0",
            metrics,
        )


if __name__ == "__main__":
    unittest.main()