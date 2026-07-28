#!/usr/bin/env python3
"""Aggregate the durable release gate without hiding blocked runtime axes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import dump_json, load_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-verify", type=Path, required=True)
    parser.add_argument("--import-report", type=Path, required=True)
    parser.add_argument("--reuse-report", type=Path, required=True)
    parser.add_argument("--lease-report", type=Path, required=True)
    parser.add_argument("--k6-exit", type=Path, required=True)
    parser.add_argument("--observability-verify", type=Path, required=True)
    parser.add_argument("--release-verify", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    artifact = load_json(args.artifact_verify)
    imported = load_json(args.import_report)
    reused = load_json(args.reuse_report)
    lease = load_json(args.lease_report)
    k6 = load_json(args.k6_exit)
    observability = load_json(args.observability_verify)
    release = load_json(args.release_verify)
    axes = {
        "artifactPromotion": "PASS" if artifact["verified"] else "FAIL",
        "durableLedger": "PASS"
        if imported["counts"]["jobs"] == 3
        and imported["counts"]["releases"] == 12
        and reused["reused"]
        and reused["counts"]["jobs"] == 3
        else "FAIL",
        "leaseAndFencing": "PASS" if lease["verified"] else "FAIL",
        "k6Threshold": "PASS"
        if k6["executed"] and k6["exitCode"] == 0
        else "RUNTIME_BLOCKED",
        "observabilityArtifacts": "PASS" if observability["verified"] else "FAIL",
        "releaseIntegrity": "PASS" if release["verified"] else "FAIL",
        "humanGate": "PENDING",
        "productionWorkflow": "UNVERIFIED",
    }
    report = {
        "schemaVersion": "durable-demo-e2e-gate/v1",
        "gateStatus": "PASS"
        if all(value == "PASS" for value in axes.values())
        else "GATE_FAILED",
        "axes": axes,
        "truth": {
            "caseRecordCount": 12,
            "actualJavaJobCount": imported["counts"]["jobs"],
            "provisionalCount": 10,
            "blockedOrRejectedCount": 2,
            "finalSelectedCount": 0,
            "manualReviewCompletedCount": 0,
            "liveSuccessCount": 0,
        },
        "k6": k6,
        "release": release,
        "claimBoundary": {
            "artifactReady": artifact["verified"],
            "durableLocalLedger": imported["durableLocalLedger"],
            "processRestartRecovery": lease["restartRecoveryVerified"],
            "distributedExactlyOnce": False,
            "humanGateReady": False,
            "finalSelectionReady": False,
            "productionPrometheusVerified": False,
            "productionAlertingVerified": False,
            "liveGrafanaImportVerified": False,
            "productionWorkflowVerified": False,
            "slsaCompliant": False,
            "signedAttestation": False,
        },
        "failureExplanation": (
            "Docker Desktop daemon was unavailable. The real k6 container invocation "
            f"returned exit code {k6['exitCode']}; no threshold PASS was synthesized."
        ),
    }
    dump_json(args.out, report)
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
