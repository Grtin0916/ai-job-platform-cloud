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
    str(Path.home() / "work/grt_work/audio_engineering_repo_skeleton_v1")
)).expanduser().resolve()
JAVA_ROOT = Path(os.environ.get(
    "JAVA_PATH",
    str(Path.home() / "work/grt_work/media-task-platform-java")
)).expanduser().resolve()

MAINBASE_BINDING = MAINBASE_ROOT / "artifacts/manifests/week12_audio_candidate_timing_binding_report_v2.json"
MAINBASE_TEMPORAL = MAINBASE_ROOT / "artifacts/manifests/week12_temporal_alignment_probe_report_v1.json"
MAINBASE_HANDOFF = MAINBASE_ROOT / "artifacts/manifests/week12_mainbase_audio_timing_handoff_index.json"

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


def git_state(repo: Path) -> Dict[str, Any]:
    porcelain = run_git(repo, "status", "--porcelain=v1")
    return {
        "path": str(repo),
        "head": run_git(repo, "rev-parse", "--short", "HEAD"),
        "originMain": run_git(repo, "rev-parse", "--short", "origin/main"),
        "cleanBeforeManifestWrite": porcelain == "",
        "porcelainBeforeManifestWrite": porcelain.splitlines(),
        "latestCommit": run_git(repo, "log", "-1", "--oneline"),
    }


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


def add_blocker(blockers: List[str], condition: bool, msg: str) -> None:
    if condition:
        blockers.append(msg)


