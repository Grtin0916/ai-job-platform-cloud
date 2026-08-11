#!/usr/bin/env python3
"""Validate W21 metric labels and missingness semantics."""

import argparse
import json
import re
from pathlib import Path

from ranker_contract import dump_json

FORBIDDEN = {"rankerVersion", "caseId", "case_id", "pairId", "pair_id", "reviewerId", "sha", "path", "timestamp"}
LABEL_RE = re.compile(r"\{([^}]*)\}")


def validate(text: str) -> dict:
    label_names = set()
    for labels in LABEL_RE.findall(text):
        for part in labels.split(","):
            if "=" in part:
                label_names.add(part.split("=", 1)[0].strip())
    forbidden = sorted(label_names & FORBIDDEN)
    unavailable = 'ranker_metric_available{metric="oof_accuracy"} 0' in text
    leaked_quality = any(
        re.search(rf"^{name}(?:\{{|\s)", text, re.MULTILINE)
        for name in ("ranker_oof_accuracy", "ranker_brier_score")
    )
    return {
        "schemaVersion": "ranker-metric-cardinality/v1",
        "valid": not forbidden and unavailable and not leaked_quality,
        "labelNames": sorted(label_names),
        "forbiddenLabelCount": len(forbidden),
        "forbiddenLabels": forbidden,
        "unavailableMetricsRepresentedByAvailabilityOnly": unavailable and not leaked_quality,
        "qualityMetricPublishedWhileUnavailableCount": int(leaked_quality),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    report = validate(args.metrics.read_text(encoding="utf-8"))
    dump_json(args.out, report)
    print(json.dumps(report, sort_keys=True))
    raise SystemExit(0 if report["valid"] else 1)


if __name__ == "__main__":
    main()
