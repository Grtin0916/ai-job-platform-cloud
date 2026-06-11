#!/usr/bin/env python3
"""
Render Week13 candidate bank platform readiness dashboard artifacts.

Inputs:
- Cloud Java API platform readiness gate JSON.

Outputs:
- Dashboard summary JSON.
- Grafana dashboard JSON.
- Grafana provisioning YAML stub.

Boundary:
- Dashboard-ready artifact only.
- Does not claim live Grafana import.
- Does not claim production SLO or alerting.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing required json: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def stat_panel(panel_id: int, title: str, value: Any, x: int, y: int, w: int = 6, h: int = 4) -> dict[str, Any]:
    return {
        "id": panel_id,
        "type": "stat",
        "title": title,
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "datasource": {"type": "grafana", "uid": "-- Grafana --"},
        "targets": [],
        "options": {
            "reduceOptions": {"values": False, "calcs": ["lastNotNull"], "fields": ""},
            "orientation": "auto",
            "textMode": "value_and_name",
            "colorMode": "value",
            "graphMode": "none",
            "justifyMode": "auto",
        },
        "fieldConfig": {
            "defaults": {
                "mappings": [
                    {
                        "type": "value",
                        "options": {
                            str(value): {"text": str(value)}
                        },
                    }
                ],
                "thresholds": {
                    "mode": "absolute",
                    "steps": [{"color": "green", "value": None}],
                },
            },
            "overrides": [],
        },
        "description": f"Static dashboard-ready value from Week13 gate: {value}",
    }


def text_panel(panel_id: int, title: str, markdown: str, x: int, y: int, w: int = 24, h: int = 7) -> dict[str, Any]:
    return {
        "id": panel_id,
        "type": "text",
        "title": title,
        "gridPos": {"h": h, "w": w, "x": x, "y": y},
        "options": {
            "mode": "markdown",
            "content": markdown,
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--gate",
        type=Path,
        default=Path("loadtest/reports/week13_java_api_platform_readiness_gate.json"),
    )
    ap.add_argument(
        "--summary-out",
        type=Path,
        default=Path("loadtest/reports/week13_candidate_bank_platform_readiness_dashboard_summary.json"),
    )
    ap.add_argument(
        "--dashboard-out",
        type=Path,
        default=Path("observability/grafana/dashboards/week13_candidate_bank_platform_readiness_dashboard.json"),
    )
    ap.add_argument(
        "--provisioning-out",
        type=Path,
        default=Path("observability/grafana/provisioning/dashboards/week13-candidate-bank-platform-readiness.yaml"),
    )
    args = ap.parse_args()

    gate = read_json(args.gate)
    test_summary = gate.get("testSummary", {})
    counts = gate.get("consumedCounts", {})
    cloud_worker = gate.get("cloudWorkerSmokeSummary", {})

    dashboard_values = {
        "status": gate.get("status"),
        "candidateCount": counts.get("candidateCount"),
        "workerSuccessCount": counts.get("workerSuccessCount"),
        "workerReadyCount": counts.get("workerReadyCount"),
        "materializedCount": counts.get("materializedCount"),
        "mountReadableCount": counts.get("mountReadableCount"),
        "testsRun": test_summary.get("testsRun"),
        "failures": test_summary.get("failures"),
        "errors": test_summary.get("errors"),
        "cloudWorkerSmokeStatus": cloud_worker.get("status"),
        "cloudWorkerSmokeSuccessCount": cloud_worker.get("workerSuccessCount"),
    }

    hard_checks = {
        "gateStatusPass": gate.get("status") == "PASS",
        "candidateCountIsTen": dashboard_values["candidateCount"] == 10,
        "workerSuccessCountIsTen": dashboard_values["workerSuccessCount"] == 10,
        "javaApiItNoFailures": dashboard_values["failures"] == 0,
        "javaApiItNoErrors": dashboard_values["errors"] == 0,
        "cloudWorkerSmokePass": dashboard_values["cloudWorkerSmokeStatus"] == "PASS",
        "cloudWorkerSmokeSuccessCountIsTen": dashboard_values["cloudWorkerSmokeSuccessCount"] == 10,
        "noGateBlockers": gate.get("blockers") == [],
    }

    status = "PASS" if all(hard_checks.values()) else "FAIL"

    summary = {
        "schemaVersion": "week13.cloud_candidate_bank_platform_readiness_dashboard_summary.v1",
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "scope": "dashboard-ready-summary-only",
        "sourceGate": str(args.gate),
        "dashboardJson": str(args.dashboard_out),
        "provisioningStub": str(args.provisioning_out),
        "dashboardValues": dashboard_values,
        "hardChecks": hard_checks,
        "blockers": [] if status == "PASS" else [k for k, v in hard_checks.items() if not v],
        "boundary": [
            "does_not_claim_live_grafana_import",
            "does_not_claim_production_slo",
            "does_not_claim_production_alerting",
            "does_not_claim_live_java_service_probe",
            "does_not_claim_production_kubernetes_job",
            "does_not_claim_s3_minio_csi_or_cloud_object_storage",
        ],
    }

    markdown = "\n".join([
        "### Week13 Candidate Bank Platform Readiness",
        "",
        f"- Status: **{gate.get('status')}**",
        f"- Endpoint: `{gate.get('endpoint')}`",
        f"- Test mode: `{gate.get('testMode')}`",
        f"- Java API IT: tests={test_summary.get('testsRun')}, failures={test_summary.get('failures')}, errors={test_summary.get('errors')}",
        f"- Candidate count: {counts.get('candidateCount')}",
        f"- Worker success count: {counts.get('workerSuccessCount')}",
        f"- Cloud worker smoke: {cloud_worker.get('status')} / success={cloud_worker.get('workerSuccessCount')}",
        "",
        "Boundary: dashboard-ready JSON only; not a live Grafana import, not production SLO, not production alerting.",
    ])

    dashboard = {
        "id": None,
        "uid": "week13-candidate-bank-platform-readiness",
        "title": "Week13 Candidate Bank Platform Readiness",
        "tags": ["week13", "candidate-bank", "platform-readiness", "local-demo"],
        "timezone": "browser",
        "schemaVersion": 39,
        "version": 1,
        "refresh": "",
        "panels": [
            text_panel(1, "Readiness decision", markdown, 0, 0, 24, 7),
            stat_panel(2, "Gate status", dashboard_values["status"], 0, 7),
            stat_panel(3, "Candidate count", dashboard_values["candidateCount"], 6, 7),
            stat_panel(4, "Worker success count", dashboard_values["workerSuccessCount"], 12, 7),
            stat_panel(5, "Cloud worker smoke", dashboard_values["cloudWorkerSmokeStatus"], 18, 7),
            stat_panel(6, "Java API tests run", dashboard_values["testsRun"], 0, 11),
            stat_panel(7, "Java API failures", dashboard_values["failures"], 6, 11),
            stat_panel(8, "Java API errors", dashboard_values["errors"], 12, 11),
            stat_panel(9, "Mount readable count", dashboard_values["mountReadableCount"], 18, 11),
        ],
        "templating": {"list": []},
        "annotations": {"list": []},
        "time": {"from": "now-6h", "to": "now"},
    }

    provisioning = "\n".join([
        "apiVersion: 1",
        "",
        "providers:",
        "  - name: week13-candidate-bank-platform-readiness",
        "    orgId: 1",
        "    folder: Week13",
        "    type: file",
        "    disableDeletion: false",
        "    editable: true",
        "    options:",
        "      path: /etc/grafana/provisioning/dashboards",
        "",
    ])

    args.summary_out.parent.mkdir(parents=True, exist_ok=True)
    args.dashboard_out.parent.mkdir(parents=True, exist_ok=True)
    args.provisioning_out.parent.mkdir(parents=True, exist_ok=True)

    args.summary_out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.dashboard_out.write_text(json.dumps(dashboard, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    args.provisioning_out.write_text(provisioning, encoding="utf-8")

    print(json.dumps({
        "summaryOut": str(args.summary_out),
        "dashboardOut": str(args.dashboard_out),
        "provisioningOut": str(args.provisioning_out),
        "status": status,
        "dashboardValues": dashboard_values,
        "failedChecks": summary["blockers"],
    }, indent=2, ensure_ascii=False))

    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())