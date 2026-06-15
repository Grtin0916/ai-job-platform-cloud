#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing required json: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"json root must be object: {path}")
    return data


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def as_int(obj: dict[str, Any], key: str) -> int:
    value = obj.get(key)
    if not isinstance(value, int):
        raise AssertionError(f"{key} must be int, got {value!r}")
    return value


def main() -> int:
    cloud_root = Path.cwd()

    java_repo = Path(
        os.environ.get(
            "JAVA_REPO",
            str(Path.home() / "work" / "media-task-platform-java"),
        )
    )

    java_report_path = java_repo / "artifacts/manifests/week15_java_temporal_alignment_score_summary_contract_report.json"
    cloud_dashboard_ready_path = cloud_root / "loadtest/reports/week15_temporal_alignment_dashboard_ready.json"
    cloud_platform_gate_path = cloud_root / "loadtest/reports/week15_temporal_alignment_platform_gate.json"

    java_report = load_json(java_report_path)
    if cloud_dashboard_ready_path.exists():
        cloud_dashboard_ready = load_json(cloud_dashboard_ready_path)
        dashboard_ready_missing = False
    else:
        cloud_dashboard_ready = {
            "status": "MISSING_OPTIONAL_INPUT",
            "missingPath": str(cloud_dashboard_ready_path),
            "note": "dashboard-ready report is absent in this local checkout; score summary platform index falls back to platform gate and Java contract report."
        }
        dashboard_ready_missing = True

    cloud_platform_gate = load_json(cloud_platform_gate_path)

    require(java_report.get("status") == "PASS", "java score summary contract must PASS")
    require(
        java_report.get("gateDecision") == "TEMPORAL_ALIGNMENT_DASHBOARD_READY_AND_REGRESSION_GUARDED",
        "unexpected java gateDecision",
    )

    score = java_report.get("scoreSummary")
    delta = java_report.get("remediationDelta")
    drifts = java_report.get("candidateDrifts")
    artifact_links = java_report.get("artifactLinks")
    source = java_report.get("source")
    boundary = java_report.get("boundary")

    require(isinstance(score, dict), "scoreSummary must be object")
    require(isinstance(delta, dict), "remediationDelta must be object")
    require(isinstance(drifts, list), "candidateDrifts must be array")
    require(isinstance(artifact_links, dict), "artifactLinks must be object")
    require(isinstance(source, dict), "source must be object")
    require(isinstance(boundary, list), "boundary must be array")

    candidate_count = as_int(score, "candidateCount")
    original_fail_count = as_int(score, "originalFailCount")
    remediated_fail_count = as_int(score, "remediatedFailCount")
    original_event_local_pass_count = as_int(score, "originalEventLocalPassCount")
    remediated_event_local_pass_count = as_int(score, "remediatedEventLocalPassCount")
    event_local_pass_delta = as_int(delta, "eventLocalPassDelta")
    fail_count_delta = as_int(delta, "failCountDelta")

    require(candidate_count == 10, "candidateCount must stay 10 for week15 contract")
    require(original_fail_count == 2, "originalFailCount must be 2")
    require(remediated_fail_count == 0, "remediatedFailCount must be 0")
    require(event_local_pass_delta == 2, "eventLocalPassDelta must be 2")
    require(fail_count_delta == -2, "failCountDelta must be -2")

    remediated_ids = delta.get("remediatedCandidateIds")
    require(isinstance(remediated_ids, list), "remediatedCandidateIds must be array")
    require("procedural_v0_0004" in remediated_ids, "missing procedural_v0_0004")
    require("procedural_v0_0010" in remediated_ids, "missing procedural_v0_0010")

    drift_ids = sorted(
        item.get("candidateId")
        for item in drifts
        if isinstance(item, dict) and item.get("originalStatus") == "FAIL_DRIFT"
    )
    require(drift_ids == ["procedural_v0_0004", "procedural_v0_0010"], f"unexpected drift ids: {drift_ids}")

    # 不强行猜测 Cloud 旧文件 schema，只做轻量状态抽取，避免把旧 schema 绑死。
    cloud_dashboard_status = cloud_dashboard_ready.get("status", cloud_dashboard_ready.get("decision", "UNKNOWN"))
    cloud_platform_gate_status = cloud_platform_gate.get("status", cloud_platform_gate.get("decision", "UNKNOWN"))

    platform_decision = (
        "PASS"
        if remediated_fail_count == 0
        and event_local_pass_delta == 2
        and set(remediated_ids) == {"procedural_v0_0004", "procedural_v0_0010"}
        else "FAIL"
    )

    generated_at = datetime.now(timezone.utc).isoformat()

    index = {
        "schemaVersion": "week15.temporal_alignment_score_summary_platform_index.v1",
        "generatedAt": generated_at,
        "status": platform_decision,
        "platformDecision": "SCORE_SUMMARY_CONSUMED_BY_CLOUD_PLATFORM_INDEX",
        "inputs": {
            "javaScoreSummaryContractReport": str(java_report_path),
            "cloudDashboardReadyReport": str(cloud_dashboard_ready_path),
            "cloudPlatformGateReport": str(cloud_platform_gate_path),
        },
        "sourceHeads": {
            "mainbaseInputHead": source.get("mainbaseHead"),
            "javaInputHead": source.get("javaInputHead"),
            "javaScoreSummaryCommitHead": "466e30b",
            "cloudInputHead": source.get("cloudHead"),
        },
        "scoreSummary": score,
        "remediationDelta": delta,
        "candidateDrifts": drifts,
        "artifactLinks": artifact_links,
        "cloudEvidence": {
            "dashboardReadyStatus": cloud_dashboard_status,
            "dashboardReadyMissing": dashboard_ready_missing,
            "platformGateStatus": cloud_platform_gate_status,
            "dashboardJson": artifact_links.get("cloudDashboard"),
            "cloudReadyReport": artifact_links.get("cloudReadyReport"),
        },
        "metrics": {
            "candidate_total": candidate_count,
            "original_fail_total": original_fail_count,
            "remediated_fail_total": remediated_fail_count,
            "original_event_local_pass_total": original_event_local_pass_count,
            "remediated_event_local_pass_total": remediated_event_local_pass_count,
            "event_local_pass_delta": event_local_pass_delta,
            "fail_count_delta": fail_count_delta,
            "remediated_candidate_total": len(remediated_ids),
        },
        "routingHints": {
            "dashboardPanel": "Temporal Alignment Remediation",
            "alertClass": "alignment_debt",
            "humanReviewQueue": remediated_ids,
            "nextAction": "inspect waveform/RMS PNG for remediated candidates before claiming human-audition or final-mix readiness",
        },
        "boundary": boundary + [
            "cloud_index_only",
            "does_not_call_live_java_service",
            "does_not_import_live_grafana_dashboard",
            "dashboard_ready_report_optional_for_score_summary_index",
        ],
    }

    metrics = f"""# HELP week15_temporal_alignment_candidates_total Candidate count in Week15 temporal alignment score summary.
# TYPE week15_temporal_alignment_candidates_total gauge
week15_temporal_alignment_candidates_total {candidate_count}
# HELP week15_temporal_alignment_original_fail_total Original temporal alignment fail count.
# TYPE week15_temporal_alignment_original_fail_total gauge
week15_temporal_alignment_original_fail_total {original_fail_count}
# HELP week15_temporal_alignment_remediated_fail_total Remediated temporal alignment fail count.
# TYPE week15_temporal_alignment_remediated_fail_total gauge
week15_temporal_alignment_remediated_fail_total {remediated_fail_count}
# HELP week15_temporal_alignment_event_local_pass_delta Event-local pass count improvement after remediation.
# TYPE week15_temporal_alignment_event_local_pass_delta gauge
week15_temporal_alignment_event_local_pass_delta {event_local_pass_delta}
# HELP week15_temporal_alignment_remediated_candidate_total Count of candidates remediated by drift trimming.
# TYPE week15_temporal_alignment_remediated_candidate_total gauge
week15_temporal_alignment_remediated_candidate_total {len(remediated_ids)}
# HELP week15_temporal_alignment_score_summary_platform_index_ready Cloud consumed Java score summary contract successfully.
# TYPE week15_temporal_alignment_score_summary_platform_index_ready gauge
week15_temporal_alignment_score_summary_platform_index_ready{{status="{platform_decision}"}} {1 if platform_decision == "PASS" else 0}
"""

    output_index = cloud_root / "loadtest/reports/week15_temporal_alignment_score_summary_platform_index.json"
    output_metrics = cloud_root / "observability/prometheus/week15_temporal_alignment_score_summary_metrics.prom"

    write_json(output_index, index)
    write_text(output_metrics, metrics)

    print(json.dumps(index, ensure_ascii=False, indent=2))
    print(f"WROTE_INDEX={output_index}")
    print(f"WROTE_METRICS={output_metrics}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
