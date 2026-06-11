#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import wave
from pathlib import Path
from typing import Any


DEFAULT_INPUT = "loadtest/reports/week13_ready_candidate_worker_input_manifest.json"
DEFAULT_RESULT = "loadtest/reports/week13_local_audio_worker_smoke_result.json"
DEFAULT_TABLE = "loadtest/reports/week13_local_audio_worker_smoke_table.csv"
DEFAULT_JOB = "k8s/base/week13-audio-worker-job-template.yaml"
DEFAULT_OBJECT_ROOT = "artifacts/local-object-store"


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


def read_wav_meta(path: Path) -> dict[str, Any]:
    with wave.open(str(path), "rb") as w:
        channels = w.getnchannels()
        sample_width = w.getsampwidth()
        sample_rate = w.getframerate()
        frames = w.getnframes()
        comp_type = w.getcomptype()
        duration = frames / sample_rate if sample_rate else 0.0
        preview = w.readframes(min(frames, 1024))
    return {
        "channels": channels,
        "sampleWidthBytes": sample_width,
        "sampleRateHz": sample_rate,
        "frames": frames,
        "durationSecActual": round(duration, 6),
        "compressionType": comp_type,
        "previewBytesRead": len(preview),
        "validPcmWav": comp_type == "NONE" and channels > 0 and sample_width > 0 and sample_rate > 0 and frames > 0,
    }


def local_path_from_record(record: dict[str, Any], object_root: Path) -> Path:
    object_key = record.get("objectKey")
    if isinstance(object_key, str) and object_key:
        return object_root / object_key

    pod_path = record.get("podPath")
    if isinstance(pod_path, str) and "/mnt/audio-candidates/" in pod_path:
        suffix = pod_path.split("/mnt/audio-candidates/", 1)[1]
        return object_root / "audio-candidates" / suffix

    raise ValueError(f"cannot map record to local path: {record.get('candidateId')}")


