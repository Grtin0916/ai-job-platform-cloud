#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import subprocess
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

INPUT_PREVIEW = ROOT / "loadtest/reports/week17_layer_mix_v0_result_platform_preview.json"

OUT_JSON = ROOT / "loadtest/reports/week17_layer_mix_v0_action_gate.json"
OUT_CSV = ROOT / "loadtest/reports/week17_layer_mix_v0_action_gate.csv"
OUT_PROM = ROOT / "observability/prometheus/week17_layer_mix_v0_action_gate.prom"


EXPECTED_TRACK_TOTAL = 7
MAX_CLIP_RATE = 0.0
MIN_RMS = 0.01


def git_head(repo: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
        text=True,
    ).strip()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing input: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def prom_escape(v: object) -> str:
    return str(v).replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


def metric(name: str, labels: dict[str, object], value: object) -> str:
    label_text = ",".join(f'{k}="{prom_escape(v)}"' for k, v in sorted(labels.items()))
    return f"{name}{{{label_text}}} {value}"


def decide_case(case: dict[str, Any]) -> tuple[str, str, list[str]]:
    issues: list[str] = []

    track_total = int(case.get("trackTotal", -1))
    final_rms = float(case.get("finalRms", 0.0))
    clip_rate = float(case.get("finalClipRateBeforeClip", 1.0))

    if track_total != EXPECTED_TRACK_TOTAL:
        issues.append("TRACK_TOTAL_MISMATCH")
    if clip_rate > MAX_CLIP_RATE:
        issues.append("CLIP_RATE_ABOVE_ZERO")
    if final_rms <= MIN_RMS:
        issues.append("RMS_TOO_LOW_OR_SILENT")
    if case.get("finalMixReadinessClaimed") is True:
        issues.append("FINAL_MIX_READINESS_OVERCLAIM")
    if case.get("productionSloClaimed") is True:
        issues.append("PRODUCTION_SLO_OVERCLAIM")
    if case.get("livePrometheusScrapeClaimed") is True:
        issues.append("LIVE_PROMETHEUS_OVERCLAIM")
    if case.get("liveGrafanaImportClaimed") is True:
        issues.append("LIVE_GRAFANA_OVERCLAIM")

    if not issues:
        return (
            "PASS_WEEK17_LAYER_MIX_V0_ACTION_GATE",
            "ALLOW_PLACEHOLDER_CONTROL_PLATFORM_PREVIEW_ONLY",
            issues,
        )

    if any(x.endswith("OVERCLAIM") for x in issues):
        return (
            "BLOCK_WEEK17_LAYER_MIX_V0_ACTION_GATE",
            "BLOCK_OVERCLAIMED_CAPABILITY",
            issues,
        )

    if "CLIP_RATE_ABOVE_ZERO" in issues:
        return (
            "BLOCK_WEEK17_LAYER_MIX_V0_ACTION_GATE",
            "BLOCK_AUDIO_CLIPPING_RISK",
            issues,
        )

    if "TRACK_TOTAL_MISMATCH" in issues:
        return (
            "BLOCK_WEEK17_LAYER_MIX_V0_ACTION_GATE",
            "BLOCK_INCOMPLETE_LAYER_INPUT",
            issues,
        )

    return (
        "BLOCK_WEEK17_LAYER_MIX_V0_ACTION_GATE",
        "BLOCK_INVALID_AUDIO_ENERGY",
        issues,
    )


