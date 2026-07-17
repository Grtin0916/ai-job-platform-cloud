#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

DRYRUN_DEFAULT = "loadtest/reports/week13_materialized_copy_mount_dryrun.json"
MANIFEST_DEFAULT = "loadtest/reports/week13_materialized_audio_artifact_manifest.json"
MOUNT_DEFAULT = "loadtest/reports/week13_mount_read_contract.json"
OBJECT_ROOT_DEFAULT = "artifacts/local-object-store"
POD_PREFIX_DEFAULT = "/mnt/audio-candidates"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def iter_dicts(x: Any):
    if isinstance(x, dict):
        yield x
        for v in x.values():
            yield from iter_dicts(v)
    elif isinstance(x, list):
        for v in x:
            yield from iter_dicts(v)


def get_first(d: dict[str, Any], names: list[str]) -> Any:
    lower = {str(k).lower(): k for k in d.keys()}
    for name in names:
        k = lower.get(name.lower())
        if k is not None:
            return d.get(k)
    return None


def find_source_wav(d: dict[str, Any]) -> str | None:
    preferred = [
        "sourcePath", "source_path", "sourceUri", "source_uri",
        "mainbaseSourcePath", "mainbase_source_path",
        "sourceAudioPath", "source_audio_path",
        "audioSourcePath", "audio_source_path",
    ]
    v = get_first(d, preferred)
    if isinstance(v, str) and ".wav" in v:
        return v

    candidates = []
    for k, v in d.items():
        ks = str(k).lower()
        if isinstance(v, str) and ".wav" in v:
            score = 0
            if "source" in ks:
                score += 10
            if "mainbase" in v.lower() or "audio_engineering_repo" in v.lower():
                score += 5
            if "local-object-store" in v.lower():
                score -= 10
            candidates.append((score, v))
    if not candidates:
        return None
    candidates.sort(reverse=True, key=lambda t: t[0])
    return candidates[0][1]


def find_dest_hint(d: dict[str, Any]) -> str | None:
    preferred = [
        "objectKey", "object_key",
        "storagePath", "storage_path",
        "targetPath", "target_path",
        "destinationPath", "destination_path",
        "destPath", "dest_path",
        "localObjectPath", "local_object_path",
        "cloudObjectPath", "cloud_object_path",
    ]
    for name in preferred:
        v = get_first(d, [name])
        if isinstance(v, str) and ".wav" in v:
            return v

    candidates = []
    for k, v in d.items():
        ks = str(k).lower()
        if isinstance(v, str) and ".wav" in v:
            score = 0
            if any(s in ks for s in ["object", "storage", "target", "dest", "local"]):
                score += 10
            if "local-object-store" in v.lower():
                score += 5
            if "source" in ks:
                score -= 10
            candidates.append((score, v))
    if not candidates:
        return None
    candidates.sort(reverse=True, key=lambda t: t[0])
    return candidates[0][1]


def normalize_candidate_id(raw: Any, fallback: str) -> str:
    if raw is None:
        return fallback
    s = str(raw).strip()
    return s if s else fallback


def resolve_source(raw: str, cloud_root: Path, mainbase_root: Path) -> Path:
    raw = raw.replace("file://", "")
    raw_path = Path(raw).expanduser()

    candidates = []
    if raw_path.is_absolute():
        candidates.append(raw_path)
    else:
        candidates.extend([
            cloud_root / raw_path,
            mainbase_root / raw_path,
            Path.home() / raw_path,
        ])

    for p in candidates:
        if p.exists():
            return p.resolve()
    return candidates[0].resolve()