def build_job_template(path: Path, object_root_abs: Path, manifest_abs: Path) -> None:
    content = f"""apiVersion: batch/v1
kind: Job
metadata:
  name: week13-audio-worker-smoke
  labels:
    app.kubernetes.io/name: week13-audio-worker-smoke
    app.kubernetes.io/part-of: ai-job-platform-cloud
    week: "13"
spec:
  completions: 1
  parallelism: 1
  backoffLimit: 1
  template:
    metadata:
      labels:
        app.kubernetes.io/name: week13-audio-worker-smoke
    spec:
      restartPolicy: Never
      containers:
        - name: worker-smoke
          image: python:3.11-slim
          command: ["python", "-c"]
          args:
            - |
              import json, pathlib, wave
              manifest = pathlib.Path("/workspace/loadtest/reports/week13_ready_candidate_worker_input_manifest.json")
              data = json.loads(manifest.read_text())
              assert data["status"] == "PASS"
              assert data["candidateCount"] == 10
              print("week13 worker input manifest is readable from pod contract")
          volumeMounts:
            - name: audio-candidates
              mountPath: /mnt/audio-candidates
              readOnly: true
            - name: workspace
              mountPath: /workspace
              readOnly: true
      volumes:
        - name: audio-candidates
          hostPath:
            path: {object_root_abs / "audio-candidates"}
            type: Directory
        - name: workspace
          hostPath:
            path: {manifest_abs.parent.parent.parent}
            type: Directory
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=DEFAULT_INPUT)
    ap.add_argument("--result", default=DEFAULT_RESULT)
    ap.add_argument("--table", default=DEFAULT_TABLE)
    ap.add_argument("--job-template", default=DEFAULT_JOB)
    ap.add_argument("--object-root", default=DEFAULT_OBJECT_ROOT)
    args = ap.parse_args()

    root = Path.cwd().resolve()
    input_path = root / args.input
    result_path = root / args.result
    table_path = root / args.table
    job_path = root / args.job_template
    object_root = (root / args.object_root).resolve()

    manifest = load_json(input_path)
    blockers: list[str] = []

    if manifest.get("status") != "PASS":
        blockers.append(f"worker_input_status={manifest.get('status')}")

    rows = []
    records = manifest.get("records", [])
    for idx, r in enumerate(records):
        cid = r.get("candidateId")
        mode = r.get("assetTimeMode")
        declared_duration = float(r.get("durationSec") or 0)
        timeline_start = float(r.get("timelineStartSec") or 0)
        timeline_end = float(r.get("timelineEndSec") or 0)
        declared_sha = r.get("sha256")
        declared_size = int(r.get("sizeBytes") or 0)

        result = {
            "workerIndex": idx,
            "candidateId": cid,
            "workerStatus": "FAIL",
            "assetTimeMode": mode,
            "placementPolicy": r.get("placementPolicy"),
            "podPath": r.get("podPath"),
            "timelineStartSec": timeline_start,
            "timelineEndSec": timeline_end,
            "durationSecDeclared": declared_duration,
            "localPath": None,
            "localExists": False,
            "sizeVerified": False,
            "sha256Verified": False,
            "durationVerified": False,
            "audioReadable": False,
            "error": None,
        }

        try:
            local_path = local_path_from_record(r, object_root).resolve()
            result["localPath"] = str(local_path)
            result["localExists"] = local_path.exists()

            if not local_path.exists():
                raise FileNotFoundError(str(local_path))

            actual_size = local_path.stat().st_size
            actual_sha = sha256_file(local_path)
            wav_meta = read_wav_meta(local_path)

            result.update(wav_meta)
            result["sizeBytesActual"] = actual_size
            result["sha256Actual"] = actual_sha
            result["sizeVerified"] = actual_size == declared_size
            result["sha256Verified"] = actual_sha == declared_sha
            result["audioReadable"] = bool(wav_meta["validPcmWav"])
            result["durationVerified"] = abs(float(wav_meta["durationSecActual"]) - declared_duration) <= 0.02

            if mode == "full_clip" and timeline_start != 0.0:
                blockers.append(f"full_clip_not_at_zero:{cid}:{timeline_start}")
            if mode == "event_local" and timeline_start <= 0.0:
                blockers.append(f"event_local_not_offset:{cid}:{timeline_start}")
            if abs((timeline_end - timeline_start) - declared_duration) > 0.02:
                blockers.append(f"timeline_duration_mismatch:{cid}")

            ok = (
                result["localExists"]
                and result["sizeVerified"]
                and result["sha256Verified"]
                and result["audioReadable"]
                and result["durationVerified"]
            )
            result["workerStatus"] = "SUCCESS" if ok else "FAIL"
            if not ok:
                blockers.append(f"worker_candidate_failed:{cid}")

        except Exception as e:
            result["error"] = repr(e)
            blockers.append(f"worker_exception:{cid}:{repr(e)}")

        rows.append(result)

    success_count = sum(1 for r in rows if r["workerStatus"] == "SUCCESS")

    mode_counts: dict[str, int] = {}
    for r in rows:
        mode = r.get("assetTimeMode") or "UNKNOWN"
        mode_counts[mode] = mode_counts.get(mode, 0) + 1

    status = "PASS" if (
        len(rows) == 10
        and success_count == 10
        and mode_counts == {"full_clip": 5, "event_local": 5}
        and not blockers
    ) else "FAIL"

    build_job_template(
        job_path,
        object_root_abs=object_root,
        manifest_abs=input_path.resolve(),
    )

    result_doc = {
        "status": status,
        "scope": "week13_local_audio_worker_smoke_v1",
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "sourceWorkerInput": str(input_path),
        "k8sJobTemplate": str(job_path),
        "candidateCount": len(rows),
        "workerSuccessCount": success_count,
        "assetTimeModeCounts": mode_counts,
        "blockers": blockers,
        "boundary": [
            "local worker smoke consumes worker input manifest",
            "opens materialized wav files and verifies size, sha256, duration and placement policy",
            "generates Kubernetes Job template only",
            "does not apply the Job to a cluster",
            "does not claim semantic audio quality or final mix readiness",
        ],
        "records": rows,
    }

    write_json(result_path, result_doc)

    table_path.parent.mkdir(parents=True, exist_ok=True)
    with table_path.open("w", encoding="utf-8", newline="") as f:
        fields = [
            "workerIndex", "candidateId", "workerStatus", "assetTimeMode",
            "placementPolicy", "timelineStartSec", "timelineEndSec",
            "durationSecDeclared", "durationSecActual",
            "sampleRateHz", "channels", "sizeVerified",
            "sha256Verified", "durationVerified", "audioReadable", "podPath",
        ]
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in fields})

    print(json.dumps({
        "result": str(result_path),
        "table": str(table_path),
        "jobTemplate": str(job_path),
        "status": status,
        "candidateCount": len(rows),
        "workerSuccessCount": success_count,
        "assetTimeModeCounts": mode_counts,
        "blockers": blockers,
    }, ensure_ascii=False, indent=2))

    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
