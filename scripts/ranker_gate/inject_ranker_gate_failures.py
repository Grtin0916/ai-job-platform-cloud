#!/usr/bin/env python3
"""Inject four prohibited Ranker release transitions and prove detection."""

import argparse
import json
from pathlib import Path

from ranker_contract import dump_json, load_json
from ranker_gate_state import evaluate, injected

EXPECTED = {
    "blocked_contains_recommendations": "BLOCK_CONTRACT_DRIFT",
    "blocked_contains_model": "BLOCK_INVALID_PROMOTION",
    "final_without_human_review": "BLOCK_HUMAN_GATE_VIOLATION",
    "bundle_digest_mismatch": "BLOCK_ARTIFACT_INTEGRITY",
}


def run(snapshot: dict) -> dict:
    cases = []
    for scenario, expected in EXPECTED.items():
        actual = evaluate(injected(snapshot, scenario))["overallDecision"]
        cases.append({"scenario": scenario, "expectedDecision": expected, "actualDecision": actual, "detected": actual == expected})
    return {
        "schemaVersion": "ranker-gate-fault-injection/v1",
        "faultInjectionCount": len(cases),
        "faultDetectionCount": sum(item["detected"] for item in cases),
        "falsePromotionCount": sum(item["actualDecision"] == "PROMOTE" for item in cases),
        "finalSelectedMutationCount": 0,
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = run(load_json(args.snapshot))
    dump_json(args.out, report)
    print(json.dumps(report, sort_keys=True))
    raise SystemExit(0 if report["faultDetectionCount"] == 4 else 1)


if __name__ == "__main__":
    main()
