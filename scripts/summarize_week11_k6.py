#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any


ROOT = Path(".")
REPORT_DIR = ROOT / "loadtest/reports"
OUT_JSON = REPORT_DIR / "week11_k6_slo_summary.json"
OUT_MD = ROOT / "docs/benchmarks/cloud_k6_week11.md"


def load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        x = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(x) or math.isinf(x):
        return None
    return x


def metric_value(report: dict[str, Any], metric_name: str, key: str) -> float | None:
    metrics = report.get("metrics", {})
    if not isinstance(metrics, dict):
        return None
    item = metrics.get(metric_name, {})
    if not isinstance(item, dict):
        return None

    # k6 handleSummary JSON often stores values under metric.values.
    values = item.get("values")
    if isinstance(values, dict) and key in values:
        return as_float(values.get(key))

    # Some custom summaries flatten fields directly.
    if key in item:
        return as_float(item.get(key))

    return None


def discover_reports() -> list[Path]:
    if not REPORT_DIR.exists():
        return []
    reports = []
    for p in REPORT_DIR.glob("*.json"):
        if p.name == OUT_JSON.name:
            continue
        if "week11" not in p.name.lower() and "k6" not in p.name.lower():
            continue
        reports.append(p)
    return sorted(reports)


def classify_report(path: Path, report: dict[str, Any]) -> str:
    name = path.name.lower()
    text = json.dumps(report, ensure_ascii=False).lower()

    if "boundary" in name or "negative" in name or "invalid" in name or "400" in text:
        return "boundary_smoke"
    if "auth" in name or "authenticated" in name or "business" in name or "created" in text:
        return "business_smoke"
    if "infra" in name or "health" in name or "metrics" in name:
        return "infra_smoke"
    return "unknown_smoke"


def extract_report_summary(path: Path, report: dict[str, Any]) -> dict[str, Any]:
    http_req_failed_rate = metric_value(report, "http_req_failed", "rate")
    http_req_duration_p95 = (
        metric_value(report, "http_req_duration", "p(95)")
        or metric_value(report, "http_req_duration", "p95")
    )
    checks_rate = metric_value(report, "checks", "rate")

    # k6 summary may expose root_state/test status differently across custom exporters.
    thresholds = report.get("thresholds", {})
    root_thresholds = {}
    if isinstance(thresholds, dict):
        for k, v in thresholds.items():
            root_thresholds[str(k)] = v

    report_passed = True
    failed_reasons: list[str] = []

    if http_req_failed_rate is not None and http_req_failed_rate > 0:
        report_passed = False
        failed_reasons.append("http_req_failed_rate_gt_0")

    if checks_rate is not None and checks_rate < 1:
        report_passed = False
        failed_reasons.append("checks_rate_lt_1")

    # Smoke gate: local p95 should remain below 200ms when present.
    if http_req_duration_p95 is not None and http_req_duration_p95 >= 200:
        report_passed = False
        failed_reasons.append("p95_ge_200ms")

    return {
        "file": str(path),
        "kind": classify_report(path, report),
        "http_req_failed_rate": http_req_failed_rate,
        "http_req_duration_p95_ms": http_req_duration_p95,
        "checks_rate": checks_rate,
        "threshold_keys": sorted(root_thresholds.keys()),
        "passed_local_smoke_gate": report_passed,
        "failed_reasons": failed_reasons,
    }


def aggregate(report_summaries: list[dict[str, Any]]) -> dict[str, Any]:
    p95_values = [
        r["http_req_duration_p95_ms"]
        for r in report_summaries
        if isinstance(r.get("http_req_duration_p95_ms"), (int, float))
    ]
    failed_rates = [
        r["http_req_failed_rate"]
        for r in report_summaries
        if isinstance(r.get("http_req_failed_rate"), (int, float))
    ]
    checks_rates = [
        r["checks_rate"]
        for r in report_summaries
        if isinstance(r.get("checks_rate"), (int, float))
    ]

    kinds = {}
    for r in report_summaries:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1

    all_passed = bool(report_summaries) and all(r["passed_local_smoke_gate"] for r in report_summaries)

    return {
        "report_count": len(report_summaries),
        "report_kinds": kinds,
        "all_reports_passed_local_smoke_gate": all_passed,
        "max_p95_ms": max(p95_values) if p95_values else None,
        "max_http_req_failed_rate": max(failed_rates) if failed_rates else None,
        "min_checks_rate": min(checks_rates) if checks_rates else None,
        "local_gate_rule": {
            "http_req_failed_rate": "must equal 0 when present",
            "checks_rate": "must equal 1 when present",
            "http_req_duration_p95_ms": "must be < 200ms when present",
            "scope": "local week11 smoke evidence only; not a production SLO",
        },
    }


