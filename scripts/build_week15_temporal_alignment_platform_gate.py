#!/usr/bin/env python3
"""
Build Week15 temporal alignment platform gate.

Purpose:
- Consume Mainbase temporal alignment remediation regression gate.
- Consume Java temporal alignment remediation API contract report.
- Emit a Cloud-side platform readiness gate input.

Boundary:
- Does not run Kubernetes Job.
- Does not import live Grafana dashboard.
- Does not claim production SLO.
- Does not claim semantic audio quality or human audition pass.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(str(path))
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mainbase", required=True)
    ap.add_argument("--java", required=True)
    ap.add_argument("--cloud", default=".")
    ap.add_argument("--out", default="loadtest/reports/week15_temporal_alignment_platform_gate.json")
    args = ap.parse_args()

    mainbase = Path(args.mainbase).expanduser().resolve()
    java = Path(args.java).expanduser().resolve()
    cloud = Path(args.cloud).expanduser().resolve()

    mainbase_gate_path = mainbase / "artifacts/evals/week15_temporal_alignment_regression_gate.json"
    java_contract_path = java / "artifacts/manifests/week15_temporal_alignment_remediation_api_contract_report.json"
    out_path = cloud / args.out

    blockers: list[str] = []

    try:
        mainbase_gate = read_json(mainbase_gate_path)
    except Exception as exc:
        mainbase_gate = {}
        blockers.append(f"cannot read mainbase regression gate: {mainbase_gate_path}: {exc}")

    try:
        java_contract = read_json(java_contract_path)
    except Exception as exc:
        java_contract = {}
        blockers.append(f"cannot read java api contract report: {java_contract_path}: {exc}")

    mainbase_summary = mainbase_gate.get("summary", {})
    original = mainbase_summary.get("original", {}) if isinstance(mainbase_summary, dict) else {}
    remediated = mainbase_summary.get("remediated", {}) if isinstance(mainbase_summary, dict) else {}
    remediated_candidate_ids = mainbase_summary.get("remediatedCandidateIds", []) if isinstance(mainbase_summary, dict) else []

    checks = {
        "mainbaseGatePass": mainbase_gate.get("status") == "PASS",
        "mainbaseDecisionGuarded": mainbase_gate.get("gateDecision") == "TEMPORAL_ALIGNMENT_REMEDIATION_REGRESSION_GUARDED",
        "mainbaseOriginalFailCountTwo": original.get("failCount") == 2,
        "mainbaseRemediatedFailCountZero": remediated.get("failCount") == 0,
        "mainbaseEventLocalPassDeltaTwo": mainbase_summary.get("eventLocalPassDelta") == 2 if isinstance(mainbase_summary, dict) else False,
        "mainbaseRemediatedTargetsExpected": sorted(remediated_candidate_ids) == ["procedural_v0_0004", "procedural_v0_0010"],
        "javaContractPass": java_contract.get("status") == "PASS",
        "javaApiTestsRunOne": java_contract.get("testsRun") == 1,
        "javaApiNoFailures": java_contract.get("failures") == 0,
        "javaApiNoErrors": java_contract.get("errors") == 0,
        "javaOriginalFailCountTwo": java_contract.get("originalFailCount") == 2,
        "javaRemediatedFailCountZero": java_contract.get("remediatedFailCount") == 0,
        "javaEventLocalPassDeltaTwo": java_contract.get("eventLocalPassDelta") == 2,
        "javaFailCountDeltaMinusTwo": java_contract.get("failCountDelta") == -2,
        "javaRemediatedTargetsExpected": sorted(java_contract.get("remediatedCandidateIds", [])) == ["procedural_v0_0004", "procedural_v0_0010"],
    }

    failed_checks = [name for name, ok in checks.items() if not ok]
    for name in failed_checks:
        blockers.append(f"failed check: {name}")

    status = "PASS" if not blockers else "FAIL"

    report = {
        "schemaVersion": "week15.temporal_alignment_platform_gate.v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "platformDecision": "TEMPORAL_ALIGNMENT_REMEDIATION_PLATFORM_READY_INPUT" if status == "PASS" else "BLOCKED",
        "inputs": {
            "mainbaseRegressionGate": str(mainbase_gate_path),
            "javaRemediationApiContractReport": str(java_contract_path),
        },
        "checks": checks,
        "failedChecks": failed_checks,
        "summary": {
            "candidateCount": java_contract.get("candidateCount"),
            "originalFailCount": java_contract.get("originalFailCount"),
            "remediatedFailCount": java_contract.get("remediatedFailCount"),
            "originalEventLocalPassCount": java_contract.get("originalEventLocalPassCount"),
            "remediatedEventLocalPassCount": java_contract.get("remediatedEventLocalPassCount"),
            "eventLocalPassDelta": java_contract.get("eventLocalPassDelta"),
            "failCountDelta": java_contract.get("failCountDelta"),
            "remediatedCandidateIds": java_contract.get("remediatedCandidateIds", []),
        },
        "platformMeaning": {
            "businessClaim": (
                "Temporal alignment drift is detectable, remediable, regression-guarded, "
                "and exposed through Java API contract evidence."
            ),
            "nextCloudUse": [
                "dashboard-ready platform readiness input",
                "future alert/log field input",
                "future worker result contract input"
            ],
        },
        "blockers": blockers,
        "boundary": [
            "platform_gate_input_only",
            "consumes_mainbase_and_java_evidence",
            "does_not_run_production_kubernetes_job",
            "does_not_claim_live_grafana_import",
            "does_not_claim_production_slo",
            "does_not_claim_semantic_audio_quality",
            "does_not_claim_human_audition_passed",
            "does_not_claim_final_mix_readiness"
        ],
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({
        "output": str(out_path),
        "status": status,
        "platformDecision": report["platformDecision"],
        "summary": report["summary"],
        "failedChecks": failed_checks,
        "blockers": blockers,
    }, indent=2, ensure_ascii=False))

    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())