def build_scenarios(base: dict[str, Any]) -> list[dict[str, Any]]:
    scenarios = []

    healthy = deepcopy(base)
    healthy["scenarioId"] = "real_current_healthy_preview"
    healthy["scenarioKind"] = "real_current"
    scenarios.append(healthy)

    high_clip = deepcopy(base)
    high_clip["scenarioId"] = "synthetic_high_clip_rate"
    high_clip["scenarioKind"] = "negative_control"
    high_clip["finalClipRateBeforeClip"] = 0.025
    scenarios.append(high_clip)

    missing_track = deepcopy(base)
    missing_track["scenarioId"] = "synthetic_missing_track"
    missing_track["scenarioKind"] = "negative_control"
    missing_track["trackTotal"] = 6
    scenarios.append(missing_track)

    low_rms = deepcopy(base)
    low_rms["scenarioId"] = "synthetic_low_rms_silentish"
    low_rms["scenarioKind"] = "negative_control"
    low_rms["finalRms"] = 0.0
    scenarios.append(low_rms)

    overclaim = deepcopy(base)
    overclaim["scenarioId"] = "synthetic_final_mix_overclaim"
    overclaim["scenarioKind"] = "negative_control"
    overclaim["finalMixReadinessClaimed"] = True
    scenarios.append(overclaim)

    return scenarios


