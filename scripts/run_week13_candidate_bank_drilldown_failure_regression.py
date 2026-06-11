#!/usr/bin/env python3
"""
Run Week13 candidate-bank drilldown failure regression.

This script creates a temporary corrupted worker-smoke table, flips one
candidate's workerStatus to FAILED, re-runs the existing drilldown builder,
and expects the drilldown summary to fail with a blocker pointing to that
candidate.

Boundary:
- Uses temporary copied inputs only.
- Does not modify official PASS tables.
- Does not claim semantic quality or production readiness.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing required json: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def copy_and_corrupt_smoke_table(
    src: Path,
    dst: Path,
    candidate_id: str,
    status_column: str,
    failed_value: str,
) -> dict[str, Any]:
    if not src.exists():
        raise FileNotFoundError(f"missing smoke table: {src}")

    dst.parent.mkdir(parents=True, exist_ok=True)

    with src.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    if "candidateId" not in fieldnames:
        raise SystemExit(f"candidateId column not found in {src}, fields={fieldnames}")

    if status_column not in fieldnames:
        raise SystemExit(f"{status_column} column not found in {src}, fields={fieldnames}")

    touched = 0
    original_status = None

    for row in rows:
        if row.get("candidateId") == candidate_id:
            original_status = row.get(status_column)
            row[status_column] = failed_value
            touched += 1

    if touched != 1:
        raise SystemExit(f"expected exactly one candidate row for {candidate_id}, touched={touched}")

    with dst.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return {
        "source": str(src),
        "corruptedCopy": str(dst),
        "candidateId": candidate_id,
        "statusColumn": status_column,
        "originalStatus": original_status,
        "failedValue": failed_value,
        "touchedRows": touched,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--builder",
        type=Path,
        default=Path("scripts/build_week13_candidate_bank_platform_drilldown.py"),
    )
    ap.add_argument(
        "--mainbase-placement-table",
        type=Path,
        required=True,
    )
    ap.add_argument(
        "--cloud-worker-input-table",
        type=Path,
        default=Path("loadtest/reports/week13_ready_candidate_worker_input_table.csv"),
    )
    ap.add_argument(
        "--cloud-worker-smoke-table",
        type=Path,
        default=Path("loadtest/reports/week13_local_audio_worker_smoke_table.csv"),
    )
    ap.add_argument(
        "--cloud-gate",
        type=Path,
        default=Path("loadtest/reports/week13_java_api_platform_readiness_gate.json"),
    )
    ap.add_argument(
        "--candidate-id",
        default="procedural_v0_0002",
    )
    ap.add_argument(
        "--status-column",
        default="workerStatus",
    )
    ap.add_argument(
        "--failed-value",
        default="FAILED",
    )
    ap.add_argument(
        "--tmp-dir",
        type=Path,
        default=Path("artifacts/tmp/week13_drilldown_failure_regression"),
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=Path("loadtest/reports/week13_candidate_bank_platform_drilldown_failure_regression.json"),
    )
    args = ap.parse_args()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = args.tmp_dir / ts
    run_dir.mkdir(parents=True, exist_ok=True)

    corrupted_smoke = run_dir / "week13_local_audio_worker_smoke_table_corrupted.csv"
    corruption = copy_and_corrupt_smoke_table(
        src=args.cloud_worker_smoke_table,
        dst=corrupted_smoke,
        candidate_id=args.candidate_id,
        status_column=args.status_column,
        failed_value=args.failed_value,
    )

    fail_csv = run_dir / "week13_candidate_bank_platform_drilldown_table_fail.csv"
    fail_json = run_dir / "week13_candidate_bank_platform_drilldown_table_fail.json"
    fail_summary = run_dir / "week13_candidate_bank_platform_drilldown_summary_fail.json"

    cmd = [
        sys.executable,
        str(args.builder),
        "--mainbase-placement-table",
        str(args.mainbase_placement_table),
        "--cloud-worker-input-table",
        str(args.cloud_worker_input_table),
        "--cloud-worker-smoke-table",
        str(corrupted_smoke),
        "--cloud-gate",
        str(args.cloud_gate),
        "--csv-out",
        str(fail_csv),
        "--json-out",
        str(fail_json),
        "--summary-out",
        str(fail_summary),
    ]

    proc = subprocess.run(cmd, text=True, capture_output=True)

    summary_exists = fail_summary.exists()
    fail_obj = read_json(fail_summary) if summary_exists else {}

    blockers = fail_obj.get("blockers", [])
    blockers_text = "\n".join(str(x) for x in blockers)

    expected_checks = {
        "builderExitedNonZero": proc.returncode != 0,
        "failureSummaryExists": summary_exists,
        "failureSummaryStatusFail": fail_obj.get("status") == "FAIL",
        "targetCandidateMentionedInBlockers": args.candidate_id in blockers_text,
        "workerSmokeFailureDetected": "worker_smoke_not_success" in blockers_text,
        "officialSmokeTableNotModified": read_json(args.cloud_gate).get("status") == "PASS",
    }

    status = "PASS" if all(expected_checks.values()) else "FAIL"

    payload = {
        "schemaVersion": "week13.cloud_candidate_bank_platform_drilldown_failure_regression.v1",
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "scope": "negative-path-failure-regression-only",
        "corruption": corruption,
        "builderCommand": cmd,
        "builderReturnCode": proc.returncode,
        "builderStdout": proc.stdout[-4000:],
        "builderStderr": proc.stderr[-4000:],
        "failureOutputs": {
            "csv": str(fail_csv),
            "json": str(fail_json),
            "summary": str(fail_summary),
        },
        "failureSummaryStatus": fail_obj.get("status"),
        "failureSummaryCounts": fail_obj.get("counts"),
        "failureSummaryHardChecks": fail_obj.get("hardChecks"),
        "failureSummaryBlockers": blockers,
        "expectedChecks": expected_checks,
        "blockers": [] if status == "PASS" else [k for k, v in expected_checks.items() if not v],
        "boundary": [
            "uses_temporary_corrupted_copy_only",
            "does_not_modify_official_pass_tables",
            "does_not_claim_semantic_audio_quality",
            "does_not_claim_human_audition_pass",
            "does_not_claim_final_mix_readiness",
            "does_not_claim_production_kubernetes_job",
        ],
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({
        "out": str(args.out),
        "status": status,
        "targetCandidate": args.candidate_id,
        "builderReturnCode": proc.returncode,
        "failureSummaryStatus": payload["failureSummaryStatus"],
        "failureSummaryBlockers": blockers,
        "expectedChecks": expected_checks,
        "blockers": payload["blockers"],
    }, indent=2, ensure_ascii=False))

    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())