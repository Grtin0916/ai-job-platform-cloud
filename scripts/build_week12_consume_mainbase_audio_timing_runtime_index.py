#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List


CLOUD_ROOT = Path(__file__).resolve().parents[1]
MAINBASE_ROOT = Path(os.environ.get(
    "MAINBASE_PATH",
    str(Path.home() / "work/audio_engineering_repo_skeleton_v1")
)).expanduser().resolve()

MAINBASE_HANDOFF = MAINBASE_ROOT / "artifacts/manifests/week12_mainbase_audio_timing_handoff_index.json"

OUT_RUNTIME_INDEX = CLOUD_ROOT / "artifacts/manifests/week12_cloud_mainbase_audio_timing_runtime_index.json"
OUT_DASHBOARD_STUB = CLOUD_ROOT / "observability/grafana/dashboards/week12_audio_timing_alignment_runtime_stub.json"


def run_git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args],
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing required file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def rel_to_cloud(path: Path) -> str:
    try:
        return str(path.relative_to(CLOUD_ROOT))
    except ValueError:
        return str(path)


def require_pass(name: str, obj: Dict[str, Any]) -> None:
    if obj.get("status") != "PASS":
        raise RuntimeError(f"{name} status is not PASS: {obj.get('status')}")


def build_dashboard_stub(runtime_index: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": "Week12 Audio Timing Runtime Semantics",
        "tags": ["week12", "soundlayer", "timing", "runtime-semantics"],
        "timezone": "browser",
        "schemaVersion": 39,
        "version": 1,
        "refresh": "30s",
        "annotations": {"list": []},
        "panels": [
            {
                "id": 1,
                "type": "stat",
                "title": "Timing Binding PASS",
                "description": "Mainbase candidate-to-event timing binding result consumed by Cloud.",
                "gridPos": {"x": 0, "y": 0, "w": 6, "h": 4},
                "fieldConfig": {"defaults": {}, "overrides": []},
                "options": {"reduceOptions": {"calcs": ["lastNotNull"]}},
                "targets": [],
            },
            {
                "id": 2,
                "type": "stat",
                "title": "Temporal Alignment PASS",
                "description": "RMS/onset-proxy timing compatibility after coordinate-frame repair.",
                "gridPos": {"x": 6, "y": 0, "w": 6, "h": 4},
                "fieldConfig": {"defaults": {}, "overrides": []},
                "options": {"reduceOptions": {"calcs": ["lastNotNull"]}},
                "targets": [],
            },
            {
                "id": 3,
                "type": "table",
                "title": "Asset Time Modes",
                "description": "full_clip assets use scene timeline; event_local assets require expectedStartSec placement.",
                "gridPos": {"x": 0, "y": 4, "w": 12, "h": 6},
                "fieldConfig": {"defaults": {}, "overrides": []},
                "targets": [],
            },
            {
                "id": 4,
                "type": "table",
                "title": "Runtime Placement Requirements",
                "description": "Cloud/runtime/mixer must preserve placement offsets for event-local foley assets.",
                "gridPos": {"x": 12, "y": 0, "w": 12, "h": 10},
                "fieldConfig": {"defaults": {}, "overrides": []},
                "targets": [],
            },
        ],
        "week12RuntimeSummary": {
            "status": runtime_index["status"],
            "sourceMainbaseCommit": runtime_index["source"]["mainbaseCommit"],
            "candidateCount": runtime_index["metrics"]["candidateCount"],
            "timingBoundCount": runtime_index["metrics"]["timingBoundCount"],
            "alignmentPassCount": runtime_index["metrics"]["alignmentPassCount"],
            "assetTimeModeCounts": runtime_index["metrics"]["assetTimeModeCounts"],
            "runtimeWarnings": runtime_index["runtimeWarnings"],
        },
    }


