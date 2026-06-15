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


def main() -> int:
    cloud_root = Path.cwd()
    mainbase_root = Path(
        os.environ.get(
            "MAINBASE_REPO",
            str(Path.home() / "work" / "audio_engineering_repo_skeleton_v1"),
        )
    )

    decision_path = mainbase_root / "artifacts/reviews/week15_temporal_alignment_manual_review_decision.json"
    evidence_gate_path = cloud_root / "loadtest/reports/week15_temporal_alignment_evidence_gate.json"

    decision = load_json(decision_path)
    evidence_gate = load_json(evidence_gate_path)

    require(decision.get("status") == "HUMAN_REVIEW_PARTIAL", "manual review decision must be HUMAN_REVIEW_PARTIAL")
    require(evidence_gate.get("status") == "PASS", "Cloud evidence gate must PASS")

    review_decision = decision.get("reviewDecision")
    require(isinstance(review_decision, dict), "reviewDecision must be object")
    require(review_decision.get("humanVisualInspection") == "PASS", "humanVisualInspection must PASS")
    require(review_decision.get("humanAudition") == "PARTIAL", "humanAudition must remain PARTIAL")
    require(review_decision.get("semanticQualityReview") == "NOT_PERFORMED", "semanticQualityReview must be NOT_PERFORMED")
    require(review_decision.get("finalMixReadiness") == "NOT_CLAIMED", "finalMixReadiness must be NOT_CLAIMED")

    records = decision.get("decisions")
    require(isinstance(records, list), "decisions must be array")
    require(len(records) == 2, "expected 2 review decision records")

    expected_ids = {"procedural_v0_0004", "procedural_v0_0010"}
    observed_ids = {r.get("candidateId") for r in records if isinstance(r, dict)}
    require(observed_ids == expected_ids, f"unexpected candidate ids: {observed_ids}")

    for item in records:
        cid = item["candidateId"]
        require(item.get("visualInspection") == "PASS", f"{cid} visualInspection must PASS")
        require(item.get("audition") == "NOT_PERFORMED", f"{cid} audition must be NOT_PERFORMED")
        require(float(item.get("durationTrimSec", 0.0)) > 0.0, f"{cid} durationTrimSec must be positive")
        require(float(item.get("onsetProxyDeltaSec", -1.0)) == 0.0, f"{cid} onsetProxyDeltaSec must be 0.0")

    index = {
        "schemaVersion": "week15.temporal_alignment_review_decision_platform_index.v1",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "platformDecision": "MANUAL_REVIEW_DECISION_CONSUMED_BY_CLOUD_PLATFORM_INDEX",
        "inputs": {
            "mainbaseManualReviewDecision": str(decision_path),
            "cloudEvidenceGate": str(evidence_gate_path),
        },
        "sourceHeads": {
            "mainbaseManualReviewDecisionCommitHead": "3c4579a",
            "cloudEvidenceGateCommitHead": "e7fd36b",
        },
        "reviewStatus": decision.get("status"),
        "reviewDecision": review_decision,
        "candidateDecisions": records,
        "allowedClaim": decision.get("allowedClaim"),
        "blockedClaims": decision.get("blockedClaims"),
        "metrics": {
            "review_candidate_total": len(records),
            "visual_pass_total": sum(1 for r in records if r.get("visualInspection") == "PASS"),
            "audition_not_performed_total": sum(1 for r in records if r.get("audition") == "NOT_PERFORMED"),
            "human_review_partial": 1,
            "human_review_pass": 0,
            "semantic_quality_review_performed": 0,
            "final_mix_readiness_claimed": 0,
        },
        "allowedPlatformClaim": "Signal/visual review supports duration trimming for procedural_v0_0004 and procedural_v0_0010; human audition remains partial/not performed.",
        "blockedPlatformClaims": [
            "Do not claim full human review pass.",
            "Do not claim human audition passed.",
            "Do not claim semantic quality review passed.",
            "Do not claim final mix readiness.",
            "Do not claim onset-proxy shift evidence.",
            "Do not claim production SLO or live Grafana import.",
        ],
        "nextAction": "Stop engineering expansion for today; upload/inspect the two waveform/RMS images or perform actual audition only if you want to upgrade from HUMAN_REVIEW_PARTIAL to HUMAN_REVIEW_PASS.",
        "boundary": [
            "cloud_review_decision_index_only",
            "consumes_mainbase_manual_review_decision",
            "does_not_call_live_java_service",
            "does_not_claim_full_human_review_pass",
            "does_not_claim_semantic_audio_quality",
            "does_not_claim_final_mix_readiness",
            "does_not_claim_production_slo",
        ],
    }

    out_index = cloud_root / "loadtest/reports/week15_temporal_alignment_review_decision_platform_index.json"
    out_index.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    metrics_text = f"""# HELP week15_temporal_alignment_review_decision_platform_index_ready Cloud consumed Mainbase manual review decision successfully.
# TYPE week15_temporal_alignment_review_decision_platform_index_ready gauge
week15_temporal_alignment_review_decision_platform_index_ready{{status="PASS"}} 1
# HELP week15_temporal_alignment_review_candidate_total Candidate count in manual review decision.
# TYPE week15_temporal_alignment_review_candidate_total gauge
week15_temporal_alignment_review_candidate_total {index["metrics"]["review_candidate_total"]}
# HELP week15_temporal_alignment_visual_pass_total Visual/signal review PASS count.
# TYPE week15_temporal_alignment_visual_pass_total gauge
week15_temporal_alignment_visual_pass_total {index["metrics"]["visual_pass_total"]}
# HELP week15_temporal_alignment_audition_not_performed_total Audition NOT_PERFORMED count.
# TYPE week15_temporal_alignment_audition_not_performed_total gauge
week15_temporal_alignment_audition_not_performed_total {index["metrics"]["audition_not_performed_total"]}
# HELP week15_temporal_alignment_human_review_partial Human review partial status.
# TYPE week15_temporal_alignment_human_review_partial gauge
week15_temporal_alignment_human_review_partial 1
# HELP week15_temporal_alignment_human_review_pass Human review pass status.
# TYPE week15_temporal_alignment_human_review_pass gauge
week15_temporal_alignment_human_review_pass 0
"""
    out_metrics = cloud_root / "observability/prometheus/week15_temporal_alignment_review_decision_metrics.prom"
    out_metrics.write_text(metrics_text, encoding="utf-8")

    print(json.dumps(index, ensure_ascii=False, indent=2))
    print(f"WROTE_INDEX={out_index}")
    print(f"WROTE_METRICS={out_metrics}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
