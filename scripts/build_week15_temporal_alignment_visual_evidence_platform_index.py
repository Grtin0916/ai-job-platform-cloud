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
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"json root must be object: {path}")
    return data


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def as_float(value: Any, field: str) -> float:
    if not isinstance(value, (int, float)):
        raise AssertionError(f"{field} must be numeric, got {value!r}")
    return float(value)


def main() -> int:
    cloud_root = Path.cwd()
    mainbase_repo = Path(
        os.environ.get(
            "MAINBASE_REPO",
            str(Path.home() / "work" / "grt_work" / "audio_engineering_repo_skeleton_v1"),
        )
    )

    waveform_index_path = mainbase_repo / "artifacts/evals/week15_temporal_alignment_waveform_rms_index.json"
    score_platform_index_path = cloud_root / "loadtest/reports/week15_temporal_alignment_score_summary_platform_index.json"

    waveform_index = load_json(waveform_index_path)
    score_platform_index = load_json(score_platform_index_path)

    require(waveform_index.get("status") == "PASS", "mainbase waveform/RMS index must PASS")
    require(score_platform_index.get("status") == "PASS", "cloud score summary platform index must PASS")

    candidates = waveform_index.get("candidates")
    require(isinstance(candidates, list), "waveform candidates must be array")
    require(len(candidates) == 2, f"expected 2 waveform candidates, got {len(candidates)}")

    expected_ids = {"procedural_v0_0004", "procedural_v0_0010"}
    observed_ids = {item.get("candidateId") for item in candidates if isinstance(item, dict)}
    require(observed_ids == expected_ids, f"unexpected waveform candidate ids: {observed_ids}")

    visual_records = []
    total_trim_sec = 0.0
    onset_shift_abs_total = 0.0

    for item in candidates:
        cid = item["candidateId"]
        fig = mainbase_repo / item["figure"]
        original = mainbase_repo / item["originalAudio"]
        remediated = mainbase_repo / item["remediatedAudio"]

        require(fig.exists(), f"missing figure for {cid}: {fig}")
        require(fig.stat().st_size > 0, f"empty figure for {cid}: {fig}")
        require(original.exists(), f"missing original audio for {cid}: {original}")
        require(remediated.exists(), f"missing remediated audio for {cid}: {remediated}")

        duration_delta = as_float(item.get("durationDeltaSec"), f"{cid}.durationDeltaSec")
        onset_delta = as_float(item.get("onsetProxyDeltaSec"), f"{cid}.onsetProxyDeltaSec")

        trim_sec = max(0.0, -duration_delta)
        total_trim_sec += trim_sec
        onset_shift_abs_total += abs(onset_delta)

        visual_records.append(
            {
                "candidateId": cid,
                "figure": item["figure"],
                "originalAudio": item["originalAudio"],
                "remediatedAudio": item["remediatedAudio"],
                "originalDurationSec": item["originalDurationSec"],
                "remediatedDurationSec": item["remediatedDurationSec"],
                "durationTrimSec": round(trim_sec, 6),
                "originalOnsetProxySec": item["originalOnsetProxySec"],
                "remediatedOnsetProxySec": item["remediatedOnsetProxySec"],
                "onsetProxyDeltaSec": item["onsetProxyDeltaSec"],
                "interpretation": (
                    "remediation evidence primarily shows duration trimming while preserving the local RMS onset proxy"
                    if abs(onset_delta) < 1e-6 and trim_sec > 0
                    else "remediation evidence shows waveform/RMS difference; inspect manually before stronger claims"
                ),
            }
        )

    index = {
        "schemaVersion": "week15.temporal_alignment_visual_evidence_platform_index.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "platformDecision": "WAVEFORM_RMS_EVIDENCE_CONSUMED_BY_CLOUD_PLATFORM_INDEX",
        "inputs": {
            "mainbaseWaveformRmsIndex": str(waveform_index_path),
            "cloudScoreSummaryPlatformIndex": str(score_platform_index_path),
        },
        "sourceHeads": {
            "mainbaseWaveformRmsCommitHead": "3a5b12a",
            "cloudScoreSummaryCommitHead": "f24ae4a",
            "javaScoreSummaryCommitHead": score_platform_index.get("sourceHeads", {}).get("javaScoreSummaryCommitHead"),
        },
        "visualEvidence": visual_records,
        "metrics": {
            "visual_evidence_candidate_total": len(visual_records),
            "visual_evidence_figure_total": len(visual_records),
            "duration_trim_total_sec": round(total_trim_sec, 6),
            "duration_trim_mean_sec": round(total_trim_sec / len(visual_records), 6),
            "onset_proxy_abs_delta_total_sec": round(onset_shift_abs_total, 6),
        },
        "interpretation": {
            "primaryFinding": "0004/0010 remediation is supported by waveform/RMS figures and duration trimming evidence.",
            "importantCaveat": "The local RMS onset proxy is unchanged in the current index; do not describe this as onset-proxy shift evidence.",
            "nextAction": "manual audition or semantic-quality evaluation is still required before claiming human-audition pass or final mix readiness.",
        },
        "boundary": [
            "cloud_visual_evidence_index_only",
            "consumes_mainbase_waveform_rms_evidence",
            "does_not_score_semantic_audio_quality",
            "does_not_claim_human_audition_passed",
            "does_not_claim_final_mix_readiness",
            "does_not_import_live_grafana_dashboard",
            "does_not_claim_production_slo",
        ],
    }

    out_index = cloud_root / "loadtest/reports/week15_temporal_alignment_visual_evidence_platform_index.json"
    out_metrics = cloud_root / "observability/prometheus/week15_temporal_alignment_visual_evidence_metrics.prom"

    out_index.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    metrics = f"""# HELP week15_temporal_alignment_visual_evidence_candidate_total Candidates with waveform/RMS visual evidence.
# TYPE week15_temporal_alignment_visual_evidence_candidate_total gauge
week15_temporal_alignment_visual_evidence_candidate_total {len(visual_records)}
# HELP week15_temporal_alignment_visual_evidence_figure_total Waveform/RMS figures available for temporal alignment candidates.
# TYPE week15_temporal_alignment_visual_evidence_figure_total gauge
week15_temporal_alignment_visual_evidence_figure_total {len(visual_records)}
# HELP week15_temporal_alignment_duration_trim_total_sec Total audio duration trimmed across remediated candidates.
# TYPE week15_temporal_alignment_duration_trim_total_sec gauge
week15_temporal_alignment_duration_trim_total_sec {round(total_trim_sec, 6)}
# HELP week15_temporal_alignment_duration_trim_mean_sec Mean audio duration trimmed across remediated candidates.
# TYPE week15_temporal_alignment_duration_trim_mean_sec gauge
week15_temporal_alignment_duration_trim_mean_sec {round(total_trim_sec / len(visual_records), 6)}
# HELP week15_temporal_alignment_onset_proxy_abs_delta_total_sec Total absolute local RMS onset proxy delta across visual evidence candidates.
# TYPE week15_temporal_alignment_onset_proxy_abs_delta_total_sec gauge
week15_temporal_alignment_onset_proxy_abs_delta_total_sec {round(onset_shift_abs_total, 6)}
# HELP week15_temporal_alignment_visual_evidence_platform_index_ready Cloud consumed Mainbase waveform/RMS evidence successfully.
# TYPE week15_temporal_alignment_visual_evidence_platform_index_ready gauge
week15_temporal_alignment_visual_evidence_platform_index_ready{{status="PASS"}} 1
"""
    out_metrics.write_text(metrics, encoding="utf-8")

    print(json.dumps(index, ensure_ascii=False, indent=2))
    print(f"WROTE_INDEX={out_index}")
    print(f"WROTE_METRICS={out_metrics}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
