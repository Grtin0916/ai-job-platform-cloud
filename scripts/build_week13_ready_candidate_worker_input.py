#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
from pathlib import Path
from typing import Any


DEFAULT_MAINBASE = os.environ.get(
    "MAINBASE",
    str(Path.home() / "work/audio_engineering_repo_skeleton_v1"),
)
DEFAULT_JAVA = os.environ.get(
    "JAVA_REPO",
    str(Path.home() / "work/media-task-platform-java"),
)

DEFAULT_FEEDBACK = "artifacts/manifests/week13_cloud_materialization_feedback_index.json"
DEFAULT_POD_READ = "loadtest/reports/week13_pod_audio_read_simulation_report.json"
DEFAULT_JAVA_API = "artifacts/manifests/week13_materialized_readiness_api_contract_report.json"

DEFAULT_OUT_JSON = "loadtest/reports/week13_ready_candidate_worker_input_manifest.json"
DEFAULT_OUT_CSV = "loadtest/reports/week13_ready_candidate_worker_input_table.csv"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def iter_dicts(x: Any):
    if isinstance(x, dict):
        yield x
        for v in x.values():
            yield from iter_dicts(v)
    elif isinstance(x, list):
        for v in x:
            yield from iter_dicts(v)


def candidate_id(d: dict[str, Any]) -> str | None:
    for k in ["candidateId", "candidate_id", "id"]:
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def extract_records(obj: Any) -> dict[str, dict[str, Any]]:
    out = {}
    for d in iter_dicts(obj):
        cid = candidate_id(d)
        if not cid:
            continue
        if any(k in d for k in [
            "feedbackStatus", "podPath", "assetTimeMode", "durationSec",
            "audioReadable", "sampleRateHz", "materializedStorageStatus"
        ]):
            out[cid] = dict(d)
    return out


def pick(d: dict[str, Any] | None, keys: list[str], default=None):
    if not d:
        return default
    for k in keys:
        if k in d:
            return d.get(k)
    return default


