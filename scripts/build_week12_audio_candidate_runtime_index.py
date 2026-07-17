#!/usr/bin/env python3
"""
Build Week12 Cloud audio candidate runtime index.

Inputs:
- Java HTTP IT summary/body generated from SpringBootTest.RANDOM_PORT.
- Mainbase enriched audio audition review queue.
- Existing Cloud audio audition artifact index when available.

Outputs:
- loadtest/reports/week12_audio_candidate_runtime_index.json
- observability/grafana/dashboards/week12_audio_candidate_dashboard.json

Boundary:
- Cloud consumes Java API evidence and Mainbase artifacts.
- Cloud does not claim production object storage.
- Cloud does not claim human audition passed.
- Cloud does not claim semantic audio quality passed.
- Cloud does not claim final mix readiness.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


ROOT = Path(".").resolve()
JAVA = Path(os.environ.get("JAVA", str(Path.home() / "work" / "grt_work" / "media-task-platform-java"))).resolve()
MAINBASE = Path(os.environ.get("MAINBASE", str(Path.home() / "work" / "grt_work" / "audio_engineering_repo_skeleton_v1"))).resolve()

JAVA_HTTP_SUMMARY = JAVA / "artifacts/runtime/week12_audio_candidate_api_http_it_summary.json"
JAVA_HTTP_BODY = JAVA / "artifacts/runtime/week12_audio_candidate_api_http_it_body.json"
MAINBASE_QUEUE = MAINBASE / "artifacts/evals/week12_audio_audition_review_queue_v0.json"
CLOUD_AUDITION_INDEX = ROOT / "loadtest/reports/week12_audio_audition_artifact_index.json"

OUT_INDEX = ROOT / "loadtest/reports/week12_audio_candidate_runtime_index.json"
OUT_DASHBOARD = ROOT / "observability/grafana/dashboards/week12_audio_candidate_dashboard.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path, required: bool = True) -> Dict[str, Any]:
    if not path.exists():
        if required:
            raise SystemExit(f"ERROR: missing required file: {path}")
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def assert_equal(obj: Dict[str, Any], key: str, expected: Any, source: str) -> None:
    actual = obj.get(key)
    if actual != expected:
        raise SystemExit(f"ERROR: {source}.{key}: expected={expected!r}, actual={actual!r}")


def panel(title: str, grid_y: int, stat_value: Any, description: str) -> Dict[str, Any]:
    return {
        "type": "stat",
        "title": title,
        "description": description,
        "gridPos": {"h": 5, "w": 6, "x": 0, "y": grid_y},
        "fieldConfig": {
            "defaults": {
                "mappings": [],
                "thresholds": {
                    "mode": "absolute",
                    "steps": [
                        {"color": "green", "value": None}
                    ]
                }
            },
            "overrides": []
        },
        "options": {
            "reduceOptions": {
                "values": False,
                "calcs": ["lastNotNull"],
                "fields": ""
            },
            "orientation": "auto",
            "textMode": "auto",
            "colorMode": "value",
            "graphMode": "none",
            "justifyMode": "auto"
        },
        "targets": [],
        "transparent": False,
        "datasource": None,
        "pluginVersion": "local-json-stub",
        "week12StaticValue": stat_value,
    }


def main() -> int:
    java_summary = read_json(JAVA_HTTP_SUMMARY)
    java_body = read_json(JAVA_HTTP_BODY)
    mainbase_queue = read_json(MAINBASE_QUEUE)
    cloud_audition_index = read_json(CLOUD_AUDITION_INDEX, required=False)

    assert_equal(java_summary, "status", "PASS", "java_summary")
    assert_equal(java_summary, "httpCode", 200, "java_summary")
    assert_equal(java_summary, "candidateCount", 10, "java_summary")
    assert_equal(java_summary, "audioProbeOkCount", 10, "java_summary")
    assert_equal(java_summary, "semanticFidelityClaimedAny", False, "java_summary")
    assert_equal(java_summary, "mixReadyClaimedAny", False, "java_summary")

    assert_equal(java_body, "status", "PASS", "java_body")
    assert_equal(java_body, "qualityGateStatus", "HUMAN_AUDITION_REQUIRED", "java_body")
    assert_equal(java_body, "candidateCount", 10, "java_body")
    assert_equal(java_body, "audioProbeOkCount", 10, "java_body")
    assert_equal(java_body, "audioProbeFailedCount", 0, "java_body")
    assert_equal(java_body, "durationMissingCount", 0, "java_body")
    assert_equal(java_body, "sampleRateMissingCount", 0, "java_body")
    assert_equal(java_body, "eventIdMissingCount", 0, "java_body")
    assert_equal(java_body, "semanticFidelityClaimedAny", False, "java_body")
    assert_equal(java_body, "mixReadyClaimedAny", False, "java_body")

    assert_equal(mainbase_queue, "status", "PASS", "mainbase_queue")
    assert_equal(mainbase_queue, "candidateCount", 10, "mainbase_queue")
    assert_equal(mainbase_queue, "audioProbeOkCount", 10, "mainbase_queue")
    assert_equal(mainbase_queue, "semanticFidelityClaimedAny", False, "mainbase_queue")
    assert_equal(mainbase_queue, "mixReadyClaimedAny", False, "mainbase_queue")

    candidates = java_body.get("candidates") or []
    if len(candidates) != 10:
        raise SystemExit(f"ERROR: expected 10 candidates, got {len(candidates)}")

    required_candidate_fields = [
        "candidateId",
        "caseId",
        "eventId",
        "eventLabel",
        "layer",
        "candidateUri",
        "durationSec",
        "sampleRateHz",
        "channels",
        "sampleWidthBytes",
        "rmsDbfs",
        "peakDbfs",
        "formatOk",
        "reviewStatus",
        "failureTags",
    ]
    missing_records: List[Dict[str, Any]] = []
    for c in candidates:
        missing = [k for k in required_candidate_fields if c.get(k) in (None, "")]
        if missing:
            missing_records.append({"candidateId": c.get("candidateId"), "missing": missing})

    blockers: List[str] = []
    if missing_records:
        blockers.append("CANDIDATE_FIELD_MISSING")
    if java_body.get("qualityGateStatus") != "HUMAN_AUDITION_REQUIRED":
        blockers.append("QUALITY_GATE_NOT_HUMAN_AUDITION_REQUIRED")

    layers = {}
    durations = []
    rms_values = []
    peak_values = []
    for c in candidates:
        layer = str(c.get("layer") or "unknown")
        layers[layer] = layers.get(layer, 0) + 1
        if isinstance(c.get("durationSec"), (int, float)):
            durations.append(float(c["durationSec"]))
        if isinstance(c.get("rmsDbfs"), (int, float)):
            rms_values.append(float(c["rmsDbfs"]))
        if isinstance(c.get("peakDbfs"), (int, float)):
            peak_values.append(float(c["peakDbfs"]))

    index = {
        "schemaVersion": "week12.cloud.audio_candidate_runtime_index.v0",
        "generatedAt": utc_now(),
        "status": "PASS" if not blockers else "FAIL",
        "source": "java.week12.audio_candidate_api_http_it",
        "java": {
            "summaryUri": str(JAVA_HTTP_SUMMARY),
            "bodyUri": str(JAVA_HTTP_BODY),
            "endpoint": java_summary.get("endpoint"),
            "verificationMode": java_summary.get("verificationMode"),
            "httpCode": java_summary.get("httpCode"),
        },
        "mainbase": {
            "reviewQueueUri": str(MAINBASE_QUEUE),
            "candidateCount": mainbase_queue.get("candidateCount"),
            "audioProbeOkCount": mainbase_queue.get("audioProbeOkCount"),
        },
        "cloudPreviousIndex": {
            "audioAuditionArtifactIndexUri": str(CLOUD_AUDITION_INDEX) if CLOUD_AUDITION_INDEX.exists() else None,
            "present": CLOUD_AUDITION_INDEX.exists(),
            "status": cloud_audition_index.get("status"),
        },
        "candidateCount": java_body.get("candidateCount"),
        "audioProbeOkCount": java_body.get("audioProbeOkCount"),
        "audioProbeFailedCount": java_body.get("audioProbeFailedCount"),
        "durationMissingCount": java_body.get("durationMissingCount"),
        "sampleRateMissingCount": java_body.get("sampleRateMissingCount"),
        "eventIdMissingCount": java_body.get("eventIdMissingCount"),
        "formatFailedCount": java_body.get("formatFailedCount"),
        "qualityGateStatus": java_body.get("qualityGateStatus"),
        "semanticFidelityClaimedAny": java_body.get("semanticFidelityClaimedAny"),
        "mixReadyClaimedAny": java_body.get("mixReadyClaimedAny"),
        "doesNotClaim": java_body.get("doesNotClaim"),
        "blockers": blockers,
        "missingRecords": missing_records,
        "layerCounts": layers,
        "durationSec": {
            "min": min(durations) if durations else None,
            "max": max(durations) if durations else None,
            "mean": round(sum(durations) / len(durations), 6) if durations else None,
        },
        "rmsDbfs": {
            "min": min(rms_values) if rms_values else None,
            "max": max(rms_values) if rms_values else None,
            "mean": round(sum(rms_values) / len(rms_values), 6) if rms_values else None,
        },
        "peakDbfs": {
            "min": min(peak_values) if peak_values else None,
            "max": max(peak_values) if peak_values else None,
            "mean": round(sum(peak_values) / len(peak_values), 6) if peak_values else None,
        },
        "sampleCandidates": candidates[:3],
        "boundary": [
            "local_cloud_index_only",
            "not_production_object_storage",
            "not_human_audition_passed",
            "not_semantic_audio_quality_passed",
            "not_final_mix_ready",
            "not_real_prometheus_datasource_panel",
        ],
    }

    dashboard = {
        "uid": "week12-audio-candidate",
        "title": "Week12 Audio Candidate Runtime Gate",
        "tags": ["week12", "audio-candidate", "local", "artifact-index"],
        "timezone": "browser",
        "schemaVersion": 39,
        "version": 1,
        "refresh": "",
        "panels": [
            panel("Candidate Count", 0, index["candidateCount"], "Expected 10 candidates from Java API."),
            panel("Audio Probe OK", 5, index["audioProbeOkCount"], "Expected 10 WAV metadata probes passed."),
            panel("Quality Gate", 10, index["qualityGateStatus"], "Should remain HUMAN_AUDITION_REQUIRED."),
            panel("Semantic Claimed", 15, index["semanticFidelityClaimedAny"], "Must remain false."),
            panel("Mix Ready Claimed", 20, index["mixReadyClaimedAny"], "Must remain false."),
            panel("Blocker Count", 25, len(blockers), "Must be zero."),
        ],
        "templating": {"list": []},
        "annotations": {"list": []},
        "time": {"from": "now-6h", "to": "now"},
        "week12StaticSource": str(OUT_INDEX),
        "week12Boundary": index["boundary"],
    }

    OUT_INDEX.parent.mkdir(parents=True, exist_ok=True)
    OUT_INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    OUT_DASHBOARD.parent.mkdir(parents=True, exist_ok=True)
    OUT_DASHBOARD.write_text(json.dumps(dashboard, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": index["status"],
        "candidateCount": index["candidateCount"],
        "audioProbeOkCount": index["audioProbeOkCount"],
        "qualityGateStatus": index["qualityGateStatus"],
        "semanticFidelityClaimedAny": index["semanticFidelityClaimedAny"],
        "mixReadyClaimedAny": index["mixReadyClaimedAny"],
        "blockers": index["blockers"],
        "index": str(OUT_INDEX),
        "dashboard": str(OUT_DASHBOARD),
    }, ensure_ascii=False, indent=2))

    return 0 if index["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())