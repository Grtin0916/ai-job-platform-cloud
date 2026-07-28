#!/usr/bin/env python3
"""Print a stable JSON snapshot of the local durable ledger."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cloud_job_ledger import CloudJobLedger


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, required=True)
    args = parser.parse_args()
    ledger = CloudJobLedger(args.db)
    try:
        print(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "counts": ledger.counts(),
                    "jobs": sorted(ledger.rows("jobs"), key=lambda item: item["java_job_id"]),
                    "leases": sorted(ledger.rows("leases"), key=lambda item: item["resource_key"]),
                },
                sort_keys=True,
            )
        )
    finally:
        ledger.close()


if __name__ == "__main__":
    main()