def write_prom(rows: list[dict[str, Any]]) -> None:
    lines: list[str] = []

    metrics = {
        "week17_layer_mix_v0_action_gate_pass": "Whether the Week17 layer mix v0 action gate passed for a scenario.",
        "week17_layer_mix_v0_action_gate_block": "Whether the Week17 layer mix v0 action gate blocked a scenario.",
        "week17_layer_mix_v0_action_gate_issue_total": "Number of issues detected by the Week17 layer mix v0 action gate.",
        "week17_layer_mix_v0_action_gate_track_total": "Track total observed by the Week17 layer mix v0 action gate.",
        "week17_layer_mix_v0_action_gate_clip_rate": "Clip rate observed by the Week17 layer mix v0 action gate.",
        "week17_layer_mix_v0_action_gate_final_rms": "Final RMS observed by the Week17 layer mix v0 action gate.",
    }

    for name, help_text in metrics.items():
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} gauge")

    for r in rows:
        labels = {
            "scenario": r["scenarioId"],
            "scenario_kind": r["scenarioKind"],
            "decision": r["decision"],
            "action": r["action"],
            "source_java_head": r["sourceJavaHead"],
            "source_mainbase_head": r["sourceMainbaseHead"],
        }
        passed = 1 if r["decision"].startswith("PASS_") else 0
        blocked = 1 if r["decision"].startswith("BLOCK_") else 0
        lines.append(metric("week17_layer_mix_v0_action_gate_pass", labels, passed))
        lines.append(metric("week17_layer_mix_v0_action_gate_block", labels, blocked))
        lines.append(metric("week17_layer_mix_v0_action_gate_issue_total", labels, len(r["issues"])))
        lines.append(metric("week17_layer_mix_v0_action_gate_track_total", labels, r["trackTotal"]))
        lines.append(metric("week17_layer_mix_v0_action_gate_clip_rate", labels, r["finalClipRateBeforeClip"]))
        lines.append(metric("week17_layer_mix_v0_action_gate_final_rms", labels, r["finalRms"]))

    lines.append("")
    OUT_PROM.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    base = load_json(INPUT_PREVIEW)

    if base.get("decision") != "PASS_WEEK17_LAYER_MIX_V0_PLATFORM_PREVIEW":
        raise RuntimeError(f"input preview is not PASS: {base.get('decision')}")
    if base.get("sourceJavaHead") != "d6928dc":
        raise RuntimeError(f"unexpected Java source head: {base.get('sourceJavaHead')}")
    if base.get("sourceMainbaseHead") != "d9a6df0":
        raise RuntimeError(f"unexpected Mainbase source head: {base.get('sourceMainbaseHead')}")

    cloud_head = git_head(ROOT)

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    OUT_PROM.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for s in build_scenarios(base):
        decision, action, issues = decide_case(s)
        rows.append({
            "scenarioId": s["scenarioId"],
            "scenarioKind": s["scenarioKind"],
            "decision": decision,
            "action": action,
            "issues": issues,
            "sourceJavaHead": s.get("sourceJavaHead"),
            "sourceMainbaseHead": s.get("sourceMainbaseHead"),
            "trackTotal": int(s.get("trackTotal", -1)),
            "finalPeak": float(s.get("finalPeak", 0.0)),
            "finalRms": float(s.get("finalRms", 0.0)),
            "finalClipRateBeforeClip": float(s.get("finalClipRateBeforeClip", 1.0)),
            "finalMixReadinessClaimed": bool(s.get("finalMixReadinessClaimed", False)),
            "productionSloClaimed": bool(s.get("productionSloClaimed", False)),
            "livePrometheusScrapeClaimed": bool(s.get("livePrometheusScrapeClaimed", False)),
            "liveGrafanaImportClaimed": bool(s.get("liveGrafanaImportClaimed", False)),
        })

    real_rows = [r for r in rows if r["scenarioKind"] == "real_current"]
    negative_rows = [r for r in rows if r["scenarioKind"] == "negative_control"]

    if len(real_rows) != 1:
        raise RuntimeError("expected exactly one real_current scenario")
    if not real_rows[0]["decision"].startswith("PASS_"):
        raise RuntimeError("real current scenario must PASS")
    if not all(r["decision"].startswith("BLOCK_") for r in negative_rows):
        raise RuntimeError("all negative controls must BLOCK")

    report = {
        "schemaVersion": "week17.layer_mix_v0.action_gate.v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "decision": "PASS_WEEK17_LAYER_MIX_V0_ACTION_GATE_WITH_NEGATIVE_CONTROLS",
        "cloudHeadBeforeCommit": cloud_head,
        "sourcePreview": str(INPUT_PREVIEW.relative_to(ROOT)),
        "scenarioTotal": len(rows),
        "realCurrentScenarioTotal": len(real_rows),
        "negativeControlTotal": len(negative_rows),
        "passScenarioTotal": sum(1 for r in rows if r["decision"].startswith("PASS_")),
        "blockScenarioTotal": sum(1 for r in rows if r["decision"].startswith("BLOCK_")),
        "realCurrentDecision": real_rows[0]["decision"],
        "realCurrentAction": real_rows[0]["action"],
        "negativeControlsAllBlocked": True,
        "expectedTrackTotal": EXPECTED_TRACK_TOTAL,
        "maxClipRate": MAX_CLIP_RATE,
        "minRms": MIN_RMS,
        "platformBehavior": "healthy preview is allowed as placeholder-control preview only; malformed or overclaimed mix results are blocked",
        "blockedClaimsPreserved": True,
        "livePrometheusScrapeClaimed": False,
        "liveGrafanaImportClaimed": False,
        "productionSloClaimed": False,
        "finalMixReadinessClaimed": False,
        "scenarios": rows,
    }
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "scenarioId",
                "scenarioKind",
                "decision",
                "action",
                "issues",
                "sourceJavaHead",
                "sourceMainbaseHead",
                "trackTotal",
                "finalPeak",
                "finalRms",
                "finalClipRateBeforeClip",
                "finalMixReadinessClaimed",
                "productionSloClaimed",
                "livePrometheusScrapeClaimed",
                "liveGrafanaImportClaimed",
            ],
        )
        writer.writeheader()
        for r in rows:
            x = dict(r)
            x["issues"] = "|".join(r["issues"])
            writer.writerow(x)

    write_prom(rows)

    print(json.dumps({
        "decision": report["decision"],
        "scenarioTotal": report["scenarioTotal"],
        "realCurrentDecision": report["realCurrentDecision"],
        "realCurrentAction": report["realCurrentAction"],
        "negativeControlsAllBlocked": report["negativeControlsAllBlocked"],
        "outputs": [
            str(OUT_JSON.relative_to(ROOT)),
            str(OUT_CSV.relative_to(ROOT)),
            str(OUT_PROM.relative_to(ROOT)),
        ],
    }, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())