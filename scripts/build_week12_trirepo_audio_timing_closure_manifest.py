#!/usr/bin/env python3
from __future__ import annotations

import fnmatch
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
CLOUD_CLOSURE_SCRIPT = CLOUD_ROOT / "scripts/build_week12_trirepo_audio_timing_closure_manifest.py"

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


def status_porcelain(repo: Path) -> List[str]:
    out = run_git(repo, "status", "--porcelain=v1")
    return [line for line in out.splitlines() if line.strip()]


def status_path(line: str) -> str:
    """Extract path from git status --porcelain=v1 line.

    Handles common forms:
      - ' M path'
      - 'M  path'
      - 'M path'
      - '?? path'
      - 'R  old -> new'
    """
    raw = line.rstrip("
")
    if not raw:
        return ""

    # Most porcelain v1 lines have a status token followed by whitespace and a path.
    parts = raw.split(maxsplit=1)
    if len(parts) == 1:
        candidate = parts[0]
    else:
        candidate = parts[1]

    # For rename/copy entries, use the destination path.
    if " -> " in candidate:
        candidate = candidate.split(" -> ", 1)[1]

    return candidate.strip()


def unexpected_dirty_entries(repo: Path, allowed_patterns: List[str]) -> List[str]:
    bad = []
    for line in status_porcelain(repo):
        p = status_path(line)
        if not any(fnmatch.fnmatch(p, pat) for pat in allowed_patterns):
            bad.append(line)
    return bad


def last_touch_commit(repo: Path, path: Path) -> str:
    rel = str(path.relative_to(repo))
    return run_git(repo, "log", "-1", "--format=%h", "--", rel)


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


def repo_state(repo: Path, allowed_dirty_patterns: List[str] | None = None) -> Dict[str, Any]:
    allowed_dirty_patterns = allowed_dirty_patterns or []
    dirty = status_porcelain(repo)
    unexpected = unexpected_dirty_entries(repo, allowed_dirty_patterns)
    return {
        "path": str(repo),
        "head": run_git(repo, "rev-parse", "--short", "HEAD"),
        "originMain": run_git(repo, "rev-parse", "--short", "origin/main"),
        "strictClean": len(dirty) == 0,
        "unexpectedDirtyClean": len(unexpected) == 0,
        "dirtyEntries": dirty,
        "unexpectedDirtyEntries": unexpected,
        "latestCommit": run_git(repo, "log", "-1", "--oneline"),
    }


def main() -> int:
    blockers: List[str] = []
    warnings: List[str] = []

    cloud_allowed_dirty = [
        "scripts/build_week12_trirepo_audio_timing_closure_manifest.py",
        "artifacts/manifests/week12_trirepo_audio_timing_closure_manifest.json",
        "artifacts/logs/week12_trirepo_audio_timing_closure_manifest_*.log",
    ]

    repos = {
        "mainbase": repo_state(MAINBASE_ROOT),
        "cloud": repo_state(CLOUD_ROOT, cloud_allowed_dirty),
        "java": repo_state(JAVA_ROOT),
    }

    for name, state in repos.items():
        if state["head"] != state["originMain"]:
            blockers.append(f"{name.upper()}_HEAD_DIFFERS_FROM_ORIGIN_MAIN")
        if name in {"mainbase", "java"} and not state["strictClean"]:
            blockers.append(f"{name.upper()}_WORKTREE_NOT_CLEAN")
        if name == "cloud" and not state["unexpectedDirtyClean"]:
            blockers.append(f"CLOUD_UNEXPECTED_WORKTREE_DIRTY:{state['unexpectedDirtyEntries']}")

    mainbase_handoff = load_json(MAINBASE_HANDOFF)
    mainbase_binding = load_json(MAINBASE_BINDING)
    mainbase_temporal = load_json(MAINBASE_TEMPORAL)
    cloud_runtime = load_json(CLOUD_RUNTIME)
    cloud_dashboard = load_json(CLOUD_DASHBOARD)
    java_report = load_json(JAVA_REPORT)
    java_resource = load_json(JAVA_RESOURCE)
    java_controller_text = read_text(JAVA_CONTROLLER)
    java_it_text = read_text(JAVA_IT)

    artifact_commits = {
        "mainbaseHandoffCommit": last_touch_commit(MAINBASE_ROOT, MAINBASE_HANDOFF),
        "mainbaseBindingCommit": last_touch_commit(MAINBASE_ROOT, MAINBASE_BINDING),
        "mainbaseTemporalCommit": last_touch_commit(MAINBASE_ROOT, MAINBASE_TEMPORAL),
        "cloudRuntimeCommit": last_touch_commit(CLOUD_ROOT, CLOUD_RUNTIME),
        "cloudDashboardCommit": last_touch_commit(CLOUD_ROOT, CLOUD_DASHBOARD),
        "javaContractReportCommit": last_touch_commit(JAVA_ROOT, JAVA_REPORT),
        "javaResourceCommit": last_touch_commit(JAVA_ROOT, JAVA_RESOURCE),
        "javaControllerCommit": last_touch_commit(JAVA_ROOT, JAVA_CONTROLLER),
        "javaITCommit": last_touch_commit(JAVA_ROOT, JAVA_IT),
    }

    assert_eq("mainbase.head", repos["mainbase"]["head"], "28e79ff", blockers)
    assert_eq("java.head", repos["java"]["head"], "88d8d28", blockers)
    assert_eq("mainbase.handoff.status", mainbase_handoff.get("status"), "PASS", blockers)
    assert_eq("mainbase.binding.status", mainbase_binding.get("status"), "PASS", blockers)
    assert_eq("mainbase.temporal.status", mainbase_temporal.get("status"), "PASS", blockers)
    assert_eq("cloud.runtime.status", cloud_runtime.get("status"), "PASS", blockers)

    assert_eq("mainbase.binding.timingBoundCount", mainbase_binding.get("timingBoundCount"), 10, blockers)
    assert_eq("mainbase.temporal.alignmentPassCount", mainbase_temporal.get("alignmentPassCount"), 10, blockers)
    assert_eq("cloud.runtime.source.mainbaseCommit", cloud_runtime.get("source", {}).get("mainbaseCommit"), "28e79ff", blockers)
    assert_eq("cloud.runtime.metrics.candidateCount", cloud_runtime.get("metrics", {}).get("candidateCount"), 10, blockers)
    assert_eq("cloud.runtime.metrics.timingBoundCount", cloud_runtime.get("metrics", {}).get("timingBoundCount"), 10, blockers)
    assert_eq("cloud.runtime.metrics.alignmentPassCount", cloud_runtime.get("metrics", {}).get("alignmentPassCount"), 10, blockers)
    assert_eq("cloud.runtime.metrics.assetTimeModeCounts.full_clip", cloud_runtime.get("metrics", {}).get("assetTimeModeCounts", {}).get("full_clip"), 5, blockers)
    assert_eq("cloud.runtime.metrics.assetTimeModeCounts.event_local", cloud_runtime.get("metrics", {}).get("assetTimeModeCounts", {}).get("event_local"), 5, blockers)
    assert_eq("cloud.runtime.eventLocalPlacementOffsetCount", len(cloud_runtime.get("eventLocalPlacementOffsets", [])), 5, blockers)

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

    warnings.extend(cloud_runtime.get("runtimeWarnings", []))
    warnings.extend(mainbase_handoff.get("warnings", []))
    warnings = sorted(set(warnings))

    closure = {
        "status": "PASS" if not blockers else "FAIL",
        "scope": "week12_trirepo_audio_timing_runtime_contract_closure_v2",
        "repoState": repos,
        "artifactProducerCommits": artifact_commits,
        "businessChain": [
            {
                "repo": "mainbase",
                "commit": "28e79ff",
                "behavior": "binds 10 audio candidates to event timing windows and repairs temporal coordinate frame",
                "evidence": [
                    str(MAINBASE_BINDING),
                    str(MAINBASE_TEMPORAL),
                    str(MAINBASE_HANDOFF),
                ],
            },
            {
                "repo": "cloud",
                "commit": artifact_commits["cloudRuntimeCommit"],
                "behavior": "consumes Mainbase timing evidence and converts it into runtime placement semantics",
                "evidence": [
                    str(CLOUD_RUNTIME),
                    str(CLOUD_DASHBOARD),
                ],
            },
            {
                "repo": "java",
                "commit": "88d8d28",
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
            "eventLocalPlacementOffsetCount": len(cloud_runtime.get("eventLocalPlacementOffsets", [])),
            "dashboardPanelCount": len(dashboard_panels),
        },
        "contractEndpoints": required_controller_tokens,
        "runtimeWarnings": warnings,
        "blockers": blockers,
        "nextRisk": (
            "The next concrete risk is mixer/runtime placement: event_local foley assets must be placed at expectedStartSec, "
            "otherwise timing compatibility will regress even though the API contract is now correct."
        ),
        "boundaryStatement": (
            "This closure proves the Week12 timing/alignment runtime contract across Mainbase, Cloud, and Java. "
            "It does not prove semantic audio quality, human audition, final mix readiness, production SLO, or real cloud deployment."
        ),
        "repairNote": (
            "v3 fixes the self-referential clean-state bug and robustly parses porcelain dirty paths in the first closure manifest: Cloud closure files are allowed "
            "while generating the closure, but unexpected dirty files still block the manifest."
        ),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(closure, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(closure, ensure_ascii=False, indent=2))

    return 0 if closure["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())