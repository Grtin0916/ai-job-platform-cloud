#!/usr/bin/env python3
"""Verify promoted Cloud demo objects and public path boundaries."""

from __future__ import annotations

import argparse
from pathlib import Path

from common import contains_host_path, digest_without_prefix, dump_json, load_json, sha256_file


def verify(index_path: Path, store_root: Path) -> dict:
    index = load_json(index_path)
    failures = []
    for item in index["objects"]:
        digest = digest_without_prefix(item["sha256"])
        target = store_root / digest
        if (
            not target.is_file()
            or target.stat().st_size != item["sizeBytes"]
            or sha256_file(target) != digest
        ):
            failures.append(item["objectUri"])
    public_projection = {
        "objects": index["objects"],
        "caseRecords": index["caseRecords"],
    }
    host_leak = contains_host_path(public_projection)
    return {
        "verified": not failures and not host_leak,
        "recordCount": index["recordCount"],
        "provisionalCount": index["provisionalCount"],
        "blockedOrRejectedCount": index["blockedOrRejectedCount"],
        "finalSelectedCount": index["finalSelectedCount"],
        "uniqueObjectCount": len(index["objects"]),
        "integrityFailureCount": len(failures),
        "integrityFailures": failures,
        "hostPathLeakCount": int(host_leak),
        "decisionMutationCount": index["decisionMutationCount"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--store-root", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    report = verify(args.index, args.store_root)
    if args.out:
        dump_json(args.out, report)
    print(report)
    raise SystemExit(0 if report["verified"] else 1)


if __name__ == "__main__":
    main()
