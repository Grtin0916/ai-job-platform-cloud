#!/usr/bin/env python3
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_LOCAL_ROOT = "artifacts/local-object-store/audio-candidates/week13"
DEFAULT_POD_ROOT = "/mnt/audio-candidates/week13"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def safe_name(s: str) -> str:
    s = str(s)
    s = s.replace("\\", "/").split("/")[-1]
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s)
    return s or "unknown.wav"


def extension_from_uri(uri: str) -> str:
    name = safe_name(uri)
    suffix = Path(name).suffix
    return suffix if suffix else ".wav"


def normalize_mode(mode):
    mode = str(mode or "").strip()
    return mode if mode else "unknown_time_mode"


def build_object_projection(candidate, local_root, pod_root):
    cid = str(candidate.get("candidateId") or "").strip()
    if not cid:
        raise ValueError("candidate without candidateId")

    mode = normalize_mode(candidate.get("assetTimeMode"))
    ext = extension_from_uri(candidate.get("audioUri") or "")
    object_key = f"audio-candidates/week13/{mode}/{cid}{ext}"

    local_object_path = str(Path(local_root) / mode / f"{cid}{ext}")
    pod_path = str(Path(pod_root) / mode / f"{cid}{ext}")

    out = dict(candidate)
    out["objectKey"] = object_key
    out["localObjectPath"] = local_object_path
    out["podPath"] = pod_path
    out["storageClass"] = "local-kind-hostpath-simulation"
    out["storageProjectionMode"] = "metadata_only_no_file_copy"
    out["materialized"] = False
    return out


def count(items, pred):
    return sum(1 for x in items if pred(x))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--java-snapshot",
        default=str(Path.home() / "work/media-task-platform-java/artifacts/manifests/week13_java_audio_artifact_registry_snapshot.json"),
    )
    parser.add_argument(
        "--existing-cloud-index",
        default="loadtest/reports/week13_audio_artifact_storage_index.json",
    )
    parser.add_argument(
        "--out",
        default="loadtest/reports/week13_audio_artifact_storage_index.json",
    )
    parser.add_argument("--local-root", default=DEFAULT_LOCAL_ROOT)
    parser.add_argument("--pod-root", default=DEFAULT_POD_ROOT)
    args = parser.parse_args()

    java_path = Path(args.java_snapshot).expanduser().resolve()
    cloud_path = Path(args.existing_cloud_index).expanduser().resolve()
    out_path = Path(args.out).expanduser()

    java = load_json(java_path)
    old_cloud = load_json(cloud_path) if cloud_path.exists() else {}

    candidates = java.get("artifacts") or []
    if len(candidates) != 10:
        raise SystemExit(f"java snapshot candidate count is not 10: {len(candidates)}")

    projected = [
        build_object_projection(c, args.local_root, args.pod_root)
        for c in candidates
    ]

    full_clip = [x for x in projected if x.get("assetTimeMode") == "full_clip"]
    event_local = [x for x in projected if x.get("assetTimeMode") == "event_local"]

    blockers = []
    if len(projected) != 10:
        blockers.append(f"CANDIDATE_COUNT_NOT_10:{len(projected)}")
    if any(not x.get("objectKey") for x in projected):
        blockers.append("OBJECT_KEY_MISSING")
    if any(not x.get("localObjectPath") for x in projected):
        blockers.append("LOCAL_OBJECT_PATH_MISSING")
    if any(not x.get("podPath") for x in projected):
        blockers.append("POD_PATH_MISSING")

    # 这里继续守住 placement 语义：full_clip 固定 0，event_local 等于 expectedStartSec。
    placement_errors = []
    for x in projected:
        mode = x.get("assetTimeMode")
        expected = float(x.get("expectedStartSec"))
        global_start = float(x.get("globalStartSec"))
        cid = x.get("candidateId")
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

    if placement_errors:
        blockers.append("PLACEMENT_RULE_VIOLATION")

    report = {
        "status": "PASS" if not blockers else "FAIL",
        "scope": "week13_audio_artifact_storage_index_v1_object_projection",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sourceJavaSnapshot": str(java_path),
        "previousCloudIndex": str(cloud_path),
        "candidateCount": len(projected),
        "fullClipCount": len(full_clip),
        "eventLocalCount": len(event_local),
        "placementRequiredCount": count(projected, lambda x: bool(x.get("placementRequired"))),
        "objectKeyCount": count(projected, lambda x: bool(x.get("objectKey"))),
        "localObjectPathCount": count(projected, lambda x: bool(x.get("localObjectPath"))),
        "podPathCount": count(projected, lambda x: bool(x.get("podPath"))),
        "fixedPlacementMisplacedCount": len(placement_errors),
        "naiveZeroWouldMisplaceCount": count(
            projected,
            lambda x: x.get("assetTimeMode") == "event_local" and float(x.get("expectedStartSec")) != 0.0
        ),
        "dashboardPanelCount": old_cloud.get("dashboardPanelCount"),
        "storageRoot": {
            "localRoot": args.local_root,
            "podRoot": args.pod_root,
            "mode": "local Docker Desktop/kind hostPath-style metadata projection",
        },
        "artifacts": projected,
        "placementErrors": placement_errors,
        "blockers": blockers,
        "boundaryStatement": (
            "This index projects Java registry candidates into local/kind storage paths. "
            "It is metadata-only and does not claim durable registry, MinIO/S3, CSI, production SLO, "
            "final mixer, semantic quality, or human audition readiness."
        ),
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "status": report["status"],
        "candidateCount": report["candidateCount"],
        "fullClipCount": report["fullClipCount"],
        "eventLocalCount": report["eventLocalCount"],
        "placementRequiredCount": report["placementRequiredCount"],
        "objectKeyCount": report["objectKeyCount"],
        "localObjectPathCount": report["localObjectPathCount"],
        "podPathCount": report["podPathCount"],
        "fixedPlacementMisplacedCount": report["fixedPlacementMisplacedCount"],
        "naiveZeroWouldMisplaceCount": report["naiveZeroWouldMisplaceCount"],
        "blockers": report["blockers"],
    }, indent=2, ensure_ascii=False))

    if report["status"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()