def main() -> int:
    blockers: List[str] = []
    warnings: List[str] = []

    repo_state = {
        "mainbase": git_state(MAINBASE_ROOT),
        "cloud": git_state(CLOUD_ROOT),
        "java": git_state(JAVA_ROOT),
    }

    for name, state in repo_state.items():
        add_blocker(blockers, state["head"] != state["originMain"], f"{name.upper()}_HEAD_DIFFERS_FROM_ORIGIN_MAIN")
        add_blocker(blockers, not state["cleanBeforeManifestWrite"], f"{name.upper()}_NOT_CLEAN_BEFORE_MANIFEST_WRITE:{state['porcelainBeforeManifestWrite']}")

    mainbase_binding = load_json(MAINBASE_BINDING)
    mainbase_temporal = load_json(MAINBASE_TEMPORAL)
    mainbase_handoff = load_json(MAINBASE_HANDOFF)
    cloud_runtime = load_json(CLOUD_RUNTIME)
    cloud_dashboard = load_json(CLOUD_DASHBOARD)
    java_report = load_json(JAVA_REPORT)
    java_resource = load_json(JAVA_RESOURCE)
    java_controller_text = read_text(JAVA_CONTROLLER)
    java_it_text = read_text(JAVA_IT)

    artifact_commits = {
        "mainbaseBindingCommit": last_touch_commit(MAINBASE_ROOT, MAINBASE_BINDING),
        "mainbaseTemporalCommit": last_touch_commit(MAINBASE_ROOT, MAINBASE_TEMPORAL),
        "mainbaseHandoffCommit": last_touch_commit(MAINBASE_ROOT, MAINBASE_HANDOFF),
        "cloudRuntimeCommit": last_touch_commit(CLOUD_ROOT, CLOUD_RUNTIME),
        "cloudDashboardCommit": last_touch_commit(CLOUD_ROOT, CLOUD_DASHBOARD),
        "javaContractReportCommit": last_touch_commit(JAVA_ROOT, JAVA_REPORT),
        "javaResourceCommit": last_touch_commit(JAVA_ROOT, JAVA_RESOURCE),
        "javaControllerCommit": last_touch_commit(JAVA_ROOT, JAVA_CONTROLLER),
        "javaITCommit": last_touch_commit(JAVA_ROOT, JAVA_IT),
    }

    add_blocker(blockers, repo_state["mainbase"]["head"] != "28e79ff", "MAINBASE_HEAD_NOT_EXPECTED_28e79ff")
    add_blocker(blockers, repo_state["java"]["head"] != "88d8d28", "JAVA_HEAD_NOT_EXPECTED_88d8d28")

    add_blocker(blockers, mainbase_binding.get("status") != "PASS", "MAINBASE_BINDING_NOT_PASS")
    add_blocker(blockers, mainbase_temporal.get("status") != "PASS", "MAINBASE_TEMPORAL_NOT_PASS")
    add_blocker(blockers, mainbase_handoff.get("status") != "PASS", "MAINBASE_HANDOFF_NOT_PASS")
    add_blocker(blockers, cloud_runtime.get("status") != "PASS", "CLOUD_RUNTIME_NOT_PASS")

    add_blocker(blockers, mainbase_binding.get("timingBoundCount") != 10, "MAINBASE_TIMING_BOUND_NOT_10")
    add_blocker(blockers, mainbase_temporal.get("alignmentPassCount") != 10, "MAINBASE_ALIGNMENT_PASS_NOT_10")

    metrics = cloud_runtime.get("metrics", {})
    asset_modes = metrics.get("assetTimeModeCounts", {})
    event_offsets = cloud_runtime.get("eventLocalPlacementOffsets", [])

    add_blocker(blockers, cloud_runtime.get("source", {}).get("mainbaseCommit") != "28e79ff", "CLOUD_RUNTIME_MAINBASE_COMMIT_NOT_28e79ff")
    add_blocker(blockers, metrics.get("candidateCount") != 10, "CLOUD_CANDIDATE_COUNT_NOT_10")
    add_blocker(blockers, metrics.get("timingBoundCount") != 10, "CLOUD_TIMING_BOUND_NOT_10")
    add_blocker(blockers, metrics.get("alignmentPassCount") != 10, "CLOUD_ALIGNMENT_PASS_NOT_10")
    add_blocker(blockers, metrics.get("alignmentFailCount") != 0, "CLOUD_ALIGNMENT_FAIL_NOT_0")
    add_blocker(blockers, asset_modes.get("full_clip") != 5, "CLOUD_FULL_CLIP_NOT_5")
    add_blocker(blockers, asset_modes.get("event_local") != 5, "CLOUD_EVENT_LOCAL_NOT_5")
    add_blocker(blockers, len(event_offsets) != 5, "CLOUD_EVENT_LOCAL_OFFSET_COUNT_NOT_5")

    add_blocker(blockers, java_report.get("source", {}).get("cloudCommit") != "a1f7159", "JAVA_REPORT_CLOUD_COMMIT_NOT_a1f7159")
    add_blocker(blockers, java_resource.get("source", {}).get("mainbaseCommit") != "28e79ff", "JAVA_RESOURCE_MAINBASE_COMMIT_NOT_28e79ff")
    add_blocker(blockers, java_resource.get("metrics", {}).get("assetTimeModeCounts", {}).get("event_local") != 5, "JAVA_RESOURCE_EVENT_LOCAL_NOT_5")

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
        add_blocker(blockers, token not in java_controller_text, f"JAVA_CONTROLLER_MISSING:{token}")
    for token in required_it_tokens:
        add_blocker(blockers, token not in java_it_text, f"JAVA_IT_MISSING:{token}")

    dashboard_panels = cloud_dashboard.get("panels", [])
    add_blocker(blockers, len(dashboard_panels) < 4, f"CLOUD_DASHBOARD_PANEL_COUNT_TOO_LOW:{len(dashboard_panels)}")

    warnings.extend(mainbase_handoff.get("warnings", []))
    warnings.extend(cloud_runtime.get("runtimeWarnings", []))
    warnings = sorted(set(warnings))

    closure = {
        "status": "PASS" if not blockers else "FAIL",
        "scope": "week12_trirepo_audio_timing_runtime_contract_closure_v3_finalized",
        "repoStateBeforeManifestWrite": repo_state,
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
            "candidateCount": metrics.get("candidateCount"),
            "timingBoundCount": metrics.get("timingBoundCount"),
            "alignmentPassCount": metrics.get("alignmentPassCount"),
            "alignmentFailCount": metrics.get("alignmentFailCount"),
            "assetTimeModeCounts": asset_modes,
            "eventLocalPlacementOffsetCount": len(event_offsets),
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
        "finalizerNote": (
            "v3 checks repo cleanliness before writing the closure manifest and does not treat the manifest/log generated by this run as a blocker."
        ),
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(closure, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(closure, ensure_ascii=False, indent=2))

    return 0 if closure["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())