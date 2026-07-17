#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CLOUD_ROOT = Path.cwd()
MAINBASE_ROOT = Path.home() / "work/grt_work/audio_engineering_repo_skeleton_v1"
JAVA_ROOT = Path.home() / "work/grt_work/media-task-platform-java"

MAINBASE_PLACEMENT_TABLE = MAINBASE_ROOT / "artifacts/evals/week13_mix_global_placement_table.csv"
MAINBASE_DRYRUN_MANIFEST = MAINBASE_ROOT / "artifacts/audio_mix/week13_mix_preview_manifest.json"
JAVA_REGISTRY_REPORT = JAVA_ROOT / "artifacts/manifests/week13_java_audio_artifact_registry_contract_report.json"

OUT_INDEX = CLOUD_ROOT / "loadtest/reports/week13_audio_artifact_storage_index.json"
OUT_RUNBOOK = CLOUD_ROOT / "docs/runbooks/audio-artifact-storage.md"
OUT_DASHBOARD = CLOUD_ROOT / "observability/grafana/dashboards/week13_mix_placement_dashboard.json"
OUT_MANIFEST = CLOUD_ROOT / "artifacts/manifests/week13_cloud_audio_artifact_storage_manifest.json"
OUT_LOG = CLOUD_ROOT / "artifacts/logs" / f"week13_audio_artifact_storage_index_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"


def git_head(path: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=path,
            text=True,
        ).strip()
    except Exception:
        return "UNKNOWN"


