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
JAVA_ROOT = Path(os.environ.get(
    "JAVA_PATH",
    str(Path.home() / "work/media-task-platform-java")
)).expanduser().resolve()

MAINBASE_HANDOFF = MAINBASE_ROOT / "artifacts/manifests/week12_mainbase_audio_timing_handoff_index.json"
MAINBASE_BINDING = MAINBASE_ROOT / "artifacts/manifests/week12_audio_candidate_timing_binding_report_v2.json"
MAINBASE_TEMPORAL = MAINBASE_ROOT / "artifacts/manifests/week12_temporal_alignment_probe_report_v1.json"

CLOUD_RUNTIME = CLOUD_ROOT / "artifacts/manifests/week12_cloud_mainbase_audio_timing_runtime_index.json"
CLOUD_DASHBOARD = CLOUD_ROOT / "observability/grafana/dashboards/week12_audio_timing_alignment_runtime_stub.json"

JAVA_REPORT = JAVA_ROOT / "artifacts/manifests/week12_java_audio_timing_runtime_contract_report.json"
JAVA_RESOURCE = JAVA_ROOT / "src/main/resources/week12/week12_cloud_mainbase_audio_timing_runtime_index.json"
JAVA_CONTROLLER = JAVA_ROOT / "src/main/java/com/ryan/media/week12/Week12AudioTimingRuntimeContractController.java"
JAVA_IT = JAVA_ROOT / "src/test/java/com/ryan/media/week12/Week12AudioTimingRuntimeContractIT.java"

OUT = CLOUD_ROOT / "artifacts/manifests/week12_trirepo_audio_timing_closure_manifest.json"


def run_git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args],
        text=True,
        stderr=subprocess.STDOUT,
    ).strip()


def git_clean(repo: Path) -> bool:
    return run_git(repo, "status", "--porcelain=v1") == ""


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing required file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def read_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"missing required file: {path}")
    return path.read_text(encoding="utf-8", errors="replace")


def assert_eq(name: str, actual: Any, expected: Any, blockers: List[str]) -> None:
    if actual != expected:
        blockers.append(f"{name}: expected {expected!r}, got {actual!r}")


