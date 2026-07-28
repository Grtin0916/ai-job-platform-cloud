#!/usr/bin/env python3
"""Exercise contention, takeover, stale fencing, and restart recovery."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cloud_job_ledger import CloudJobLedger, LeaseConflict, StaleFence
from common import dump_json


def exercise(db: Path) -> dict:
    ledger = CloudJobLedger(db)
    jobs = sorted(ledger.rows("jobs"), key=lambda item: item["java_job_id"])
    if not jobs:
        raise ValueError("ledger has no imported Java jobs")
    job_id = jobs[-1]["java_job_id"]
    resource = f"demo-job:{job_id}"
    token_a = ledger.acquire_lease(resource, "worker-A", 1.0, now=100.0)
    contention = False
    try:
        ledger.acquire_lease(resource, "worker-B", 1.0, now=100.2)
    except LeaseConflict:
        contention = True
        ledger.event("LEASE_CONTENTION", resource, {"holderId": "worker-B"})
    token_b = ledger.acquire_lease(resource, "worker-B", 5.0, now=102.0)
    ledger.event(
        "LEASE_TAKEOVER",
        resource,
        {"holderId": "worker-B", "fencingToken": token_b},
    )
    stale_rejected = False
    try:
        ledger.finalize(resource, "worker-A", token_a, f"job:{job_id}", job_id, now=102.1)
    except StaleFence:
        stale_rejected = True
        ledger.event(
            "STALE_FENCE_REJECTED",
            resource,
            {"holderId": "worker-A", "fencingToken": token_a},
        )
    ledger.finalize(resource, "worker-B", token_b, f"job:{job_id}", job_id, now=102.2)
    before = ledger.counts()
    ledger.close()

    reopened = CloudJobLedger(db)
    after = reopened.counts()
    release_rows = [
        row for row in reopened.rows("releases") if row["release_key"] == f"job:{job_id}"
    ]
    reopened.close()
    report = {
        "leaseContentionVerified": contention,
        "expiredLeaseTakeoverVerified": token_b == token_a + 1,
        "staleFenceRejected": stale_rejected,
        "restartRecoveryVerified": before == after and len(release_rows) == 1,
        "tokenA": token_a,
        "tokenB": token_b,
        "duplicateReleaseCount": max(0, len(release_rows) - 1),
        "descendantSystemClaimed": False,
        "durableLocalLedger": True,
        "distributedExactlyOnce": False,
        "countsBeforeRestart": before,
        "countsAfterRestart": after,
    }
    report["verified"] = all(
        report[key]
        for key in (
            "leaseContentionVerified",
            "expiredLeaseTakeoverVerified",
            "staleFenceRejected",
            "restartRecoveryVerified",
        )
    ) and report["duplicateReleaseCount"] == 0
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = exercise(args.db)
    dump_json(args.out, report)
    print(json.dumps(report, sort_keys=True))
    raise SystemExit(0 if report["verified"] else 1)


if __name__ == "__main__":
    main()