def dest_from_hint(
    hint: str | None,
    source: Path,
    candidate_id: str,
    object_root: Path,
) -> tuple[Path, str]:
    if hint:
        h = hint.replace("file://", "").strip()
        hpath = Path(h)

        marker = "artifacts/local-object-store/"
        if marker in h:
            rel = h.split(marker, 1)[1].lstrip("/")
            return (object_root / rel).resolve(), rel

        if hpath.is_absolute():
            try:
                rel = hpath.relative_to(object_root.resolve()).as_posix()
                return hpath.resolve(), rel
            except ValueError:
                pass

        rel = h.lstrip("/")
        if rel.startswith("audio-candidates/") or rel.startswith("week13/"):
            return (object_root / rel).resolve(), rel

        if rel.startswith("artifacts/"):
            rel = Path(rel).name

    safe_id = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in candidate_id)
    rel = f"audio-candidates/week13/{safe_id}_{source.name}"
    return (object_root / rel).resolve(), rel


def extract_records(dryrun: Any, cloud_root: Path, mainbase_root: Path, object_root: Path) -> list[dict[str, Any]]:
    records = []
    seen = set()

    for i, d in enumerate(iter_dicts(dryrun)):
        src_raw = find_source_wav(d)
        if not src_raw:
            continue

        candidate_id = normalize_candidate_id(
            get_first(d, ["candidateId", "candidate_id", "id", "audioCandidateId", "audio_candidate_id"]),
            fallback=f"candidate_{i:03d}",
        )
        src = resolve_source(src_raw, cloud_root, mainbase_root)
        hint = find_dest_hint(d)
        dest, object_key = dest_from_hint(hint, src, candidate_id, object_root)

        key = (candidate_id, str(src), str(dest))
        if key in seen:
            continue
        seen.add(key)

        records.append({
            "candidateId": candidate_id,
            "assetTimeMode": get_first(d, ["assetTimeMode", "asset_time_mode", "timeMode", "time_mode"]),
            "expectedStartSec": get_first(d, ["expectedStartSec", "expected_start_sec"]),
            "placementRequired": get_first(d, ["placementRequired", "placement_required"]),
            "sourcePathRaw": src_raw,
            "sourcePath": str(src),
            "objectKey": object_key,
            "localObjectPath": str(dest),
        })

    return records


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dryrun", default=DRYRUN_DEFAULT)
    ap.add_argument("--manifest", default=MANIFEST_DEFAULT)
    ap.add_argument("--mount-contract", default=MOUNT_DEFAULT)
    ap.add_argument("--object-root", default=OBJECT_ROOT_DEFAULT)
    ap.add_argument("--pod-prefix", default=POD_PREFIX_DEFAULT)
    ap.add_argument("--mainbase", default=os.environ.get("MAINBASE", str(Path.home() / "work/grt_work/audio_engineering_repo_skeleton_v1")))
    args = ap.parse_args()

    cloud_root = Path.cwd().resolve()
    dryrun_path = cloud_root / args.dryrun
    manifest_path = cloud_root / args.manifest
    mount_path = cloud_root / args.mount_contract
    object_root = (cloud_root / args.object_root).resolve()
    mainbase_root = Path(args.mainbase).expanduser().resolve()

    dryrun = load_json(dryrun_path)
    records = extract_records(dryrun, cloud_root, mainbase_root, object_root)

    expected_count = dryrun.get("copyPlanCount") or dryrun.get("candidateCount") or 10
    blockers = []
    materialized = []

    if len(records) != expected_count:
        blockers.append(f"extracted_records={len(records)} expected={expected_count}")

    for r in records:
        src = Path(r["sourcePath"])
        dst = Path(r["localObjectPath"])

        source_exists = src.exists()
        copy_ok = False
        error = None
        src_size = None
        dst_size = None
        src_sha = None
        dst_sha = None

        if not source_exists:
            blockers.append(f"missing_source:{r['candidateId']}:{src}")
        else:
            try:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                src_size = src.stat().st_size
                dst_size = dst.stat().st_size
                src_sha = sha256_file(src)
                dst_sha = sha256_file(dst)
                copy_ok = src_size == dst_size and src_sha == dst_sha
                if not copy_ok:
                    blockers.append(f"hash_or_size_mismatch:{r['candidateId']}")
            except Exception as e:
                error = repr(e)
                blockers.append(f"copy_error:{r['candidateId']}:{error}")

        r.update({
            "sourceExists": source_exists,
            "materialized": copy_ok,
            "sourceSizeBytes": src_size,
            "localSizeBytes": dst_size,
            "sourceSha256": src_sha,
            "localSha256": dst_sha,
            "sizeMatched": src_size is not None and src_size == dst_size,
            "sha256Matched": src_sha is not None and src_sha == dst_sha,
            "copyError": error,
        })
        materialized.append(r)

    materialized_count = sum(1 for r in materialized if r["materialized"])
    size_matched_count = sum(1 for r in materialized if r["sizeMatched"])
    hash_matched_count = sum(1 for r in materialized if r["sha256Matched"])
    missing_source_count = sum(1 for r in materialized if not r["sourceExists"])

    status = "PASS" if not blockers and materialized_count == expected_count else "FAIL"

    manifest = {
        "status": status,
        "scope": "week13_materialized_audio_artifact_manifest_v1",
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "sourceDryrun": args.dryrun,
        "sourceDryrunStatus": dryrun.get("status"),
        "candidateCount": expected_count,
        "extractedRecordCount": len(records),
        "materializedCount": materialized_count,
        "sizeMatchedCount": size_matched_count,
        "hashMatchedCount": hash_matched_count,
        "missingSourceCount": missing_source_count,
        "objectRoot": str(object_root),
        "blockers": blockers,
        "records": materialized,
    }

    mount_records = []
    for r in materialized:
        local_path = Path(r["localObjectPath"])
        object_key = r["objectKey"]
        pod_path = str(Path(args.pod_prefix) / object_key.replace("audio-candidates/", ""))
        mount_records.append({
            "candidateId": r["candidateId"],
            "objectKey": object_key,
            "localObjectPath": str(local_path),
            "podPath": pod_path,
            "existsInCloudLocal": local_path.exists(),
            "readableByPodPathContract": local_path.exists() and r["sha256Matched"] and r["sizeMatched"],
            "sizeBytes": r["localSizeBytes"],
            "sha256": r["localSha256"],
            "assetTimeMode": r.get("assetTimeMode"),
            "expectedStartSec": r.get("expectedStartSec"),
            "placementRequired": r.get("placementRequired"),
        })

    readable_count = sum(1 for r in mount_records if r["readableByPodPathContract"])
    mount_contract = {
        "status": "PASS" if status == "PASS" and readable_count == expected_count else "FAIL",
        "scope": "week13_mount_read_contract_v1_local_object_store",
        "generatedAt": manifest["generatedAt"],
        "candidateCount": expected_count,
        "readableCount": readable_count,
        "podPathPrefix": args.pod_prefix,
        "objectRoot": str(object_root),
        "blockers": [] if status == "PASS" and readable_count == expected_count else blockers,
        "records": mount_records,
        "boundary": [
            "local object store simulation only",
            "not S3 or MinIO",
            "not CSI or production PV",
            "podPath is a read contract for later kind/hostPath wiring",
        ],
    }

    write_json(manifest_path, manifest)
    write_json(mount_path, mount_contract)

    print(json.dumps({
        "manifest": str(manifest_path),
        "mountContract": str(mount_path),
        "status": manifest["status"],
        "mountStatus": mount_contract["status"],
        "candidateCount": expected_count,
        "extractedRecordCount": len(records),
        "materializedCount": materialized_count,
        "sizeMatchedCount": size_matched_count,
        "hashMatchedCount": hash_matched_count,
        "missingSourceCount": missing_source_count,
        "readableCount": readable_count,
        "blockers": blockers,
    }, ensure_ascii=False, indent=2))

    return 0 if status == "PASS" and mount_contract["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
