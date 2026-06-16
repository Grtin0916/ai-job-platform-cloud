#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_INPUT = (
    Path.home()
    / "work/audio_engineering_repo_skeleton_v1/artifacts/reviews/"
    / "week15_temporal_alignment_semantic_quality_review_v0.json"
)
OUT_INDEX = Path("loadtest/reports/week15_temporal_alignment_semantic_quality_platform_index.json")
OUT_METRICS = Path("observability/prometheus/week15_temporal_alignment_semantic_quality_metrics.prom")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing input json: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def metric_line(name: str, value: int | float, labels: dict[str, str] | None = None) -> str:
    labels = labels or {}
    label_text = ""
    if labels:
        encoded = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        label_text = "{" + encoded + "}"
    return f"{name}{label_text} {value}"


def bool_to_int(v: bool) -> int:
    return 1 if v else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    args = parser.parse_args()

    src = load_json(args.input)

    candidates = src.get("candidates", [])
    candidate_count = len(candidates)
    candidates_with_audio = [c for c in candidates if c.get("audioPaths")]
    candidates_with_original = [c for c in candidates if "original" in c.get("audioPaths", {})]
    candidates_with_remediated = [c for c in candidates if "remediated" in c.get("audioPaths", {})]

    risky_candidates = []
    for c in candidates:
        flags = set(c.get("riskFlags", []))
        flags.discard("NO_LIGHTWEIGHT_SIGNAL_RISK_DETECTED")
        flags.discard("NO_AUDIO_PATHS_RESOLVED")
        if flags:
            risky_candidates.append(
                {
                    "candidateId": c.get("candidateId"),
                    "riskFlags": sorted(flags),
                    "audioPaths": c.get("audioPaths", {}),
                }
            )

    boundary = {
        "humanReviewStatus": src.get("humanReviewStatus"),
        "auditionStatus": src.get("auditionStatus"),
        "semanticQualityReviewStatus": src.get("semanticQualityReviewStatus"),
        "finalMixReadiness": src.get("finalMixReadiness"),
    }

    blocked_claims_ok = (
        boundary["humanReviewStatus"] == "HUMAN_REVIEW_PARTIAL"
        and boundary["auditionStatus"] == "NOT_PERFORMED"
        and boundary["semanticQualityReviewStatus"] == "NOT_PERFORMED"
        and boundary["finalMixReadiness"] == "NOT_CLAIMED"
    )

    platform_decision = "SEMANTIC_REVIEW_READY_FOR_PLATFORM"
    if src.get("qualityGateLiteStatus") != "SEMANTIC_REVIEW_READY":
        platform_decision = "BLOCKED_SOURCE_NOT_READY"
    elif not blocked_claims_ok:
        platform_decision = "BLOCKED_CLAIM_BOUNDARY_VIOLATION"
    elif not candidates_with_remediated:
        platform_decision = "BLOCKED_NO_REMEDIATED_AUDIO"

    index = {
        "schemaVersion": "week15.semantic-quality-platform-index.v0",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "source": {
            "mainbaseReviewJson": str(args.input),
            "mainbaseSchemaVersion": src.get("schemaVersion"),
            "mainbaseGeneratedAtUtc": src.get("generatedAtUtc"),
        },
        "platformDecision": platform_decision,
        "claimBoundaryOk": blocked_claims_ok,
        "qualityGateLiteStatus": src.get("qualityGateLiteStatus"),
        "reviewBoundary": boundary,
        "summary": {
            "candidateCount": candidate_count,
            "candidatesWithAnyAudio": len(candidates_with_audio),
            "candidatesWithOriginalAudio": len(candidates_with_original),
            "candidatesWithRemediatedAudio": len(candidates_with_remediated),
            "riskyCandidateCount": len(risky_candidates),
            "riskCandidateIds": [x["candidateId"] for x in risky_candidates],
        },
        "riskDrilldown": risky_candidates,
        "allowedClaims": [
            "Cloud consumed a local Mainbase semantic-quality review packet.",
            "Platform can expose SEMANTIC_REVIEW_READY_FOR_PLATFORM when source is ready and claim boundaries are safe.",
        ],
        "blockedClaims": [
            "Do not claim human audition PASS.",
            "Do not claim semantic audio quality PASS.",
            "Do not claim final mix readiness.",
            "Do not claim live Grafana import or production SLO.",
        ],
    }

    OUT_INDEX.parent.mkdir(parents=True, exist_ok=True)
    OUT_METRICS.parent.mkdir(parents=True, exist_ok=True)
    OUT_INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# HELP week15_temporal_alignment_semantic_quality_ready Source semantic quality review is ready for platform consumption.",
        "# TYPE week15_temporal_alignment_semantic_quality_ready gauge",
        metric_line(
            "week15_temporal_alignment_semantic_quality_ready",
            bool_to_int(platform_decision == "SEMANTIC_REVIEW_READY_FOR_PLATFORM"),
            {"decision": platform_decision},
        ),
        "# HELP week15_temporal_alignment_semantic_quality_candidate_count Candidate count in semantic quality packet.",
        "# TYPE week15_temporal_alignment_semantic_quality_candidate_count gauge",
        metric_line("week15_temporal_alignment_semantic_quality_candidate_count", candidate_count),
        "# HELP week15_temporal_alignment_semantic_quality_risky_candidate_count Candidates with lightweight signal risk flags.",
        "# TYPE week15_temporal_alignment_semantic_quality_risky_candidate_count gauge",
        metric_line("week15_temporal_alignment_semantic_quality_risky_candidate_count", len(risky_candidates)),
        "# HELP week15_temporal_alignment_semantic_quality_claim_boundary_ok Whether unverified claims remain blocked.",
        "# TYPE week15_temporal_alignment_semantic_quality_claim_boundary_ok gauge",
        metric_line("week15_temporal_alignment_semantic_quality_claim_boundary_ok", bool_to_int(blocked_claims_ok)),
    ]

    for c in risky_candidates:
        lines.append(
            metric_line(
                "week15_temporal_alignment_semantic_quality_candidate_risk",
                1,
                {
                    "candidate_id": str(c["candidateId"]),
                    "risk_flags": "|".join(c["riskFlags"]),
                },
            )
        )

    OUT_METRICS.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(
        {
            "platformDecision": platform_decision,
            "claimBoundaryOk": blocked_claims_ok,
            "candidateCount": candidate_count,
            "riskyCandidateCount": len(risky_candidates),
            "riskCandidateIds": [x["candidateId"] for x in risky_candidates],
            "index": str(OUT_INDEX),
            "metrics": str(OUT_METRICS),
        },
        ensure_ascii=False,
        indent=2,
    ))

    return 0 if platform_decision == "SEMANTIC_REVIEW_READY_FOR_PLATFORM" else 2


if __name__ == "__main__":
    raise SystemExit(main())
