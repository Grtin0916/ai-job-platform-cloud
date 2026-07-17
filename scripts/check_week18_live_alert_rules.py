#!/usr/bin/env python3
"""Check live Prometheus Week18 alert rule state."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


EXPECTED_ALERTS = {
    "Week18LifecycleTargetDown",
    "Week18LifecycleResultBindingGap",
    "Week18LifecycleMissingAsset",
    "Week18LifecycleRepairIncomplete",
}


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(data, dict):
        raise ValueError("Rules API root must be an object")

    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rules", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    data = load_json(args.rules)

    discovered: dict[str, dict[str, Any]] = {}

    for group in data.get("data", {}).get("groups", []):
        for rule in group.get("rules", []):
            name = rule.get("name")

            if name in EXPECTED_ALERTS:
                discovered[name] = {
                    "state": rule.get("state"),
                    "health": rule.get("health"),
                    "lastError": rule.get("lastError", ""),
                    "activeAlertCount": len(rule.get("alerts", [])),
                    "query": rule.get("query"),
                }

    missing = sorted(EXPECTED_ALERTS - set(discovered))

    unhealthy = sorted(
        name
        for name, rule in discovered.items()
        if rule["health"] != "ok"
        or bool(rule["lastError"])
    )

    non_inactive = sorted(
        name
        for name, rule in discovered.items()
        if rule["state"] != "inactive"
        or rule["activeAlertCount"] != 0
    )

    passed = (
        not missing
        and not unhealthy
        and not non_inactive
        and len(discovered) == len(EXPECTED_ALERTS)
    )

    summary = {
        "gateStatus": "PASS" if passed else "FAIL",
        "expectedRuleCount": len(EXPECTED_ALERTS),
        "loadedRuleCount": len(discovered),
        "missingRules": missing,
        "unhealthyRules": unhealthy,
        "nonInactiveRules": non_inactive,
        "rules": discovered,
        "healthyInputExpected": True,
        "localLiveAlertRulesVerified": passed,
        "alertmanagerConfigured": False,
        "productionAlertingVerified": False,
    }

    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(summary, sort_keys=True))

    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())