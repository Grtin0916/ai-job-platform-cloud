#!/usr/bin/env python3
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def size_or_none(path: Path):
    return path.stat().st_size if path.exists() and path.is_file() else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--storage-index",
        default="loadtest/reports/week13_audio_artifact_storage_index.json",
    )
    parser.add_argument(
        "--mainbase-root",
        default=str(Path.home() / "work/audio_engineering_repo_skeleton_v1"),
    )
    parser.add_argument(
        "--out",
        default="loadtest/reports/week13_materialized_copy_mount_dryrun.json",
    )
    args = parser.parse_args()

    storage_index_path = Path(args.storage_index).expanduser().resolve()
    mainbase_root = Path(args.mainbase_root).expanduser().resolve()
    out_path = Path(args.out).expanduser()

    index = load_json(storage_index_path)
    artifacts = index.get("artifacts") or []

    copy_plan = []
    missing_sources = []
    placement_errors = []
    invalid_targets = []

    for item in artifacts:
        cid = item.get("candidateId")
        audio_uri = item.get("audioUri")
        local_object_path = item.get("localObjectPath")
        pod_path = item.get("podPath")
        object_key = item.get("objectKey")

        src = mainbase_root / str(audio_uri)
        dst = Path(str(local_object_path))

        mode = item.get("assetTimeMode")
        expected = float(item.get("expectedStartSec"))
        global_start = float(item.get("globalStartSec"))

        if mode == "full_clip" and abs(global_start - 0.0) > 1e-6:
            placement_errors.append({
                "candidateId": cid,
                "reason": "FULL_CLIP_NOT_AT_ZERO",
                "expectedStartSec": expected,
                "globalStartSec": global_start,
            })

        if mode == "event_local" and abs(global_start - expected) > 1e-6:
            placement_errors.append({
                "candidateId": cid,
                "reason": "EVENT_LOCAL_NOT_AT_EXPECTED_START",
                "expectedStartSec": expected,
                "globalStartSec": global_start,
            })

        if not src.exists():
            missing_sources.append({
                "candidateId": cid,
                "audioUri": audio_uri,
                "expectedSourcePath": str(src),
            })

        if not object_key or not local_object_path or not pod_path:
            invalid_targets.append({
                "candidateId": cid,
                "objectKey": object_key,
                "localObjectPath": local_object_path,
                "podPath": pod_path,
            })

        copy_plan.append({
            "candidateId": cid,
            "assetTimeMode": mode,
            "placementRequired": item.get("placementRequired"),
            "expectedStartSec": expected,
            "globalStartSec": global_start,
            "sourceAudioUri": audio_uri,
            "sourcePath": str(src),
            "sourceExists": src.exists(),
            "sourceSizeBytes": size_or_none(src),
            "objectKey": object_key,
            "localObjectPath": local_object_path,
            "podPath": pod_path,
            "copyAction": "COPY_IF_MATERIALIZE_ENABLED",
            "mountAction": "READ_FROM_POD_PATH_AFTER_HOSTPATH_MOUNT",
        })

    blockers = []
    if len(artifacts) != 10:
        blockers.append(f"CANDIDATE_COUNT_NOT_10:{len(artifacts)}")
    if missing_sources:
        blockers.append("SOURCE_AUDIO_MISSING")
    if invalid_targets:
        blockers.append("INVALID_STORAGE_TARGET")
    if placement_errors:
        blockers.append("PLACEMENT_RULE_VIOLATION")

    full_clip_count = sum(1 for x in copy_plan if x.get("assetTimeMode") == "full_clip")
    event_local_count = sum(1 for x in copy_plan if x.get("assetTimeMode") == "event_local")

    report = {
        "status": "PASS" if not blockers else "FAIL",
        "scope": "week13_materialized_copy_mount_dryrun_v0",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "storageIndexPath": str(storage_index_path),
        "mainbaseRoot": str(mainbase_root),
        "candidateCount": len(copy_plan),
        "fullClipCount": full_clip_count,
        "eventLocalCount": event_local_count,
        "copyPlanCount": len(copy_plan),
        "sourceExistsCount": sum(1 for x in copy_plan if x.get("sourceExists")),
        "missingSourceCount": len(missing_sources),
        "invalidTargetCount": len(invalid_targets),
        "placementErrorCount": len(placement_errors),
        "materialized": False,
        "dryRun": True,
        "copyPlan": copy_plan,
        "missingSources": missing_sources,
        "invalidTargets": invalid_targets,
        "placementErrors": placement_errors,
        "hostPathSimulation": {
            "hostRoot": index.get("storageRoot", {}).get("localRoot"),
            "podRoot": index.get("storageRoot", {}).get("podRoot"),
            "semantics": "metadata-only dry-run for local Docker Desktop/kind hostPath-style mount simulation",
        },
        "blockers": blockers,
        "boundaryStatement": (
            "This dry-run verifies whether Cloud can materialize Java/Mainbase audio candidates "
            "into local object paths and expose pod paths. It does not perform file copy, does not "
            "claim durable object storage, MinIO/S3, CSI, production SLO, final mixer, semantic "
            "quality, or human audition readiness."
        ),
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "status": report["status"],
        "candidateCount": report["candidateCount"],
        "copyPlanCount": report["copyPlanCount"],
        "sourceExistsCount": report["sourceExistsCount"],
        "missingSourceCount": report["missingSourceCount"],
        "invalidTargetCount": report["invalidTargetCount"],
        "placementErrorCount": report["placementErrorCount"],
        "blockers": report["blockers"],
    }, indent=2, ensure_ascii=False))

    if report["status"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()