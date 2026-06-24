#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CLOUD_REPO = Path(__file__).resolve().parents[1]
JAVA_REPO = Path.home() / "work/media-task-platform-java"
MAINBASE = Path.home() / "work/audio_engineering_repo_skeleton_v1"

JAVA_REPORT = JAVA_REPO / "artifacts/manifests/week17_layer_mix_v0_result_preview_api_report.json"
MAINBASE_MANIFEST = MAINBASE / "artifacts/evals/week17_layer_mix_v0_manifest.json"

OUT_JSON = CLOUD_REPO / "loadtest/reports/week17_layer_mix_v0_result_platform_preview.json"
OUT_PROM = CLOUD_REPO / "observability/prometheus/week17_layer_mix_v0_result_platform_preview.prom"
OUT_DASHBOARD = CLOUD_REPO / "observability/grafana/dashboards/week17_layer_mix_v0_result_platform_preview.json"
OUT_RUNBOOK = CLOUD_REPO / "docs/runbooks/week17-layer-mix-v0-result-platform-preview.md"


def git_head(repo: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
        text=True,
    ).strip()


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(msg)


def load_json(path: Path) -> Any:
    require(path.exists(), f"missing input: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def prom_escape(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def metric_line(name: str, labels: dict[str, object], value: object) -> str:
    label_text = ",".join(f'{k}="{prom_escape(v)}"' for k, v in sorted(labels.items()))
    return f"{name}{{{label_text}}} {value}"


def write_prometheus_text(path: Path, metrics: list[tuple[str, str, str, list[str]]]) -> None:
    seen = set()
    lines: list[str] = []
    for name, help_text, metric_type, samples in metrics:
        require(name not in seen, f"duplicate metric HELP/TYPE: {name}")
        seen.add(name)
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} {metric_type}")
        lines.extend(samples)
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    java = load_json(JAVA_REPORT)
    mainbase = load_json(MAINBASE_MANIFEST)

    cloud_head = git_head(CLOUD_REPO)
    java_head = git_head(JAVA_REPO)
    mainbase_head = git_head(MAINBASE)

    require(java.get("decision") == "PASS_WEEK17_LAYER_MIX_V0_RESULT_PREVIEW_API", "Java report decision not PASS")
    require(java.get("sourceMainbaseHead") == mainbase_head, "Java report sourceMainbaseHead != current Mainbase HEAD")
    require(java.get("sourceMainbaseHead") == mainbase_head == "d9a6df0", "unexpected Mainbase source head")
    require(java_head == "d6928dc", f"unexpected Java HEAD: {java_head}")
    require(java.get("focusedITPassed") is True, "Java focused IT did not pass")
    require(java.get("platformConsumable") is True, "Java report is not platformConsumable")
    require(java.get("readOnlyPreview") is True, "Java report is not readOnlyPreview")
    require(java.get("realWorkerTriggered") is False, "Java report unexpectedly claims worker trigger")
    require(java.get("databasePersistenceClaimed") is False, "Java report unexpectedly claims DB persistence")
    require(int(java.get("trackTotal")) == 7, "trackTotal must be 7")
    require(float(java.get("finalClipRateBeforeClip")) == 0.0, "clip rate must be 0")

    require(mainbase.get("decision") == "PASS_WEEK17_LAYER_MIX_V0_PLACEHOLDER_CONTROL", "Mainbase manifest decision not PASS")
    require(mainbase.get("placeholderInputOnly") is True, "Mainbase manifest must remain placeholder-only")
    require(mainbase.get("finalMixReadinessClaimed") is False, "Mainbase must not claim final mix readiness")

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_PROM.parent.mkdir(parents=True, exist_ok=True)
    OUT_DASHBOARD.parent.mkdir(parents=True, exist_ok=True)
    OUT_RUNBOOK.parent.mkdir(parents=True, exist_ok=True)

    final_rms = float(mainbase.get("finalRms", java.get("finalRms", 0.0)))
    final_peak = float(mainbase.get("finalPeak", java.get("finalPeak", 0.0)))
    final_clip = float(java.get("finalClipRateBeforeClip", 1.0))
    track_total = int(java.get("trackTotal", 0))

    platform_decision = "PASS_WEEK17_LAYER_MIX_V0_PLATFORM_PREVIEW"
    alert_decision = "NO_ALERT_PLACEHOLDER_CONTROL_MIX_HEALTHY"
    blocked_claims = [
        "livePrometheusScrapeClaimed",
        "liveGrafanaImportClaimed",
        "productionSloClaimed",
        "realCandidateAudioClaimed",
        "semanticAudioQualityPassClaimed",
        "humanReviewPassClaimed",
        "finalMixReadinessClaimed",
        "productionMixerAvailabilityClaimed",
    ]

    preview = {
        "schemaVersion": "week17.layer_mix_v0.result_platform_preview.v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "decision": platform_decision,
        "alertDecision": alert_decision,
        "cloudHeadBeforeCommit": cloud_head,
        "sourceJavaHead": java_head,
        "sourceMainbaseHead": mainbase_head,
        "sourceJavaReport": "artifacts/manifests/week17_layer_mix_v0_result_preview_api_report.json",
        "sourceMainbaseManifest": "artifacts/evals/week17_layer_mix_v0_manifest.json",
        "javaApiPath": java.get("apiPath"),
        "mixArtifactPath": java.get("mixArtifactPath"),
        "trackTotal": track_total,
        "selectedControlIds": mainbase.get("selectedControlIds"),
        "blockedInputIds": mainbase.get("blockedInputIds"),
        "finalPeak": final_peak,
        "finalRms": final_rms,
        "finalClipRateBeforeClip": final_clip,
        "placeholderInputOnly": True,
        "javaFocusedITPassed": True,
        "platformConsumable": True,
        "metricsReady": True,
        "dashboardReady": True,
        "runbookReady": True,
        "livePrometheusScrapeClaimed": False,
        "liveGrafanaImportClaimed": False,
        "productionSloClaimed": False,
        "realCandidateAudioClaimed": False,
        "semanticAudioQualityPassClaimed": False,
        "humanReviewPassClaimed": False,
        "finalMixReadinessClaimed": False,
        "productionMixerAvailabilityClaimed": False,
        "blockedClaims": blocked_claims,
        "nextPlatformAction": "Use this preview as the Cloud-side contract for W17 layer mix result observability before live service integration.",
    }

    OUT_JSON.write_text(json.dumps(preview, ensure_ascii=False, indent=2), encoding="utf-8")

    labels = {
        "decision": platform_decision,
        "alert_decision": alert_decision,
        "source_java_head": java_head,
        "source_mainbase_head": mainbase_head,
    }

    write_prometheus_text(
        OUT_PROM,
        [
            (
                "week17_layer_mix_v0_platform_preview_info",
                "Week17 layer mix v0 platform preview information.",
                "gauge",
                [metric_line("week17_layer_mix_v0_platform_preview_info", labels, 1)],
            ),
            (
                "week17_layer_mix_v0_track_total",
                "Number of tracks included in the Week17 layer mix v0 placeholder-control mix.",
                "gauge",
                [metric_line("week17_layer_mix_v0_track_total", labels, track_total)],
            ),
            (
                "week17_layer_mix_v0_final_peak",
                "Final peak amplitude of the Week17 layer mix v0 placeholder-control mix.",
                "gauge",
                [metric_line("week17_layer_mix_v0_final_peak", labels, final_peak)],
            ),
            (
                "week17_layer_mix_v0_final_rms",
                "Final RMS amplitude of the Week17 layer mix v0 placeholder-control mix.",
                "gauge",
                [metric_line("week17_layer_mix_v0_final_rms", labels, final_rms)],
            ),
            (
                "week17_layer_mix_v0_clip_rate_before_clip",
                "Clip rate before output clipping for the Week17 layer mix v0 placeholder-control mix.",
                "gauge",
                [metric_line("week17_layer_mix_v0_clip_rate_before_clip", labels, final_clip)],
            ),
            (
                "week17_layer_mix_v0_blocked_claim_total",
                "Number of explicit blocked claims preserved by the Cloud platform preview.",
                "gauge",
                [metric_line("week17_layer_mix_v0_blocked_claim_total", labels, len(blocked_claims))],
            ),
        ],
    )

    dashboard = {
        "title": "Week17 Layer Mix V0 Result Platform Preview",
        "uid": "week17-layer-mix-v0-result-preview",
        "timezone": "browser",
        "schemaVersion": 39,
        "version": 1,
        "refresh": "30s",
        "tags": ["week17", "layer-mix", "placeholder-control", "dashboard-ready"],
        "panels": [
            {
                "id": 1,
                "type": "stat",
                "title": "Platform Preview Pass",
                "targets": [{"expr": "week17_layer_mix_v0_platform_preview_info"}],
                "gridPos": {"h": 8, "w": 6, "x": 0, "y": 0},
            },
            {
                "id": 2,
                "type": "stat",
                "title": "Track Total",
                "targets": [{"expr": "week17_layer_mix_v0_track_total"}],
                "gridPos": {"h": 8, "w": 6, "x": 6, "y": 0},
            },
            {
                "id": 3,
                "type": "stat",
                "title": "Clip Rate Before Clip",
                "targets": [{"expr": "week17_layer_mix_v0_clip_rate_before_clip"}],
                "gridPos": {"h": 8, "w": 6, "x": 12, "y": 0},
            },
            {
                "id": 4,
                "type": "stat",
                "title": "Final RMS",
                "targets": [{"expr": "week17_layer_mix_v0_final_rms"}],
                "gridPos": {"h": 8, "w": 6, "x": 18, "y": 0},
            },
            {
                "id": 5,
                "type": "stat",
                "title": "Blocked Claims",
                "targets": [{"expr": "week17_layer_mix_v0_blocked_claim_total"}],
                "gridPos": {"h": 8, "w": 6, "x": 0, "y": 8},
            },
        ],
        "annotations": {
            "list": [
                {
                    "name": "Boundary",
                    "enable": True,
                    "iconColor": "rgba(255, 96, 96, 1)",
                    "type": "dashboard",
                }
            ]
        },
    }
    OUT_DASHBOARD.write_text(json.dumps(dashboard, ensure_ascii=False, indent=2), encoding="utf-8")

    OUT_RUNBOOK.write_text(
        "\n".join([
            "# Week17 Layer Mix V0 Result Platform Preview Runbook",
            "",
            "## Purpose",
            "",
            "Consume the Java Week17 layer mix v0 result preview evidence and render Cloud-side platform preview artifacts.",
            "",
            "## Inputs",
            "",
            f"- Java HEAD: `{java_head}`",
            f"- Mainbase HEAD: `{mainbase_head}`",
            "- Java report: `artifacts/manifests/week17_layer_mix_v0_result_preview_api_report.json`",
            "- Mainbase manifest: `artifacts/evals/week17_layer_mix_v0_manifest.json`",
            "",
            "## Outputs",
            "",
            f"- Platform preview JSON: `{OUT_JSON.relative_to(CLOUD_REPO)}`",
            f"- Prometheus metrics-ready text: `{OUT_PROM.relative_to(CLOUD_REPO)}`",
            f"- Grafana dashboard-ready JSON: `{OUT_DASHBOARD.relative_to(CLOUD_REPO)}`",
            "",
            "## Boundary",
            "",
            "- This is not a live Prometheus scrape.",
            "- This is not a live Grafana import.",
            "- This is not a production SLO.",
            "- This is not real generated candidate audio.",
            "- This is not semantic audio quality pass.",
            "- This is not human review pass.",
            "- This is not final mix readiness.",
            "- This is not production mixer availability.",
            "",
            "## Operator decision",
            "",
            f"- Decision: `{platform_decision}`",
            f"- Alert decision: `{alert_decision}`",
            f"- Track total: `{track_total}`",
            f"- Clip rate before clip: `{final_clip}`",
            "",
        ]),
        encoding="utf-8",
    )

    print(json.dumps({
        "decision": platform_decision,
        "alertDecision": alert_decision,
        "sourceJavaHead": java_head,
        "sourceMainbaseHead": mainbase_head,
        "trackTotal": track_total,
        "finalRms": final_rms,
        "finalClipRateBeforeClip": final_clip,
        "outputs": [
            str(OUT_JSON.relative_to(CLOUD_REPO)),
            str(OUT_PROM.relative_to(CLOUD_REPO)),
            str(OUT_DASHBOARD.relative_to(CLOUD_REPO)),
            str(OUT_RUNBOOK.relative_to(CLOUD_REPO)),
        ],
    }, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())