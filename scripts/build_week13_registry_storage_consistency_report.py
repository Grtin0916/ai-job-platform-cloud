#!/usr/bin/env python3
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

CORE_FIELDS = [
    "assetTimeMode",
    "expectedStartSec",
    "globalStartSec",
    "placementRequired",
]

REQUIRED_JAVA_FIELDS = [
    "candidateId",
    "audioUri",
    "sourceType",
    "assetTimeMode",
    "expectedStartSec",
    "globalStartSec",
    "placementRequired",
    "status",
]

STORAGE_FIELDS = [
    "objectKey",
    "localObjectPath",
    "podPath",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def iter_dicts(obj):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from iter_dicts(v)
    elif isinstance(obj, list):
        for x in obj:
            yield from iter_dicts(x)


def first_present(d, aliases):
    for k in aliases:
        if k in d:
            return d.get(k)
    return None


def normalize_item(d):
    out = {}

    out["candidateId"] = first_present(d, [
        "candidateId", "candidate_id", "audioCandidateId", "candidateID", "id"
    ])
    out["audioUri"] = first_present(d, [
        "audioUri", "audio_uri", "sourceAudioUri", "localAudioUri", "uri", "path"
    ])
    out["sourceType"] = first_present(d, [
        "sourceType", "source_type", "generatorName", "source"
    ])
    out["assetTimeMode"] = first_present(d, [
        "assetTimeMode", "timeMode", "asset_time_mode"
    ])
    out["expectedStartSec"] = first_present(d, [
        "expectedStartSec", "expected_start_sec", "startSec", "eventStartSec"
    ])
    out["globalStartSec"] = first_present(d, [
        "globalStartSec", "global_start_sec", "placementStartSec", "placedStartSec"
    ])
    out["placementRequired"] = first_present(d, [
        "placementRequired", "placement_required", "requiresPlacement"
    ])
    out["status"] = first_present(d, [
        "status", "candidateStatus", "storageStatus"
    ])

    out["objectKey"] = first_present(d, [
        "objectKey", "object_key", "storageObjectKey", "key"
    ])
    out["localObjectPath"] = first_present(d, [
        "localObjectPath", "local_object_path", "localPath", "hostPath"
    ])
    out["podPath"] = first_present(d, [
        "podPath", "pod_path", "containerPath", "mountPath"
    ])

    for k, v in d.items():
        out.setdefault(k, v)

    return out


def looks_candidate_like(d):
    keys = set(d.keys())
    has_id = bool(keys & {
        "candidateId", "candidate_id", "audioCandidateId", "candidateID"
    })
    has_timing = bool(keys & {
        "assetTimeMode", "timeMode", "expectedStartSec", "globalStartSec"
    })
    has_storage = bool(keys & {
        "objectKey", "object_key", "localObjectPath", "podPath", "mountPath"
    })
    has_audio = bool(keys & {
        "audioUri", "sourceAudioUri", "localAudioUri"
    })
    return has_id and (has_timing or has_storage or has_audio)


def richness_score(item):
    score = 0
    for k in REQUIRED_JAVA_FIELDS + STORAGE_FIELDS:
        v = item.get(k)
        if v is not None and v != "":
            score += 1
    return score


def collect_candidate_map(obj):
    by_id = {}
    for d in iter_dicts(obj):
        if not isinstance(d, dict):
            continue
        if not looks_candidate_like(d):
            continue
        item = normalize_item(d)
        cid = item.get("candidateId")
        if not cid:
            continue
        cid = str(cid)
        old = by_id.get(cid)
        if old is None or richness_score(item) > richness_score(old):
            by_id[cid] = item
    return by_id


def to_float(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except Exception:
        return None


def to_bool(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        s = v.strip().lower()
        if s in {"true", "1", "yes", "y"}:
            return True
        if s in {"false", "0", "no", "n"}:
            return False
    return v


def values_equal(field, a, b, tol=1e-6):
    if field.endswith("Sec"):
        fa, fb = to_float(a), to_float(b)
        if fa is None or fb is None:
            return fa == fb
        return math.isclose(fa, fb, abs_tol=tol)
    if field == "placementRequired":
        return to_bool(a) == to_bool(b)
    return a == b


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--java-snapshot",
        default=str(Path.home() / "work/media-task-platform-java/artifacts/manifests/week13_java_audio_artifact_registry_snapshot.json"),
    )
    parser.add_argument(
        "--cloud-index",
        default="loadtest/reports/week13_audio_artifact_storage_index.json",
    )
    parser.add_argument(
        "--out",
        default="loadtest/reports/week13_java_cloud_registry_storage_consistency_report.json",
    )
    args = parser.parse_args()

    java_path = Path(args.java_snapshot).expanduser().resolve()
    cloud_path = Path(args.cloud_index).expanduser().resolve()
    out_path = Path(args.out).expanduser()

    java_obj = load_json(java_path)
    cloud_obj = load_json(cloud_path)

    java_items = collect_candidate_map(java_obj.get("artifacts", java_obj))
    cloud_items = collect_candidate_map(cloud_obj)

    java_ids = set(java_items)
    cloud_ids = set(cloud_items)
    shared_ids = sorted(java_ids & cloud_ids)

    missing_in_java = sorted(cloud_ids - java_ids)
    missing_in_cloud = sorted(java_ids - cloud_ids)

    field_mismatches = []
    placement_drifts = []
    object_key_missing = []
    storage_path_missing = []

    for cid in shared_ids:
        j = java_items[cid]
        c = cloud_items[cid]

        for field in CORE_FIELDS:
            if not values_equal(field, j.get(field), c.get(field)):
                field_mismatches.append({
                    "candidateId": cid,
                    "field": field,
                    "java": j.get(field),
                    "cloud": c.get(field),
                })

        j_global = to_float(j.get("globalStartSec"))
        c_global = to_float(c.get("globalStartSec"))
        j_expected = to_float(j.get("expectedStartSec"))
        c_expected = to_float(c.get("expectedStartSec"))
        mode = str(j.get("assetTimeMode") or c.get("assetTimeMode") or "")

        drift_reasons = []
        if j_global is None or c_global is None or not math.isclose(j_global, c_global, abs_tol=1e-6):
            drift_reasons.append("JAVA_CLOUD_GLOBAL_START_DRIFT")
        if j_expected is None or c_expected is None or not math.isclose(j_expected, c_expected, abs_tol=1e-6):
            drift_reasons.append("JAVA_CLOUD_EXPECTED_START_DRIFT")
        if mode == "event_local" and c_global is not None and c_expected is not None:
            if not math.isclose(c_global, c_expected, abs_tol=1e-6):
                drift_reasons.append("EVENT_LOCAL_NOT_PLACED_AT_EXPECTED_START")
        if mode == "full_clip" and c_global is not None:
            if not math.isclose(c_global, 0.0, abs_tol=1e-6):
                drift_reasons.append("FULL_CLIP_NOT_AT_GLOBAL_ZERO")

        if drift_reasons:
            placement_drifts.append({
                "candidateId": cid,
                "assetTimeMode": mode,
                "javaExpectedStartSec": j.get("expectedStartSec"),
                "javaGlobalStartSec": j.get("globalStartSec"),
                "cloudExpectedStartSec": c.get("expectedStartSec"),
                "cloudGlobalStartSec": c.get("globalStartSec"),
                "reasons": drift_reasons,
            })

        if not c.get("objectKey"):
            object_key_missing.append(cid)

        if not c.get("localObjectPath") or not c.get("podPath"):
            storage_path_missing.append({
                "candidateId": cid,
                "localObjectPath": c.get("localObjectPath"),
                "podPath": c.get("podPath"),
            })

    blockers = []
    if len(java_items) != 10:
        blockers.append(f"JAVA_CANDIDATE_COUNT_NOT_10:{len(java_items)}")
    if len(cloud_items) != 10:
        blockers.append(f"CLOUD_CANDIDATE_COUNT_NOT_10:{len(cloud_items)}")
    if missing_in_java:
        blockers.append("MISSING_IN_JAVA")
    if missing_in_cloud:
        blockers.append("MISSING_IN_CLOUD")
    if field_mismatches:
        blockers.append("FIELD_MISMATCH")
    if placement_drifts:
        blockers.append("PLACEMENT_DRIFT")
    if object_key_missing:
        blockers.append("OBJECT_KEY_MISSING")

    report = {
        "status": "PASS" if not blockers else "FAIL",
        "scope": "week13_java_cloud_registry_storage_consistency_gate_v0",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "javaSnapshotPath": str(java_path),
        "javaSnapshotSha256": sha256(java_path),
        "cloudStorageIndexPath": str(cloud_path),
        "cloudStorageIndexSha256": sha256(cloud_path),
        "javaCandidateCount": len(java_items),
        "cloudCandidateCount": len(cloud_items),
        "candidateCount": len(shared_ids),
        "missingInJava": missing_in_java,
        "missingInJavaCount": len(missing_in_java),
        "missingInCloud": missing_in_cloud,
        "missingInCloudCount": len(missing_in_cloud),
        "fieldMismatchCount": len(field_mismatches),
        "fieldMismatchDetails": field_mismatches,
        "placementDriftCount": len(placement_drifts),
        "placementDriftDetails": placement_drifts,
        "objectKeyMissingCount": len(object_key_missing),
        "objectKeyMissingCandidateIds": object_key_missing,
        "storagePathMissingCount": len(storage_path_missing),
        "storagePathMissingDetails": storage_path_missing,
        "sharedCandidateIds": shared_ids,
        "javaOnlyCandidateIds": missing_in_cloud,
        "cloudOnlyCandidateIds": missing_in_java,
        "blockers": blockers,
        "boundaryStatement": (
            "This report checks Java registry metadata against Cloud local/kind storage index only. "
            "It does not claim durable registry, S3/MinIO, CSI, production SLO, final mixer, "
            "semantic quality, or human audition readiness."
        ),
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    summary = {
        "status": report["status"],
        "javaCandidateCount": report["javaCandidateCount"],
        "cloudCandidateCount": report["cloudCandidateCount"],
        "candidateCount": report["candidateCount"],
        "missingInJavaCount": report["missingInJavaCount"],
        "missingInCloudCount": report["missingInCloudCount"],
        "fieldMismatchCount": report["fieldMismatchCount"],
        "placementDriftCount": report["placementDriftCount"],
        "objectKeyMissingCount": report["objectKeyMissingCount"],
        "storagePathMissingCount": report["storagePathMissingCount"],
        "blockers": report["blockers"],
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if report["status"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()