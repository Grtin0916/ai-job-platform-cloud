#!/usr/bin/env python3
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing required json: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"json root must be object: {path}")
    return data


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def metric(data: dict[str, Any], key: str) -> Any:
    metrics = data.get("metrics")
    require(isinstance(metrics, dict), "metrics must be object")
    require(key in metrics, f"missing metric: {key}")
    return metrics[key]


def main() -> int:
    root = Path.cwd()

    score_index_path = root / "loadtest/reports/week15_temporal_alignment_score_summary_platform_index.json"
    visual_index_path = root / "loadtest/reports/week15_temporal_alignment_visual_evidence_platform_index.json"

    score_index = load_json(score_index_path)
    visual_index = load_json(visual_index_path)

    require(score_index.get("status") == "PASS", "score summary platform index must PASS")
    require(visual_index.get("status") == "PASS", "visual evidence platform index must PASS")

    score_metrics = score_index.get("metrics", {})
    visual_metrics = visual_index.get("metrics", {})
    interpretation = visual_index.get("interpretation", {})

    require(score_metrics.get("candidate_total") == 10, "candidate_total must be 10")
    require(score_metrics.get("original_fail_total") == 2, "original_fail_total must be 2")
    require(score_metrics.get("remediated_fail_total") == 0, "remediated_fail_total must be 0")
    require(score_metrics.get("event_local_pass_delta") == 2, "event_local_pass_delta must be 2")

    require(visual_metrics.get("visual_evidence_candidate_total") == 2, "visual evidence candidate count must be 2")
    require(visual_metrics.get("visual_evidence_figure_total") == 2, "visual evidence figure count must be 2")
    require(float(visual_metrics.get("duration_trim_total_sec", 0.0)) > 0.0, "duration trim must be positive")
    require(float(visual_metrics.get("onset_proxy_abs_delta_total_sec", -1.0)) == 0.0, "onset proxy abs delta must be 0.0")

    caveat = interpretation.get("importantCaveat", "")
    require("do not describe this as onset-proxy shift evidence" in caveat, "missing onset-shift overclaim caveat")

    visual_records = visual_index.get("visualEvidence")
    require(isinstance(visual_records, list), "visualEvidence must be array")
    require(len(visual_records) == 2, "visualEvidence must contain 2 records")

    expected_ids = {"procedural_v0_0004", "procedural_v0_0010"}
    observed_ids = {item.get("candidateId") for item in visual_records if isinstance(item, dict)}
    require(observed_ids == expected_ids, f"unexpected visual evidence ids: {observed_ids}")

    for item in visual_records:
        cid = item["candidateId"]
        require(float(item["durationTrimSec"]) > 0.0, f"{cid} durationTrimSec must be positive")
        require(float(item["onsetProxyDeltaSec"]) == 0.0, f"{cid} onsetProxyDeltaSec must be 0.0")
        require(
            "duration trimming while preserving the local RMS onset proxy" in item.get("interpretation", ""),
            f"{cid} interpretation must use the conservative duration-trimming claim",
        )

    report = {
        "schemaVersion": "week15.temporal_alignment_evidence_gate.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "gateDecision": "TEMPORAL_ALIGNMENT_EVIDENCE_GATE_PASS",
        "inputs": {
            "scoreSummaryPlatformIndex": str(score_index_path),
            "visualEvidencePlatformIndex": str(visual_index_path),
        },
        "sourceHeads": {
            "mainbaseWaveformRmsCommitHead": visual_index.get("sourceHeads", {}).get("mainbaseWaveformRmsCommitHead"),
            "javaScoreSummaryCommitHead": visual_index.get("sourceHeads", {}).get("javaScoreSummaryCommitHead"),
            "cloudScoreSummaryCommitHead": visual_index.get("sourceHeads", {}).get("cloudScoreSummaryCommitHead"),
            "cloudVisualEvidenceCommitHead": "b5e84ea",
        },
        "allowedClaim": "Remediation for procedural_v0_0004 and procedural_v0_0010 is supported by duration-trimming evidence while preserving the local RMS onset proxy.",
        "blockedClaims": [
            "Do not claim semantic audio quality is solved.",
            "Do not claim human audition passed.",
            "Do not claim final mix readiness.",
            "Do not claim live Grafana import.",
            "Do not claim production SLO.",
            "Do not describe the current evidence as onset-proxy shift evidence.",
        ],
        "scoreMetrics": score_metrics,
        "visualMetrics": visual_metrics,
        "visualEvidenceIds": sorted(observed_ids),
        "nextAction": "Use the two waveform/RMS PNGs for manual visual inspection; after that, add human-audition or semantic-quality checks only if explicitly performed.",
        "boundary": [
            "offline_evidence_gate_only",
            "consumes_cloud_score_summary_and_visual_evidence_indexes",
            "does_not_call_live_java_service",
            "does_not_import_live_grafana_dashboard",
            "does_not_claim_production_slo",
        ],
    }

    out_report = root / "loadtest/reports/week15_temporal_alignment_evidence_gate.json"
    out_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    metrics_text = f"""# HELP week15_temporal_alignment_evidence_gate_ready Temporal alignment evidence gate pass status.
# TYPE week15_temporal_alignment_evidence_gate_ready gauge
week15_temporal_alignment_evidence_gate_ready{{status="PASS"}} 1
# HELP week15_temporal_alignment_evidence_gate_duration_trim_total_sec Duration trim total accepted by evidence gate.
# TYPE week15_temporal_alignment_evidence_gate_duration_trim_total_sec gauge
week15_temporal_alignment_evidence_gate_duration_trim_total_sec {visual_metrics.get("duration_trim_total_sec")}
# HELP week15_temporal_alignment_evidence_gate_onset_proxy_abs_delta_total_sec Onset proxy absolute delta total accepted by evidence gate.
# TYPE week15_temporal_alignment_evidence_gate_onset_proxy_abs_delta_total_sec gauge
week15_temporal_alignment_evidence_gate_onset_proxy_abs_delta_total_sec {visual_metrics.get("onset_proxy_abs_delta_total_sec")}
# HELP week15_temporal_alignment_evidence_gate_blocked_overclaim_total Number of blocked overclaim categories in evidence gate.
# TYPE week15_temporal_alignment_evidence_gate_blocked_overclaim_total gauge
week15_temporal_alignment_evidence_gate_blocked_overclaim_total {len(report["blockedClaims"])}
"""
    out_metrics = root / "observability/prometheus/week15_temporal_alignment_evidence_gate_metrics.prom"
    out_metrics.write_text(metrics_text, encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"WROTE_REPORT={out_report}")
    print(f"WROTE_METRICS={out_metrics}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
