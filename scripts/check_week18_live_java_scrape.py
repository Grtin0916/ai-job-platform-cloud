#!/usr/bin/env python3
"""Validate a live Prometheus scrape of the Java Week18 lifecycle service."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


JOB_NAME = "week18-java-lifecycle-live"

EXPECTED_VALUES = {
    "missing_asset": 0.0,
    "repair_applied": 6.0,
    "repair_required": 6.0,
    "result_bound": 12.0,
    "task_total": 12.0,
    "winner_succeeded": 6.0,
}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")

    return value


def find_target(
    targets_data: dict[str, Any],
) -> dict[str, Any] | None:
    targets = (
        targets_data
        .get("data", {})
        .get("activeTargets", [])
    )

    for target in targets:
        labels = target.get("labels", {})

        if labels.get("job") == JOB_NAME:
            return target

    return None


def extract_values(
    query_data: dict[str, Any],
) -> dict[str, float]:
    if query_data.get("status") != "success":
        return {}

    results = (
        query_data
        .get("data", {})
        .get("result", [])
    )

    values: dict[str, float] = {}

    for item in results:
        metric = item.get("metric", {})
        category = metric.get("category")
        value = item.get("value", [])

        if (
            isinstance(category, str)
            and isinstance(value, list)
            and len(value) == 2
        ):
            values[category] = float(value[1])

    return values


def values_match(
    actual: dict[str, float],
    expected: dict[str, float],
) -> bool:
    if set(actual) != set(expected):
        return False

    return all(
        math.isclose(
            actual[key],
            expected[key],
            rel_tol=0.0,
            abs_tol=1e-9,
        )
        for key in expected
    )


def build_summary(
    targets_path: Path,
    query_path: Path,
) -> dict[str, Any]:
    targets_data = load_json(targets_path)
    query_data = load_json(query_path)

    target = find_target(targets_data)
    values = extract_values(query_data)

    target_health = (
        target.get("health")
        if target is not None
        else None
    )
    target_last_error = (
        target.get("lastError")
        if target is not None
        else "target not found"
    )
    scrape_url = (
        target.get("scrapeUrl")
        if target is not None
        else None
    )

    target_passed = (
        target is not None
        and target_health == "up"
        and not target_last_error
    )
    values_passed = values_match(
        values,
        EXPECTED_VALUES,
    )

    gate_status = (
        "PASS"
        if target_passed and values_passed
        else "FAIL"
    )

    return {
        "gateStatus": gate_status,
        "jobName": JOB_NAME,
        "targetHealth": target_health,
        "targetLastError": target_last_error,
        "scrapeUrl": scrape_url,
        "seriesCount": len(values),
        "values": values,
        "expected": EXPECTED_VALUES,
        "targetPassed": target_passed,
        "valuesPassed": values_passed,
        "localLiveScrapeVerified": gate_status == "PASS",
        "productionPrometheusVerified": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--targets",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--query",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--summary",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    summary = build_summary(
        targets_path=args.targets,
        query_path=args.query,
    )

    args.summary.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    args.summary.write_text(
        json.dumps(
            summary,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    if not args.quiet:
        print(
            json.dumps(
                summary,
                sort_keys=True,
            )
        )

    return 0 if summary["gateStatus"] == "PASS" else 3


if __name__ == "__main__":
    raise SystemExit(main())