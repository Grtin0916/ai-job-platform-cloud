#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import wave
from pathlib import Path
from typing import Any


DEFAULT_MOUNT = "loadtest/reports/week13_mount_read_contract.json"
DEFAULT_MANIFEST = "loadtest/reports/week13_materialized_audio_artifact_manifest.json"
DEFAULT_OUT = "loadtest/reports/week13_pod_audio_read_simulation_report.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_wav(path: Path) -> dict[str, Any]:
    with wave.open(str(path), "rb") as w:
        channels = w.getnchannels()
        sample_width = w.getsampwidth()
        sample_rate = w.getframerate()
        frames = w.getnframes()
        comp_type = w.getcomptype()
        duration_sec = frames / sample_rate if sample_rate else 0.0
        preview = w.readframes(min(frames, 1024))
    return {
        "channels": channels,
        "sampleWidthBytes": sample_width,
        "sampleRateHz": sample_rate,
        "frames": frames,
        "durationSec": round(duration_sec, 6),
        "compressionType": comp_type,
        "previewBytesRead": len(preview),
        "validPcmWav": comp_type == "NONE" and channels > 0 and sample_width > 0 and sample_rate > 0 and frames > 0,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mount-contract", default=DEFAULT_MOUNT)
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST)
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    root = Path.cwd().resolve()
    mount_path = root / args.mount_contract
    manifest_path = root / args.manifest
    out_path = root / args.out

    mount = load_json(mount_path)
    manifest = load_json(manifest_path)

    manifest_by_key = {
        r.get("objectKey"): r
        for r in manifest.get("records", [])
        if r.get("objectKey")
    }

    blockers: list[str] = []
    records: list[dict[str, Any]] = []

    if mount.get("status") != "PASS":
        blockers.append(f"mount_contract_status={mount.get('status')}")
    if manifest.get("status") != "PASS":
        blockers.append(f"materialized_manifest_status={manifest.get('status')}")

    for r in mount.get("records", []):
        candidate_id = r.get("candidateId")
        object_key = r.get("objectKey")
        pod_path = r.get("podPath")
        local_path = Path(r.get("localObjectPath", ""))

        result: dict[str, Any] = {
            "candidateId": candidate_id,
            "objectKey": object_key,
            "podPath": pod_path,
            "localObjectPath": str(local_path),
            "podPathMapped": bool(pod_path and object_key and str(pod_path).endswith(str(object_key).replace("audio-candidates/", ""))),
            "localExists": local_path.exists(),
            "audioReadable": False,
            "sha256Verified": False,
            "sizeVerified": False,
            "assetTimeMode": r.get("assetTimeMode"),
            "expectedStartSec": r.get("expectedStartSec"),
            "placementRequired": r.get("placementRequired"),
            "error": None,
        }

        m = manifest_by_key.get(object_key)
        if m is None:
            result["error"] = "missing_in_materialized_manifest"
            blockers.append(f"missing_manifest_record:{candidate_id}:{object_key}")
            records.append(result)
            continue

        if not local_path.exists():
            result["error"] = "local_object_missing"
            blockers.append(f"local_missing:{candidate_id}:{local_path}")
            records.append(result)
            continue

        try:
            actual_size = local_path.stat().st_size
            actual_sha = sha256_file(local_path)
            expected_size = m.get("localSizeBytes")
            expected_sha = m.get("localSha256")

            result["sizeBytes"] = actual_size
            result["sha256"] = actual_sha
            result["sizeVerified"] = actual_size == expected_size
            result["sha256Verified"] = actual_sha == expected_sha

            wav_meta = read_wav(local_path)
            result.update(wav_meta)
            result["audioReadable"] = bool(wav_meta["validPcmWav"])

            if not result["podPathMapped"]:
                blockers.append(f"pod_path_mapping_error:{candidate_id}:{pod_path}")
            if not result["sizeVerified"]:
                blockers.append(f"size_mismatch:{candidate_id}")
            if not result["sha256Verified"]:
                blockers.append(f"sha256_mismatch:{candidate_id}")
            if not result["audioReadable"]:
                blockers.append(f"audio_not_readable:{candidate_id}")
        except Exception as e:
            result["error"] = repr(e)
            blockers.append(f"read_error:{candidate_id}:{repr(e)}")

        records.append(result)

    candidate_count = mount.get("candidateCount", len(records))
    pod_path_mapped_count = sum(1 for r in records if r["podPathMapped"])
    local_exists_count = sum(1 for r in records if r["localExists"])
    audio_readable_count = sum(1 for r in records if r["audioReadable"])
    sha256_verified_count = sum(1 for r in records if r["sha256Verified"])
    size_verified_count = sum(1 for r in records if r["sizeVerified"])

    mode_counts: dict[str, int] = {}
    for r in records:
        mode = r.get("assetTimeMode") or "UNKNOWN"
        mode_counts[mode] = mode_counts.get(mode, 0) + 1

    status = "PASS" if (
        not blockers
        and len(records) == candidate_count
        and pod_path_mapped_count == candidate_count
        and local_exists_count == candidate_count
        and audio_readable_count == candidate_count
        and sha256_verified_count == candidate_count
        and size_verified_count == candidate_count
    ) else "FAIL"

    report = {
        "status": status,
        "scope": "week13_pod_audio_read_simulation_v1",
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "sourceManifest": args.manifest,
        "sourceMountContract": args.mount_contract,
        "candidateCount": candidate_count,
        "recordCount": len(records),
        "podPathMappedCount": pod_path_mapped_count,
        "localExistsCount": local_exists_count,
        "audioReadableCount": audio_readable_count,
        "sha256VerifiedCount": sha256_verified_count,
        "sizeVerifiedCount": size_verified_count,
        "assetTimeModeCounts": mode_counts,
        "blockers": blockers,
        "boundary": [
            "podPath read simulation only",
            "local object store under Docker Desktop/kind development semantics",
            "not S3 or MinIO",
            "not CSI or production persistent volume",
            "validates PCM WAV readability for future worker consumption",
        ],
        "records": records,
    }

    write_json(out_path, report)

    print(json.dumps({
        "report": str(out_path),
        "status": report["status"],
        "candidateCount": candidate_count,
        "podPathMappedCount": pod_path_mapped_count,
        "localExistsCount": local_exists_count,
        "audioReadableCount": audio_readable_count,
        "sha256VerifiedCount": sha256_verified_count,
        "sizeVerifiedCount": size_verified_count,
        "assetTimeModeCounts": mode_counts,
        "blockers": blockers,
    }, ensure_ascii=False, indent=2))

    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
