#!/usr/bin/env python3
"""Idempotently import Java demo jobs and promoted artifacts."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

from cloud_job_ledger import CloudJobLedger, ContractConflict
from common import dump_json, load_json, sha256_bytes


def canonical_digest(*values: dict) -> str:
    payload = json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
    return sha256_bytes(payload)


def export_events(ledger: CloudJobLedger, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        for event in ledger.rows("events"):
            stream.write(json.dumps(event, sort_keys=True) + "\n")


def export_jobs(ledger: CloudJobLedger, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "java_job_id",
        "cloud_job_key",
        "case_id",
        "mode",
        "execution_status",
        "publish_decision",
        "final_selected",
    ]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in sorted(ledger.rows("jobs"), key=lambda item: item["java_job_id"]):
            writer.writerow({field: row[field] for field in fields})


def import_records(
    ledger: CloudJobLedger, handoff: dict, report: dict, artifact_index: dict
) -> dict:
    import_digest = canonical_digest(handoff, report, artifact_index)
    reused = False
    with ledger.immediate() as connection:
        existing = connection.execute(
            "SELECT 1 FROM imports WHERE import_digest=?", (import_digest,)
        ).fetchone()
        if existing:
            reused = True
        else:
            connection.execute(
                "INSERT INTO imports VALUES (?, ?, ?)",
                (import_digest, handoff["handoffDigest"], time.time()),
            )
            for job in handoff["jobs"]:
                cloud_key = sha256_bytes(
                    (
                        job["jobId"]
                        + job["requestFingerprint"]
                        + handoff["handoffDigest"]
                    ).encode()
                )
                current = connection.execute(
                    "SELECT import_digest, request_fingerprint FROM jobs WHERE java_job_id=?",
                    (job["jobId"],),
                ).fetchone()
                if current and (
                    current["import_digest"] != import_digest
                    or current["request_fingerprint"] != job["requestFingerprint"]
                ):
                    raise ContractConflict(f"CONTRACT_CONFLICT:{job['jobId']}")
                connection.execute(
                    "INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)",
                    (
                        job["jobId"],
                        cloud_key,
                        job["requestFingerprint"],
                        import_digest,
                        job["caseId"],
                        job["mode"],
                        job["executionStatus"],
                        job["publishDecision"],
                        json.dumps(job, sort_keys=True),
                    ),
                )
                for attempt in job.get("attempts", []):
                    connection.execute(
                        "INSERT INTO attempts VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            f"{job['jobId']}:{attempt['attemptId']}",
                            job["jobId"],
                            attempt["attemptNumber"],
                            attempt["status"],
                            attempt.get("exitCode"),
                            attempt.get("resultDigest"),
                            json.dumps(attempt, sort_keys=True),
                        ),
                    )
            for artifact in artifact_index["objects"]:
                connection.execute(
                    "INSERT INTO artifacts VALUES (?, ?, ?, ?, ?)",
                    (
                        artifact["objectUri"],
                        artifact["sha256"],
                        artifact["sizeBytes"],
                        artifact["mediaType"],
                        artifact["artifactOriginCommit"],
                    ),
                )
            for case in artifact_index["caseRecords"]:
                connection.execute(
                    "INSERT INTO releases VALUES (?, NULL, ?, ?, ?, ?, NULL, ?)",
                    (
                        f"case:{case['caseId']}",
                        case["caseId"],
                        case["executionStatus"],
                        case["publishDecision"],
                        case["selectedArtifactUri"]
                        if case["publishDecision"] == "PROVISIONAL_SELECTED"
                        else None,
                        time.time(),
                    ),
                )
    ledger.event(
        "IMPORT_REUSED" if reused else "IMPORT_COMMITTED",
        import_digest,
        {"reused": reused, "javaJobCount": len(handoff["jobs"]), "caseRecordCount": 12},
    )
    return {
        "importDigest": import_digest,
        "reused": reused,
        "durableLocalLedger": True,
        "processRestartRecovery": True,
        "distributedDatabase": False,
        "multiNodeConsensus": False,
        "distributedExactlyOnce": False,
        "counts": ledger.counts(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--handoff", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--artifact-index", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--out-csv", type=Path, required=True)
    parser.add_argument("--out-summary", type=Path)
    args = parser.parse_args()
    ledger = CloudJobLedger(args.db)
    try:
        summary = import_records(
            ledger, load_json(args.handoff), load_json(args.report), load_json(args.artifact_index)
        )
        export_events(ledger, args.events)
        export_jobs(ledger, args.out_csv)
        if args.out_summary:
            dump_json(args.out_summary, summary)
        print(json.dumps(summary, sort_keys=True))
    except ContractConflict as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(2) from error
    finally:
        ledger.close()


if __name__ == "__main__":
    main()
