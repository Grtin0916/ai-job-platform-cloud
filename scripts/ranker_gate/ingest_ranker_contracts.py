#!/usr/bin/env python3
"""Build the W21 unified Mainbase/Java Ranker contract snapshot."""

import argparse
import json
import shutil
from pathlib import Path

from ranker_contract import build_snapshot, dump_json, write_snapshot_csv


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mainbase-root", type=Path, required=True)
    parser.add_argument("--java-root", type=Path, required=True)
    parser.add_argument("--mainbase-delivery", type=Path, required=True)
    parser.add_argument("--java-version-report", type=Path, required=True)
    parser.add_argument("--java-events", type=Path, required=True)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-csv", type=Path, required=True)
    args = parser.parse_args()
    cloud_root = Path(__file__).resolve().parents[2]
    snapshot = build_snapshot(
        args.mainbase_root.resolve(), args.java_root.resolve(), cloud_root,
        args.mainbase_delivery, args.java_version_report, args.java_events
    )
    dump_json(args.out_json, snapshot)
    write_snapshot_csv(args.out_csv, snapshot)
    frozen = cloud_root / "artifacts/ranker/inputs"
    frozen.mkdir(parents=True, exist_ok=True)
    delivery_report = args.mainbase_root / args.mainbase_delivery
    delivery_root = args.mainbase_root / json.loads(
        delivery_report.read_text(encoding="utf-8")
    )["bundleRelativePath"]
    for source, name in (
        (delivery_report, "mainbase-ranker-delivery-report.json"),
        (delivery_root / "manifest.json", "mainbase-ranker-manifest.json"),
        (delivery_root / "checksums.sha256", "mainbase-ranker-checksums.sha256"),
        (args.java_root / args.java_version_report, "java-ranker-version-report.json"),
        (args.java_root / args.java_events, "java-ranker-events.jsonl"),
    ):
        shutil.copy2(source, frozen / name)
    print(json.dumps({
        "promotionStatus": snapshot["ranker"]["promotionStatus"],
        "bundleDigest": snapshot["ranker"]["bundleDigest"],
        "artifactIntegrityReady": snapshot["artifactIntegrity"]["ready"],
        "reviewSubmittedCount": snapshot["ranker"]["reviewSubmittedCount"],
        "finalSelectedMutationCount": snapshot["ranker"]["finalSelectedMutationCount"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
