#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
from typing import Any


ROOT = Path.cwd()
JAVA = Path(os.environ.get("JAVA", str(Path.home() / "work" / "grt_work" / "media-task-platform-java")))
MAINBASE = Path(os.environ.get("MAINBASE", str(Path.home() / "work" / "grt_work" / "audio_engineering_repo_skeleton_v1")))

JAVA_REPORT = JAVA / "artifacts/manifests/week17_layer_mix_input_readiness_api_report.json"
MAINBASE_REPORT = MAINBASE / "artifacts/evals/week16_s3_to_w17_layer_mix_input.json"

OUT_JSON = ROOT / "loadtest/reports/week17_layer_mix_readiness_platform_preview.json"
OUT_PROM = ROOT / "observability/prometheus/week17_layer_mix_readiness_platform_preview.prom"
OUT_DASHBOARD = ROOT / "observability/grafana/dashboards/week17_layer_mix_readiness_platform_preview.json"
OUT_RUNBOOK = ROOT / "docs/runbooks/week17-layer-mix-readiness-platform-preview.md"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def count_value(d: dict[str, int], key: str) -> int:
    return int(d.get(key, 0))


def prom_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def main() -> int:
    if JAVA_REPORT.exists():
        source = "java_readiness_report"
        source_path = JAVA_REPORT
        payload = read_json(JAVA_REPORT)
        source_decision = str(payload.get("decision", "UNKNOWN"))
        source_mainbase_decision = str(payload.get("sourceDecision", "UNKNOWN"))
        candidate_total = int(payload.get("candidateTotal", 0))
        mix_counts = payload.get("mixEligibilityCounts", {}) or {}
        role_counts = payload.get("fixtureRoleCounts", {}) or {}
        blocked_claims = payload.get("blockedClaims", []) or []
        real_mixer_triggered = bool(payload.get("realMixerTriggered", True))
        real_worker_triggered = bool(payload.get("realWorkerTriggered", True))
    elif MAINBASE_REPORT.exists():
        source = "mainbase_readiness_report"
        source_path = MAINBASE_REPORT
        payload = read_json(MAINBASE_REPORT)
        source_decision = str(payload.get("decision", "UNKNOWN"))
        source_mainbase_decision = source_decision
        candidate_total = int(payload.get("candidateTotal", 0))
        mix_counts = payload.get("mixEligibilityCounts", {}) or {}
        role_counts = payload.get("fixtureRoleCounts", {}) or {}
        blocked_claims = payload.get("blockedClaims", []) or []
        real_mixer_triggered = False
        real_worker_triggered = False
    else:
        raise FileNotFoundError(f"Missing readiness source: {JAVA_REPORT} or {MAINBASE_REPORT}")

    automix_blocked = count_value(mix_counts, "BLOCK_AUTOMIX_REGRESSION_ONLY")
    control_only = count_value(mix_counts, "ELIGIBLE_CONTROL_ONLY")
    threshold_monitor = count_value(mix_counts, "MONITOR_ONLY_THRESHOLD_MARGIN")

    errors: list[str] = []
    if candidate_total != 10:
        errors.append(f"expected candidateTotal=10, got {candidate_total}")
    if role_counts.get("P1_PAIRED_REGRESSION_FIXTURE") != 2:
        errors.append("expected exactly 2 P1 paired regression fixtures")
    if role_counts.get("P2_THRESHOLD_MARGIN_FIXTURE") != 1:
        errors.append("expected exactly 1 P2 threshold-margin fixture")
    if role_counts.get("P4_NUMERIC_MARGIN_CONTROL") != 7:
        errors.append("expected exactly 7 P4 numeric-margin controls")
    if real_mixer_triggered:
        errors.append("realMixerTriggered must be false")
    if real_worker_triggered:
        errors.append("realWorkerTriggered must be false")

    decision = "PASS_WEEK17_LAYER_MIX_READINESS_PLATFORM_PREVIEW" if not errors else "FAIL_WEEK17_LAYER_MIX_READINESS_PLATFORM_PREVIEW"

    report = {
        "schemaVersion": "week17.layer_mix_readiness.platform_preview.v0",
        "generatedAtUtc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "decision": decision,
        "decisionErrors": errors,
        "source": source,
        "sourcePath": str(source_path),
        "sourceSha256": sha256(source_path),
        "sourceDecision": source_decision,
        "sourceMainbaseDecision": source_mainbase_decision,
        "summary": {
            "candidateTotal": candidate_total,
            "automixBlockedTotal": automix_blocked,
            "controlOnlyTotal": control_only,
            "thresholdMonitorTotal": threshold_monitor,
            "platformReadinessScore": round(control_only / candidate_total, 6) if candidate_total else 0.0,
        },
        "fixtureRoleCounts": role_counts,
        "mixEligibilityCounts": mix_counts,
        "alertProjection": {
            "automixBlockedAlert": automix_blocked > 0,
            "thresholdMonitorAlert": threshold_monitor > 0,
            "controlInputAvailable": control_only > 0,
            "dashboardReady": True,
            "metricsReady": True,
            "livePrometheusScrapeClaimed": False,
            "liveGrafanaImportClaimed": False,
            "productionSloClaimed": False,
        },
        "blockedClaims": sorted(set(blocked_claims + [
            "live Prometheus scrape",
            "live Grafana import",
            "production SLO",
            "final mix readiness",
            "semantic audio quality pass",
            "real layer mixer executed",
        ])),
    }

    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# HELP week17_layer_mix_readiness_candidates_total Total candidates seen by the W17 readiness platform preview.",
        "# TYPE week17_layer_mix_readiness_candidates_total gauge",
        f'week17_layer_mix_readiness_candidates_total{{source="{prom_escape(source)}"}} {candidate_total}',
        "# HELP week17_layer_mix_readiness_mix_eligibility_total Candidate count by mix eligibility.",
        "# TYPE week17_layer_mix_readiness_mix_eligibility_total gauge",
    ]
    for k, v in sorted(mix_counts.items()):
        lines.append(f'week17_layer_mix_readiness_mix_eligibility_total{{eligibility="{prom_escape(str(k))}"}} {int(v)}')

    lines.extend([
        "# HELP week17_layer_mix_readiness_fixture_role_total Candidate count by fixture role.",
        "# TYPE week17_layer_mix_readiness_fixture_role_total gauge",
    ])
    for k, v in sorted(role_counts.items()):
        lines.append(f'week17_layer_mix_readiness_fixture_role_total{{role="{prom_escape(str(k))}"}} {int(v)}')

    lines.extend([
        "# HELP week17_layer_mix_readiness_platform_gate_info Platform preview gate decision as labeled info metric.",
        "# TYPE week17_layer_mix_readiness_platform_gate_info gauge",
        f'week17_layer_mix_readiness_platform_gate_info{{decision="{prom_escape(decision)}",source_decision="{prom_escape(source_decision)}"}} 1',
        "# HELP week17_layer_mix_readiness_score Control-only candidates divided by candidate total.",
        "# TYPE week17_layer_mix_readiness_score gauge",
        f'week17_layer_mix_readiness_score {report["summary"]["platformReadinessScore"]}',
    ])
    OUT_PROM.write_text("\n".join(lines) + "\n", encoding="utf-8")

    dashboard = {
        "title": "Week17 Layer Mix Readiness Platform Preview",
        "schemaVersion": 1,
        "tags": ["week17", "layer-mix", "readiness", "artifact-ready"],
        "timezone": "browser",
        "panels": [
            {
                "type": "stat",
                "title": "Candidate Total",
                "targets": [{"expr": "week17_layer_mix_readiness_candidates_total"}],
            },
            {
                "type": "bargauge",
                "title": "Mix Eligibility",
                "targets": [{"expr": "week17_layer_mix_readiness_mix_eligibility_total"}],
            },
            {
                "type": "bargauge",
                "title": "Fixture Roles",
                "targets": [{"expr": "week17_layer_mix_readiness_fixture_role_total"}],
            },
            {
                "type": "stat",
                "title": "Readiness Score",
                "targets": [{"expr": "week17_layer_mix_readiness_score"}],
            },
        ],
        "annotations": {
            "list": [
                {
                    "name": "Non-claims",
                    "enable": True,
                    "text": "dashboard-ready only; no live Grafana import, no production SLO, no final mix readiness",
                }
            ]
        },
    }
    OUT_DASHBOARD.write_text(json.dumps(dashboard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    OUT_RUNBOOK.write_text(
        "# Week17 Layer-Mix Readiness Platform Preview\n\n"
        "## Purpose\n\n"
        "Consume the Java/Mainbase readiness artifact and render platform-preview evidence for W17 layer-mix input gating.\n\n"
        "## Boundary\n\n"
        "- This is metrics-ready and dashboard-ready evidence only.\n"
        "- It does not claim live Prometheus scrape.\n"
        "- It does not claim live Grafana import.\n"
        "- It does not claim production SLO.\n"
        "- It does not execute a real layer mixer.\n\n"
        "## Expected gate\n\n"
        "- 2 candidates blocked from automatic mix as P1 regression fixtures.\n"
        "- 1 candidate monitored as P2 threshold-margin fixture.\n"
        "- 7 candidates available as P4 control-only inputs.\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "decision": decision,
        "summary": report["summary"],
        "fixtureRoleCounts": role_counts,
        "mixEligibilityCounts": mix_counts,
        "outJson": str(OUT_JSON),
        "outProm": str(OUT_PROM),
        "outDashboard": str(OUT_DASHBOARD),
        "outRunbook": str(OUT_RUNBOOK),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())