def as_float(v: Any, default: float = 0.0) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mainbase-root", default=DEFAULT_MAINBASE)
    ap.add_argument("--java-root", default=DEFAULT_JAVA)
    ap.add_argument("--feedback", default=DEFAULT_FEEDBACK)
    ap.add_argument("--pod-read", default=DEFAULT_POD_READ)
    ap.add_argument("--java-api", default=DEFAULT_JAVA_API)
    ap.add_argument("--out-json", default=DEFAULT_OUT_JSON)
    ap.add_argument("--out-csv", default=DEFAULT_OUT_CSV)
    args = ap.parse_args()

    cloud_root = Path.cwd().resolve()
    mainbase_root = Path(args.mainbase_root).expanduser().resolve()
    java_root = Path(args.java_root).expanduser().resolve()

    feedback = load_json(mainbase_root / args.feedback)
    pod_read = load_json(cloud_root / args.pod_read)
    java_api = load_json(java_root / args.java_api)

    blockers: list[str] = []

    for name, obj in [
        ("mainbase_feedback", feedback),
        ("cloud_pod_read", pod_read),
        ("java_api_contract", java_api),
    ]:
        if isinstance(obj, dict) and obj.get("status") != "PASS":
            blockers.append(f"{name}_status={obj.get('status')}")

    feedback_records = extract_records(feedback)
    pod_records = extract_records(pod_read)

    feedback_ids = set(feedback_records)
    pod_ids = set(pod_records)

    missing_in_pod_read = sorted(feedback_ids - pod_ids)
    missing_in_feedback = sorted(pod_ids - feedback_ids)

    if missing_in_pod_read:
        blockers.append(f"missing_in_cloud_pod_read={missing_in_pod_read}")
    if missing_in_feedback:
        blockers.append(f"missing_in_mainbase_feedback={missing_in_feedback}")

    rows = []
    for cid in sorted(feedback_ids):
        fr = feedback_records[cid]
        pr = pod_records.get(cid)

        mode = pick(fr, ["assetTimeMode"], pick(pr, ["assetTimeMode"]))
        duration = as_float(pick(fr, ["durationSec"], pick(pr, ["durationSec"])))
        expected_start = as_float(pick(fr, ["expectedStartSec"], pick(pr, ["expectedStartSec"])))

        if mode == "full_clip":
            timeline_start = 0.0
            placement_policy = "PLACE_AT_GLOBAL_ZERO"
        elif mode == "event_local":
            timeline_start = expected_start
            placement_policy = "PLACE_AT_EXPECTED_START_SEC"
        else:
            timeline_start = expected_start
            placement_policy = "UNKNOWN_TIME_MODE"

        timeline_end = round(timeline_start + duration, 6)

        ready = (
            pick(fr, ["feedbackStatus"]) == "READY_FOR_PLATFORM_CONSUMPTION"
            and pick(fr, ["cloudAudioReadable"]) is True
            and pick(fr, ["javaMaterializedStorageStatus"]) == "READY"
            and pick(pr, ["audioReadable"]) is True
            and pick(pr, ["sha256Verified"]) is True
            and pick(pr, ["sizeVerified"]) is True
            and pick(pr, ["podPathMapped"]) is True
        )

        if not ready:
            blockers.append(f"worker_input_not_ready:{cid}")
        if mode == "event_local" and timeline_start <= 0:
            blockers.append(f"event_local_start_not_positive:{cid}:{timeline_start}")
        if duration <= 0:
            blockers.append(f"non_positive_duration:{cid}:{duration}")

        rows.append({
            "candidateId": cid,
            "workerReadiness": "READY" if ready else "NOT_READY",
            "assetTimeMode": mode,
            "placementPolicy": placement_policy,
            "timelineStartSec": round(timeline_start, 6),
            "timelineEndSec": timeline_end,
            "durationSec": duration,
            "podPath": pick(fr, ["podPath"], pick(pr, ["podPath"])),
            "objectKey": pick(fr, ["objectKey"], pick(pr, ["objectKey"])),
            "sampleRateHz": pick(fr, ["sampleRateHz"], pick(pr, ["sampleRateHz"])),
            "channels": pick(fr, ["channels"], pick(pr, ["channels"])),
            "sizeBytes": pick(fr, ["sizeBytes"], pick(pr, ["sizeBytes"])),
            "sha256": pick(fr, ["sha256"], pick(pr, ["sha256"])),
            "sourceType": pick(fr, ["sourceType"]),
            "javaMaterializedStorageStatus": pick(fr, ["javaMaterializedStorageStatus"]),
            "cloudAudioReadable": pick(fr, ["cloudAudioReadable"], pick(pr, ["audioReadable"])),
        })

    ready_count = sum(1 for r in rows if r["workerReadiness"] == "READY")

    mode_counts: dict[str, int] = {}
    for r in rows:
        mode = r.get("assetTimeMode") or "UNKNOWN"
        mode_counts[mode] = mode_counts.get(mode, 0) + 1

    status = "PASS" if (
        len(rows) == 10
        and ready_count == 10
        and mode_counts == {"full_clip": 5, "event_local": 5}
        and not blockers
    ) else "FAIL"

    manifest = {
        "status": status,
        "scope": "week13_ready_candidate_worker_input_manifest_v1",
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "candidateCount": len(rows),
        "workerReadyCount": ready_count,
        "assetTimeModeCounts": mode_counts,
        "javaApiEndpoint": java_api.get("endpoint"),
        "sourceFiles": {
            "mainbaseFeedback": str(mainbase_root / args.feedback),
            "cloudPodRead": str(cloud_root / args.pod_read),
            "javaApiContract": str(java_root / args.java_api),
        },
        "blockers": blockers,
        "boundary": [
            "worker input contract only",
            "does not start a Kubernetes Job yet",
            "does not claim semantic audio quality",
            "does not claim final mix readiness",
            "normalizes ready candidates for later worker/orchestration consumption",
        ],
        "records": rows,
    }

    out_json = cloud_root / args.out_json
    out_csv = cloud_root / args.out_csv
    write_json(out_json, manifest)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "candidateId",
            "workerReadiness",
            "assetTimeMode",
            "placementPolicy",
            "timelineStartSec",
            "timelineEndSec",
            "durationSec",
            "podPath",
            "sampleRateHz",
            "channels",
            "sizeBytes",
            "sourceType",
        ])
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k) for k in writer.fieldnames})

    print(json.dumps({
        "manifest": str(out_json),
        "table": str(out_csv),
        "status": status,
        "candidateCount": len(rows),
        "workerReadyCount": ready_count,
        "assetTimeModeCounts": mode_counts,
        "javaApiEndpoint": java_api.get("endpoint"),
        "blockers": blockers,
    }, ensure_ascii=False, indent=2))

    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