def load_json(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"missing required json: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"missing required csv: {path}")
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def rel_or_abs(path_text: str | None) -> str:
    if not path_text:
        return ""
    p = Path(path_text)
    return str(p)


def main() -> int:
    placement_rows = read_csv(MAINBASE_PLACEMENT_TABLE)
    mainbase_dryrun = load_json(MAINBASE_DRYRUN_MANIFEST)
    java_report = load_json(JAVA_REGISTRY_REPORT)

    blockers: list[str] = []

    if mainbase_dryrun.get("status") != "PASS":
        blockers.append("MAINBASE_WEEK13_DRYRUN_NOT_PASS")
    if java_report.get("status") != "PASS":
        blockers.append("JAVA_WEEK13_REGISTRY_REPORT_NOT_PASS")
    if len(placement_rows) != 10:
        blockers.append(f"EXPECTED_10_PLACEMENT_ROWS_GOT_{len(placement_rows)}")

    full_clip_count = sum(1 for r in placement_rows if r.get("assetTimeMode") == "full_clip")
    event_local_count = sum(1 for r in placement_rows if r.get("assetTimeMode") == "event_local")
    placement_required_count = sum(1 for r in placement_rows if r.get("placementRequired") == "True")

    if full_clip_count != 5:
        blockers.append(f"EXPECTED_5_FULL_CLIP_GOT_{full_clip_count}")
    if event_local_count != 5:
        blockers.append(f"EXPECTED_5_EVENT_LOCAL_GOT_{event_local_count}")
    if placement_required_count != 5:
        blockers.append(f"EXPECTED_5_PLACEMENT_REQUIRED_GOT_{placement_required_count}")

    local_object_root = "/var/local/audio-artifacts/week13"
    pod_mount_root = "/mnt/audio-artifacts/week13"
    host_project_root = str(MAINBASE_ROOT)

    artifacts = []
    total_logical_duration_sec = 0.0

    for r in placement_rows:
        duration = float(r.get("actualDurationSec") or 0.0)
        total_logical_duration_sec += duration

        audio_uri = rel_or_abs(r.get("audioUri"))
        candidate_id = r.get("candidateId")
        case_id = r.get("caseId")
        asset_time_mode = r.get("assetTimeMode")
        layer = r.get("layer")

        object_key = f"candidates/{case_id}/{candidate_id}.wav"
        pod_path = f"{pod_mount_root}/{object_key}"
        local_path = f"{local_object_root}/{object_key}"

        artifacts.append({
            "candidateId": candidate_id,
            "caseId": case_id,
            "sceneId": r.get("sceneId"),
            "eventId": r.get("eventId"),
            "layer": layer,
            "label": r.get("label"),
            "assetTimeMode": asset_time_mode,
            "placementRequired": r.get("placementRequired") == "True",
            "sourceAudioUri": audio_uri,
            "sourceType": r.get("sourceType"),
            "expectedStartSec": float(r.get("expectedStartSec") or 0.0),
            "globalStartSec": float(r.get("globalStartSec") or 0.0),
            "globalEndSec": float(r.get("globalEndSec") or 0.0),
            "placementOffsetSec": float(r.get("placementOffsetSec") or 0.0),
            "logicalDurationSec": duration,
            "storage": {
                "localObjectRoot": local_object_root,
                "objectKey": object_key,
                "localObjectPath": local_path,
                "podMountRoot": pod_mount_root,
                "podPath": pod_path,
                "kindVolumeMode": "hostPath_or_local_PV_simulation",
                "retentionClass": "week13_ephemeral_evidence",
                "cleanupPolicy": "safe_to_delete_after_week13_summary_and_remote_commit",
            },
        })

    status = "PASS" if not blockers else "FAIL"

    storage_index = {
        "status": status,
        "scope": "week13_cloud_audio_artifact_storage_index_v0",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "sourceRepos": {
            "cloud": {
                "path": str(CLOUD_ROOT),
                "head": git_head(CLOUD_ROOT),
            },
            "mainbase": {
                "path": str(MAINBASE_ROOT),
                "head": git_head(MAINBASE_ROOT),
                "dryrunManifest": str(MAINBASE_DRYRUN_MANIFEST),
                "placementTable": str(MAINBASE_PLACEMENT_TABLE),
            },
            "java": {
                "path": str(JAVA_ROOT),
                "head": git_head(JAVA_ROOT),
                "registryReport": str(JAVA_REGISTRY_REPORT),
            },
        },
        "runtimeContext": {
            "dockerRuntime": "Docker Desktop",
            "kindScope": "local_kind_or_dev_cluster_only",
            "volumeSemantics": "local object directory mapped into pod as a volume/PV simulation",
            "notClaimed": [
                "production cloud object storage",
                "durable S3/MinIO registry",
                "CSI production storage",
                "production SLO",
                "human audition",
                "final mix readiness",
            ],
        },
        "storagePolicy": {
            "localObjectRoot": local_object_root,
            "podMountRoot": pod_mount_root,
            "hostProjectRoot": host_project_root,
            "maxCandidateCountForWeek13": 10,
            "capacityNote": (
                "Current index tracks metadata and source paths only. "
                "Actual audio byte accounting is deferred until physical copy/materialization is implemented."
            ),
            "cleanupPolicy": "delete week13 local object copies only after manifest, dashboard, and weekly summary are committed",
        },
        "metrics": {
            "candidateCount": len(placement_rows),
            "fullClipCount": full_clip_count,
            "eventLocalCount": event_local_count,
            "placementRequiredCount": placement_required_count,
            "fixedPlacementMisplacedCount": mainbase_dryrun.get("fixedPlacementMisplacedCount"),
            "naiveZeroWouldMisplaceCount": mainbase_dryrun.get("naiveZeroWouldMisplaceCount"),
            "dashboardPanelCount": 4,
            "totalLogicalDurationSec": round(total_logical_duration_sec, 6),
        },
        "artifacts": artifacts,
        "blockers": blockers,
        "boundaryStatement": (
            "Cloud indexes Mainbase/Java Week13 audio artifacts for local Docker Desktop/kind storage and dashboard semantics. "
            "This does not implement production object storage, durable registry, final mixer, semantic quality validation, "
            "human audition, or production SLO."
        ),
    }

    dashboard = {
        "title": "Week13 Mix Placement / Audio Artifact Storage",
        "uid": "week13-mix-placement-storage",
        "schemaVersion": 39,
        "version": 1,
        "refresh": "30s",
        "tags": ["week13", "audio-artifact", "mix-placement", "local-kind"],
        "timezone": "browser",
        "panels": [
            {
                "id": 1,
                "type": "stat",
                "title": "Candidate Count",
                "gridPos": {"h": 4, "w": 6, "x": 0, "y": 0},
                "description": "Expected 10 candidates from Mainbase Week13 placement table.",
                "fieldConfig": {"defaults": {}, "overrides": []},
                "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}},
                "targets": [],
            },
            {
                "id": 2,
                "type": "stat",
                "title": "Event-local Placement Required",
                "gridPos": {"h": 4, "w": 6, "x": 6, "y": 0},
                "description": "Expected 5 event_local candidates requiring expectedStartSec placement.",
                "fieldConfig": {"defaults": {}, "overrides": []},
                "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}},
                "targets": [],
            },
            {
                "id": 3,
                "type": "stat",
                "title": "Naive Zero Would Misplace",
                "gridPos": {"h": 4, "w": 6, "x": 12, "y": 0},
                "description": "Negative control: naive t=0 placement would misplace all 5 event_local assets.",
                "fieldConfig": {"defaults": {}, "overrides": []},
                "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False}},
                "targets": [],
            },
            {
                "id": 4,
                "type": "text",
                "title": "Boundary",
                "gridPos": {"h": 6, "w": 18, "x": 0, "y": 4},
                "options": {
                    "mode": "markdown",
                    "content": (
                        "Week13 dashboard stub is versioned for local Docker Desktop/kind semantics only.\\n\\n"
                        "- Not production object storage\\n"
                        "- Not final mixer readiness\\n"
                        "- Not semantic quality validation\\n"
                        "- Not production SLO"
                    ),
                },
                "targets": [],
            },
        ],
    }

    runbook = f"""# Week13 Audio Artifact Storage Runbook

## Scope

This runbook records local Docker Desktop / kind storage semantics for Week13 audio artifact evidence.

Generated from:

- Mainbase dry-run manifest: `{MAINBASE_DRYRUN_MANIFEST}`
- Mainbase placement table: `{MAINBASE_PLACEMENT_TABLE}`
- Java registry report: `{JAVA_REGISTRY_REPORT}`

## Runtime context

- Docker runtime: Docker Desktop
- Local object root: `{local_object_root}`
- Pod mount root: `{pod_mount_root}`
- Storage mode: local object directory / hostPath / local PV simulation

## Placement rule

- `full_clip`: global timeline starts at `0`
- `event_local`: global timeline starts at `expectedStartSec`

## Current metrics

- candidateCount: {len(placement_rows)}
- fullClipCount: {full_clip_count}
- eventLocalCount: {event_local_count}
- placementRequiredCount: {placement_required_count}
- fixedPlacementMisplacedCount: {mainbase_dryrun.get("fixedPlacementMisplacedCount")}
- naiveZeroWouldMisplaceCount: {mainbase_dryrun.get("naiveZeroWouldMisplaceCount")}

## Cleanup policy

Week13 local object copies are safe to delete only after the storage index, dashboard stub, and weekly summary are committed.

## Boundary

This is not production object storage, not a durable registry, not CSI production storage, not final mixer readiness, not semantic quality validation, not human audition, and not production SLO.
"""

    manifest = {
        "status": status,
        "scope": "week13_cloud_audio_artifact_storage_manifest_v0",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "outputs": {
            "storageIndex": str(OUT_INDEX.relative_to(CLOUD_ROOT)),
            "runbook": str(OUT_RUNBOOK.relative_to(CLOUD_ROOT)),
            "dashboard": str(OUT_DASHBOARD.relative_to(CLOUD_ROOT)),
            "log": str(OUT_LOG.relative_to(CLOUD_ROOT)),
        },
        "metrics": storage_index["metrics"],
        "blockers": blockers,
        "boundaryStatement": storage_index["boundaryStatement"],
    }

    OUT_INDEX.parent.mkdir(parents=True, exist_ok=True)
    OUT_RUNBOOK.parent.mkdir(parents=True, exist_ok=True)
    OUT_DASHBOARD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    OUT_LOG.parent.mkdir(parents=True, exist_ok=True)

    OUT_INDEX.write_text(json.dumps(storage_index, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_DASHBOARD.write_text(json.dumps(dashboard, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_RUNBOOK.write_text(runbook, encoding="utf-8")
    OUT_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    log_text = "\n".join([
        f"status={status}",
        f"candidateCount={len(placement_rows)}",
        f"fullClipCount={full_clip_count}",
        f"eventLocalCount={event_local_count}",
        f"placementRequiredCount={placement_required_count}",
        f"fixedPlacementMisplacedCount={mainbase_dryrun.get('fixedPlacementMisplacedCount')}",
        f"naiveZeroWouldMisplaceCount={mainbase_dryrun.get('naiveZeroWouldMisplaceCount')}",
        f"blockers={blockers}",
        f"storageIndex={OUT_INDEX}",
        f"runbook={OUT_RUNBOOK}",
        f"dashboard={OUT_DASHBOARD}",
        f"manifest={OUT_MANIFEST}",
    ])
    OUT_LOG.write_text(log_text + "\n", encoding="utf-8")

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())