def main() -> int:
    blockers: List[str] = []
    warnings: List[str] = []

    repos = {
        "mainbase": MAINBASE_ROOT,
        "cloud": CLOUD_ROOT,
        "java": JAVA_ROOT,
    }

    repo_state = {}
    for name, repo in repos.items():
        repo_state[name] = {
            "path": str(repo),
            "head": run_git(repo, "rev-parse", "--short", "HEAD"),
            "originMain": run_git(repo, "rev-parse", "--short", "origin/main"),
            "clean": git_clean(repo),
            "latestCommit": run_git(repo, "log", "-1", "--oneline"),
        }
        if repo_state[name]["head"] != repo_state[name]["originMain"]:
            blockers.append(f"{name.upper()}_HEAD_DIFFERS_FROM_ORIGIN_MAIN")
        if not repo_state[name]["clean"]:
            blockers.append(f"{name.upper()}_WORKTREE_NOT_CLEAN")

    mainbase_handoff = load_json(MAINBASE_HANDOFF)
    mainbase_binding = load_json(MAINBASE_BINDING)
    mainbase_temporal = load_json(MAINBASE_TEMPORAL)
    cloud_runtime = load_json(CLOUD_RUNTIME)
    cloud_dashboard = load_json(CLOUD_DASHBOARD)
    java_report = load_json(JAVA_REPORT)
    java_resource = load_json(JAVA_RESOURCE)
    java_controller_text = read_text(JAVA_CONTROLLER)
    java_it_text = read_text(JAVA_IT)

    assert_eq("mainbase.head", repo_state["mainbase"]["head"], "28e79ff", blockers)
    assert_eq("cloud.head", repo_state["cloud"]["head"], "a1f7159", blockers)
    assert_eq("java.head", repo_state["java"]["head"], "88d8d28", blockers)

    for name, obj in [
        ("mainbase_handoff", mainbase_handoff),
        ("mainbase_binding", mainbase_binding),
        ("mainbase_temporal", mainbase_temporal),
        ("cloud_runtime", cloud_runtime),
    ]:
        assert_eq(f"{name}.status", obj.get("status"), "PASS", blockers)

    assert_eq("mainbase.binding.timingBoundCount", mainbase_binding.get("timingBoundCount"), 10, blockers)
    assert_eq("mainbase.temporal.alignmentPassCount", mainbase_temporal.get("alignmentPassCount"), 10, blockers)
    assert_eq("cloud.runtime.source.mainbaseCommit", cloud_runtime.get("source", {}).get("mainbaseCommit"), "28e79ff", blockers)
    assert_eq("cloud.runtime.metrics.candidateCount", cloud_runtime.get("metrics", {}).get("candidateCount"), 10, blockers)
    assert_eq("cloud.runtime.metrics.alignmentPassCount", cloud_runtime.get("metrics", {}).get("alignmentPassCount"), 10, blockers)
    assert_eq("cloud.runtime.metrics.assetTimeModeCounts.full_clip", cloud_runtime.get("metrics", {}).get("assetTimeModeCounts", {}).get("full_clip"), 5, blockers)
    assert_eq("cloud.runtime.metrics.assetTimeModeCounts.event_local", cloud_runtime.get("metrics", {}).get("assetTimeModeCounts", {}).get("event_local"), 5, blockers)

    event_offsets = cloud_runtime.get("eventLocalPlacementOffsets", [])
    assert_eq("cloud.runtime.eventLocalPlacementOffsetCount", len(event_offsets), 5, blockers)

    assert_eq("java.report.source.cloudCommit", java_report.get("source", {}).get("cloudCommit"), "a1f7159", blockers)
    assert_eq("java.resource.source.mainbaseCommit", java_resource.get("source", {}).get("mainbaseCommit"), "28e79ff", blockers)
    assert_eq("java.resource.metrics.assetTimeModeCounts.event_local", java_resource.get("metrics", {}).get("assetTimeModeCounts", {}).get("event_local"), 5, blockers)

    required_controller_tokens = [
        "/api/week12/audio-timing-runtime",
        "/api/week12/audio-timing-runtime/event-local-offsets",
        "/api/week12/audio-timing-runtime/placement-required",
    ]
    required_it_tokens = [
        "assetTimeModeCounts",
        "placementRequired",
        "expectedStartSec",
        "peakGlobalSec",
        "event_local",
    ]

    for token in required_controller_tokens:
        if token not in java_controller_text:
            blockers.append(f"JAVA_CONTROLLER_MISSING_TOKEN:{token}")
    for token in required_it_tokens:
        if token not in java_it_text:
            blockers.append(f"JAVA_IT_MISSING_TOKEN:{token}")

    dashboard_panels = cloud_dashboard.get("panels", [])
    if len(dashboard_panels) < 4:
        blockers.append(f"CLOUD_DASHBOARD_PANEL_COUNT_TOO_LOW:{len(dashboard_panels)}")

    if cloud_runtime.get("runtimeWarnings"):
        warnings.extend(cloud_runtime.get("runtimeWarnings", []))
    if mainbase_handoff.get("warnings"):
        warnings.extend(mainbase_handoff.get("warnings", []))

    closure = {
        "status": "PASS" if not blockers else "FAIL",
        "scope": "week12_trirepo_audio_timing_runtime_contract_closure",
        "repoState": repo_state,
        "businessChain": [
            {
                "repo": "mainbase",
                "commit": repo_state["mainbase"]["head"],
                "behavior": "binds 10 audio candidates to event timing windows and repairs temporal coordinate frame",
                "evidence": [
                    str(MAINBASE_BINDING),
                    str(MAINBASE_TEMPORAL),
                    str(MAINBASE_HANDOFF),
                ],
            },
            {
                "repo": "cloud",
                "commit": repo_state["cloud"]["head"],
                "behavior": "consumes Mainbase timing evidence and converts it into runtime placement semantics",
                "evidence": [
                    str(CLOUD_RUNTIME),
                    str(CLOUD_DASHBOARD),
                ],
            },
            {
                "repo": "java",
                "commit": repo_state["java"]["head"],
                "behavior": "exposes Cloud-consumed runtime semantics through HTTP contract and RANDOM_PORT IT",
                "evidence": [
                    str(JAVA_REPORT),
                    str(JAVA_RESOURCE),
                    str(JAVA_CONTROLLER),
                    str(JAVA_IT),
                ],
            },
        ],
        "closureMetrics": {
            "candidateCount": cloud_runtime.get("metrics", {}).get("candidateCount"),
            "timingBoundCount": cloud_runtime.get("metrics", {}).get("timingBoundCount"),
            "alignmentPassCount": cloud_runtime.get("metrics", {}).get("alignmentPassCount"),
            "alignmentFailCount": cloud_runtime.get("metrics", {}).get("alignmentFailCount"),
            "assetTimeModeCounts": cloud_runtime.get("metrics", {}).get("assetTimeModeCounts"),
            "eventLocalPlacementOffsetCount": len(event_offsets),
            "dashboardPanelCount": len(dashboard_panels),
        },
        "contractEndpoints": required_controller_tokens,
        "runtimeWarnings": sorted(set(warnings)),
        "blockers": blockers,
        "nextRisk": (
            "The next concrete risk is mixer/runtime placement: event_local foley assets must be placed at expectedStartSec, "
            "otherwise timing compatibility will regress even though the API contract is now correct."
        ),
        "boundaryStatement": (
            "This closure proves the Week12 timing/alignment runtime contract across Mainbase, Cloud, and Java. "
            "It does not prove semantic audio quality, human audition, final mix readiness, production SLO, or real cloud deployment."
        ),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(closure, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(closure, ensure_ascii=False, indent=2))

    return 0 if closure["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())