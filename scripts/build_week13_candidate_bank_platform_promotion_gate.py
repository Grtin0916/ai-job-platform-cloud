#!/usr/bin/env python3
"""
Build Week13 candidate bank platform promotion gate.

This gate consolidates:
- Java API platform readiness gate
- dashboard-ready summary
- candidate-level drilldown summary
- negative-path drilldown failure regression

Output:
- one machine-readable promotion decision for Week13 Candidate Audio Bank V1.

Boundary:
- does not claim live Grafana import
- does not claim production SLO / alerting
- does not claim production Kubernetes Job
- does not claim S3 / MinIO / CSI
- does not claim semantic audio quality, human audition, or final mix readiness
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing required json: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--java-api-gate",
        type=Path,
        default=Path("loadtest/reports/week13_java_api_platform_readiness_gate.json"),
    )
    ap.add_argument(
        "--dashboard-summary",
        type=Path,
        default=Path("loadtest/reports/week13_candidate_bank_platform_readiness_dashboard_summary.json"),
    )
    ap.add_argument(
        "--drilldown-summary",
        type=Path,
        default=Path("loadtest/reports/week13_candidate_bank_platform_drilldown_summary.json"),
    )
    ap.add_argument(
        "--failure-regression",
        type=Path,
        default=Path("loadtest/reports/week13_candidate_bank_platform_drilldown_failure_regression.json"),
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=Path("loadtest/reports/week13_candidate_bank_platform_promotion_gate.json"),
    )
    args = ap.parse_args()

    java_gate = read_json(args.java_api_gate)
    dashboard = read_json(args.dashboard_summary)
    drilldown = read_json(args.drilldown_summary)
    failure = read_json(args.failure_regression)

    java_counts = java_gate.get("consumedCounts", {})
    java_test = java_gate.get("testSummary", {})
    dashboard_values = dashboard.get("dashboardValues", {})
    drilldown_counts = drilldown.get("counts", {})
    failure_checks = failure.get("expectedChecks", {})

    hard_checks = {
        "javaApiPlatformGatePass": java_gate.get("status") == "PASS",
        "javaApiEndpointExpected": java_gate.get("endpoint") == "/api/week13/candidate-bank-demo-readiness",
        "javaApiItNoFailures": java_test.get("failures") == 0,
        "javaApiItNoErrors": java_test.get("errors") == 0,
        "javaCandidateCountIsTen": java_counts.get("candidateCount") == 10,
        "javaWorkerSuccessCountIsTen": java_counts.get("workerSuccessCount") == 10,

        "dashboardSummaryPass": dashboard.get("status") == "PASS",
        "dashboardCandidateCountIsTen": dashboard_values.get("candidateCount") == 10,
        "dashboardWorkerSuccessCountIsTen": dashboard_values.get("workerSuccessCount") == 10,

        "drilldownSummaryPass": drilldown.get("status") == "PASS",
        "drilldownCandidateCountIsTen": drilldown_counts.get("candidateCount") == 10,
        "drilldownReadyCountIsTen": drilldown_counts.get("readyCount") == 10,
        "drilldownFullClipCountIsFive": drilldown_counts.get("fullClipLikeCount") == 5,
        "drilldownEventLocalCountIsFive": drilldown_counts.get("eventLocalLikeCount") == 5,

        "negativeRegressionPass": failure.get("status") == "PASS",
        "negativeRegressionBuilderExitedNonZero": failure_checks.get("builderExitedNonZero") is True,
        "negativeRegressionFailureDetected": failure_checks.get("workerSmokeFailureDetected") is True,
        "negativeRegressionTargetCandidateLocated": failure_checks.get("targetCandidateMentionedInBlockers") is True,
        "negativeRegressionOfficialTableNotModified": failure_checks.get("officialSmokeTableNotModified") is True,
    }

    status = "PASS" if all(hard_checks.values()) else "FAIL"
    promotion_decision = "PROMOTE_TO_WEEK13_DEMO_READY" if status == "PASS" else "HOLD"

    blockers = [] if status == "PASS" else [k for k, v in hard_checks.items() if not v]

    payload = {
        "schemaVersion": "week13.cloud_candidate_bank_platform_promotion_gate.v1",
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "promotionDecision": promotion_decision,
        "scope": "local-platform-promotion-gate-only",
        "sources": {
            "javaApiGate": str(args.java_api_gate),
            "dashboardSummary": str(args.dashboard_summary),
            "drilldownSummary": str(args.drilldown_summary),
            "failureRegression": str(args.failure_regression),
        },
        "positivePath": {
            "candidateCount": java_counts.get("candidateCount"),
            "workerSuccessCount": java_counts.get("workerSuccessCount"),
            "testsRun": java_test.get("testsRun"),
            "failures": java_test.get("failures"),
            "errors": java_test.get("errors"),
            "drilldownReadyCount": drilldown_counts.get("readyCount"),
            "fullClipLikeCount": drilldown_counts.get("fullClipLikeCount"),
            "eventLocalLikeCount": drilldown_counts.get("eventLocalLikeCount"),
        },
        "negativePath": {
            "targetCandidate": failure.get("corruption", {}).get("candidateId"),
            "originalStatus": failure.get("corruption", {}).get("originalStatus"),
            "failedValue": failure.get("corruption", {}).get("failedValue"),
            "builderReturnCode": failure.get("builderReturnCode"),
            "failureSummaryStatus": failure.get("failureSummaryStatus"),
            "failureSummaryBlockers": failure.get("failureSummaryBlockers"),
        },
        "hardChecks": hard_checks,
        "blockers": blockers,
        "boundary": [
            "does_not_claim_live_grafana_import",
            "does_not_claim_production_slo",
            "does_not_claim_production_alerting",
            "does_not_claim_live_java_service_probe",
            "does_not_claim_production_kubernetes_job",
            "does_not_claim_s3_minio_csi_or_cloud_object_storage",
            "does_not_claim_semantic_audio_quality",
            "does_not_claim_human_audition_pass",
            "does_not_claim_final_mix_readiness",
        ],
        "platformDecision": (
            "PASS: Candidate Audio Bank V1 is ready for Week13 local demo promotion with positive-path evidence and negative-path regression evidence."
            if status == "PASS"
            else "FAIL: Candidate Audio Bank V1 promotion is blocked; inspect hardChecks and blockers."
        ),
        "nextRecommendedStep": (
            "Create a concise Week13 Thursday engineering closure note or wire this promotion gate into Friday's stage gate."
        ),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({
        "out": str(args.out),
        "status": status,
        "promotionDecision": promotion_decision,
        "positivePath": payload["positivePath"],
        "negativePath": payload["negativePath"],
        "failedChecks": blockers,
    }, indent=2, ensure_ascii=False))

    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())