def write_markdown(payload: dict[str, Any]) -> None:
    agg = payload["aggregate"]
    lines = [
        "# Week11 Cloud k6 SLO Summary",
        "",
        "## Scope",
        "",
        "This document summarizes existing Week11 k6 reports into a local smoke reliability gate. It does not claim production SLO coverage.",
        "",
        "## Aggregate",
        "",
        f"- Report count: {agg['report_count']}",
        f"- Report kinds: `{agg['report_kinds']}`",
        f"- All reports passed local smoke gate: `{agg['all_reports_passed_local_smoke_gate']}`",
        f"- Max p95 latency ms: `{agg['max_p95_ms']}`",
        f"- Max http_req_failed rate: `{agg['max_http_req_failed_rate']}`",
        f"- Min checks rate: `{agg['min_checks_rate']}`",
        "",
        "## Local Gate Rule",
        "",
        "- `http_req_failed_rate == 0` when present.",
        "- `checks_rate == 1` when present.",
        "- `http_req_duration p95 < 200ms` when present.",
        "- Boundary/negative smoke may intentionally receive HTTP 400, but it must be configured as an expected status in k6 so `http_req_failed` remains zero.",
        "",
        "## Reports",
        "",
        "| file | kind | p95_ms | failed_rate | checks_rate | passed | failed_reasons |",
        "|---|---|---:|---:|---:|---|---|",
    ]

    for r in payload["reports"]:
        lines.append(
            "| {file} | {kind} | {p95} | {failed} | {checks} | {passed} | {reasons} |".format(
                file=r["file"],
                kind=r["kind"],
                p95=r["http_req_duration_p95_ms"],
                failed=r["http_req_failed_rate"],
                checks=r["checks_rate"],
                passed=r["passed_local_smoke_gate"],
                reasons=",".join(r["failed_reasons"]) if r["failed_reasons"] else "none",
            )
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "Week11 evidence shows whether the local Java task query path can be consumed by k6 under authenticated and/or boundary smoke conditions. This summary is a decision artifact for W11/W12 demo preparation, not a substitute for long-running load tests or production alerting.",
            "",
        ]
    )

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    paths = discover_reports()
    report_summaries: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    for path in paths:
        report = load_json(path)
        if not isinstance(report, dict):
            skipped.append({"file": str(path), "reason": "not_valid_json_object"})
            continue
        report_summaries.append(extract_report_summary(path, report))

    payload = {
        "schema_version": "week11_k6_slo_summary_v0",
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "scope": "Cloud-side summary of existing Week11 k6 reports. Local smoke gate only; not production SLO.",
        "reports": report_summaries,
        "skipped": skipped,
        "aggregate": aggregate(report_summaries),
        "next_recommendation": (
            "If aggregate passes, bind this summary back into Mainbase bridge evidence; "
            "if not, inspect failed report kind before rerunning Java/k6."
        ),
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_markdown(payload)

    print(f"[OK] wrote {OUT_JSON}")
    print(f"[OK] wrote {OUT_MD}")
    print("report_count=", payload["aggregate"]["report_count"])
    print("all_reports_passed_local_smoke_gate=", payload["aggregate"]["all_reports_passed_local_smoke_gate"])
    print("report_kinds=", payload["aggregate"]["report_kinds"])

    if payload["aggregate"]["report_count"] == 0:
        raise SystemExit("[FAIL] no k6 JSON reports discovered under loadtest/reports")


if __name__ == "__main__":
    main()