def main() -> int:
    handoff = load_json(MAINBASE_HANDOFF)
    require_pass("mainbase handoff", handoff)

    mainbase_commit = run_git(MAINBASE_ROOT, "rev-parse", "--short", "HEAD")
    mainbase_origin = run_git(MAINBASE_ROOT, "rev-parse", "--short", "origin/main")
    cloud_commit_before = run_git(CLOUD_ROOT, "rev-parse", "--short", "HEAD")

    if mainbase_commit != mainbase_origin:
        raise RuntimeError(f"Mainbase local HEAD differs from origin/main: {mainbase_commit} != {mainbase_origin}")

    event_local_offsets: List[Dict[str, Any]] = handoff.get("eventLocalPlacementOffsets", [])
    asset_modes = handoff.get("assetTimeModeCounts", {})
    layer_decisions = handoff.get("layerDecisionCounts", {})

    required_runtime_semantics = [
        "full_clip assets are interpreted directly on the scene/global timeline",
        "event_local assets must be placed at expectedStartSec before runtime visualization or mixing",
        "event_local peakLocalSec must be converted to peakGlobalSec through expectedStartSec offset",
        "PASS only covers timing binding and RMS/onset-proxy timing compatibility",
        "PASS does not imply semantic quality, human audition, final mix readiness, or production readiness",
    ]

    blockers: List[str] = []
    warnings: List[str] = []

    if handoff.get("timingBoundCount") != handoff.get("candidateCount"):
        blockers.append("TIMING_BOUND_COUNT_MISMATCH")
    if handoff.get("alignmentPassCount") != handoff.get("candidateCount"):
        blockers.append("ALIGNMENT_PASS_COUNT_MISMATCH")
    if asset_modes.get("event_local", 0) != len(event_local_offsets):
        blockers.append("EVENT_LOCAL_OFFSET_COUNT_MISMATCH")
    if asset_modes.get("event_local", 0) > 0:
        warnings.append("EVENT_LOCAL_ASSETS_REQUIRE_EXPECTED_START_SEC_PLACEMENT")
    if not event_local_offsets:
        warnings.append("NO_EVENT_LOCAL_OFFSETS_FOUND")

    status = "PASS" if not blockers else "FAIL"

    runtime_index = {
        "status": status,
        "scope": "cloud_consumes_week12_mainbase_audio_timing_alignment_handoff",
        "source": {
            "mainbasePath": str(MAINBASE_ROOT),
            "mainbaseCommit": mainbase_commit,
            "mainbaseOriginMain": mainbase_origin,
            "mainbaseHandoff": str(MAINBASE_HANDOFF),
            "cloudCommitBefore": cloud_commit_before,
        },
        "metrics": {
            "candidateCount": handoff.get("candidateCount"),
            "audioReadableCount": handoff.get("audioReadableCount"),
            "timingBoundCount": handoff.get("timingBoundCount"),
            "timingBindingMethodCounts": handoff.get("timingBindingMethodCounts"),
            "alignmentPassCount": handoff.get("alignmentPassCount"),
            "alignmentFailCount": handoff.get("alignmentFailCount"),
            "assetTimeModeCounts": asset_modes,
            "layerCounts": handoff.get("layerCounts"),
            "layerDecisionCounts": layer_decisions,
        },
        "runtimeSemantics": {
            "fullClipMode": {
                "assetTimeMode": "full_clip",
                "placement": "use scene/global timeline directly",
                "expectedConsumerBehavior": "visualize or mix from t=0 unless the blueprint later defines a global offset",
            },
            "eventLocalMode": {
                "assetTimeMode": "event_local",
                "placement": "place asset at expectedStartSec",
                "expectedConsumerBehavior": "convert local timestamps to global timestamps by adding expectedStartSec",
                "requiredForMixer": True,
                "requiredForDashboard": True,
            },
            "requiredRuntimeSemantics": required_runtime_semantics,
        },
        "eventLocalPlacementOffsets": event_local_offsets,
        "runtimeWarnings": warnings,
        "blockers": blockers,
        "outputs": {
            "runtimeIndex": rel_to_cloud(OUT_RUNTIME_INDEX),
            "dashboardStub": rel_to_cloud(OUT_DASHBOARD_STUB),
        },
        "boundaryStatement": (
            "Cloud consumed Mainbase audio timing evidence and converted it into runtime semantics. "
            "This is not a real production deployment, not a final mixer, not human audition, and not semantic quality validation."
        ),
    }

    if status != "PASS":
        raise RuntimeError(json.dumps(runtime_index, ensure_ascii=False, indent=2))

    OUT_RUNTIME_INDEX.parent.mkdir(parents=True, exist_ok=True)
    OUT_DASHBOARD_STUB.parent.mkdir(parents=True, exist_ok=True)

    OUT_RUNTIME_INDEX.write_text(json.dumps(runtime_index, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_DASHBOARD_STUB.write_text(
        json.dumps(build_dashboard_stub(runtime_index), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(runtime_index, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())