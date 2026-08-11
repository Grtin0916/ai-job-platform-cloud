#!/usr/bin/env python3
"""Evaluate and serialize the W21 monotonic Ranker release gate."""

import argparse
import csv
import json
from pathlib import Path

from ranker_contract import dump_json, load_json
from ranker_gate_state import evaluate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--out-csv", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(load_json(args.snapshot))
    report = {"schemaVersion": "ranker-release-gate/v1", "baselineDecision": result["overallDecision"], **result}
    dump_json(args.out_json, report)
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.out_csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=["gate", "ready"], lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows({"gate": gate, "ready": ready} for gate, ready in result["gates"].items())
    print(json.dumps({"baselineDecision": report["baselineDecision"], "gates": report["gates"]}, sort_keys=True))


if __name__ == "__main__":
    main()
