#!/usr/bin/env python3
"""
Build Week13 Cloud platform readiness gate from Java API contract report.

This is a Cloud-side consumption gate, not a live Java service probe.
It checks whether the Java platform has exposed the candidate bank demo readiness
API and verified it through a RANDOM_PORT integration test.

Boundary:
- Does not claim production Kubernetes Job.
- Does not claim S3/MinIO/CSI.
- Does not claim semantic audio quality or final mix readiness.
- Does not claim live Java service availability.
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
        "--java-api-contract",
        type=Path,
        default=Path("../media-task-platform-java/artifacts/manifests/week13_candidate_bank_demo_readiness_api_contract_report.json"),
    )
    ap.add_argument(
        "--cloud-worker-smoke",
        type=Path,
        default=Path("loadtest/reports/week13_local_audio_worker_smoke_result.json"),
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=Path("loadtest/reports/week13_java_api_platform_readiness_gate.json"),
    )
    args = ap.parse_args()

    java_contract_path = args.java_api_contract.resolve()
    cloud_worker_smoke_path = args.cloud_worker_smoke.resolve()

    java_contract = read_json(java_contract_path)
    cloud_worker_smoke = read_json(cloud_worker_smoke_path)

    test_summary = java_contract.get("testSummary", {})
    consumed_counts = java_contract.get("consumedCounts", {})
    hard_checks = {
        "javaApiContractPass": java_contract.get("status") == "PASS",
        "javaEndpointExpected": java_contract.get("endpoint") == "/api/week13/candidate-bank-demo-readiness",
        "javaTestModeRandomPort": java_contract.get("testMode") == "SpringBootTest.RANDOM_PORT",
        "javaApiItRan": isinstance(test_summary.get("testsRun"), int) and test_summary.get("testsRun") >= 1,
        "javaApiItNoFailures": test_summary.get("failures") == 0,
        "javaApiItNoErrors": test_summary.get("errors") == 0,
        "javaCandidateCountIsTen": consumed_counts.get("candidateCount") == 10,
        "javaWorkerSuccessCountIsTen": consumed_counts.get("workerSuccessCount") == 10,
        "cloudWorkerSmokePass": cloud_worker_smoke.get("status") == "PASS",
        "cloudWorkerSuccessCountIsTen": cloud_worker_smoke.get("workerSuccessCount") == 10,
        "cloudWorkerSmokeNoBlockers": cloud_worker_smoke.get("blockers") == [],
        "javaContractNoBlockers": java_contract.get("blockers") == [],
    }

    status = "PASS" if all(hard_checks.values()) else "FAIL"

    payload = {
        "schemaVersion": "week13.cloud_java_api_platform_readiness_gate.v1",
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "scope": "cloud-dashboard-ready-platform-readiness-gate",
        "sourceJavaApiContract": str(java_contract_path),
        "sourceCloudWorkerSmoke": str(cloud_worker_smoke_path),
        "endpoint": java_contract.get("endpoint"),
        "testMode": java_contract.get("testMode"),
        "testSummary": test_summary,
        "consumedCounts": consumed_counts,
        "cloudWorkerSmokeSummary": {
            "status": cloud_worker_smoke.get("status"),
            "candidateCount": cloud_worker_smoke.get("candidateCount"),
            "workerSuccessCount": cloud_worker_smoke.get("workerSuccessCount"),
            "blockers": cloud_worker_smoke.get("blockers"),
        },
        "boundary": [
            "does_not_claim_live_java_service_probe",
            "does_not_claim_production_kubernetes_job",
            "does_not_claim_s3_minio_csi_or_cloud_object_storage",
            "does_not_claim_semantic_audio_quality",
            "does_not_claim_human_audition_pass",
            "does_not_claim_final_mix_readiness",
        ],
        "hardChecks": hard_checks,
        "blockers": [] if status == "PASS" else [k for k, v in hard_checks.items() if not v],
        "platformDecision": (
            "PASS: Cloud can consume the Java Week13 candidate bank demo readiness API contract as a dashboard-ready platform gate."
            if status == "PASS"
            else "FAIL: Cloud platform readiness gate is incomplete; inspect hardChecks and blockers."
        ),
        "nextRecommendedStep": (
            "Render this gate into a lightweight Grafana dashboard JSON or dashboard-ready panel summary."
        ),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({
        "out": str(args.out),
        "status": status,
        "failedChecks": payload["blockers"],
        "testSummary": test_summary,
        "consumedCounts": consumed_counts,
        "cloudWorkerSmokeSummary": payload["cloudWorkerSmokeSummary"],
    }, indent=2, ensure_ascii=False))

    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())