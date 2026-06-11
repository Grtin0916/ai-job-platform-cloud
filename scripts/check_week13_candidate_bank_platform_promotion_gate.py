#!/usr/bin/env python3
"""
Check Week13 candidate bank platform promotion gate.

This is a CI/local gate checker:
- Reads the promotion gate JSON.
- Fails with non-zero exit code if promotion is not safe.
- Does not regenerate artifacts.
- Does not claim production deployment, live Grafana import, S3/MinIO/CSI, semantic quality, or final mix readiness.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing required gate file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--gate",
        type=Path,
        default=Path("loadtest/reports/week13_candidate_bank_platform_promotion_gate.json"),
    )
    args = ap.parse_args()

    gate = read_json(args.gate)
    positive = gate.get("positivePath", {})
    negative = gate.get("negativePath", {})
    hard = gate.get("hardChecks", {})

    checks = {
        "statusPass": gate.get("status") == "PASS",
        "promotionDecisionReady": gate.get("promotionDecision") == "PROMOTE_TO_WEEK13_DEMO_READY",
        "candidateCountIsTen": positive.get("candidateCount") == 10,
        "workerSuccessCountIsTen": positive.get("workerSuccessCount") == 10,
        "javaApiItRan": positive.get("testsRun") == 1,
        "javaApiNoFailures": positive.get("failures") == 0,
        "javaApiNoErrors": positive.get("errors") == 0,
        "drilldownReadyCountIsTen": positive.get("drilldownReadyCount") == 10,
        "fullClipLikeCountIsFive": positive.get("fullClipLikeCount") == 5,
        "eventLocalLikeCountIsFive": positive.get("eventLocalLikeCount") == 5,
        "negativeRegressionTargetExpected": negative.get("targetCandidate") == "procedural_v0_0002",
        "negativeRegressionDetectedFail": negative.get("failureSummaryStatus") == "FAIL",
        "negativeRegressionLocatedBlocker": any(
            "procedural_v0_0002:worker_smoke_not_success:FAILED" in str(x)
            for x in negative.get("failureSummaryBlockers", [])
        ),
        "noGateBlockers": gate.get("blockers") == [],
        "allEmbeddedHardChecksTrue": all(v is True for v in hard.values()),
    }

    failed = [k for k, v in checks.items() if not v]
    result = {
        "gate": str(args.gate),
        "status": "PASS" if not failed else "FAIL",
        "promotionDecision": gate.get("promotionDecision"),
        "checks": checks,
        "failedChecks": failed,
        "boundary": [
            "checker_only",
            "does_not_regenerate_artifacts",
            "does_not_claim_live_grafana_import",
            "does_not_claim_production_slo",
            "does_not_claim_production_kubernetes_job",
            "does_not_claim_s3_minio_csi_or_cloud_object_storage",
            "does_not_claim_semantic_audio_quality",
            "does_not_claim_final_mix_readiness",
        ],
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())