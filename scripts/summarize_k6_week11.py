#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"input JSON not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"input JSON root must be object: {path}")
    return data


def metric_obj(data: dict[str, Any], name: str) -> dict[str, Any]:
    obj = data.get("metrics", {}).get(name, {})
    return obj if isinstance(obj, dict) else {}


def metric_value(data: dict[str, Any], name: str, keys: list[str]) -> float | None:
    obj = metric_obj(data, name)

    values = obj.get("values")
    if isinstance(values, dict):
        for key in keys:
            val = values.get(key)
            if isinstance(val, (int, float)) and math.isfinite(float(val)):
                return float(val)

    for key in keys:
        val = obj.get(key)
        if isinstance(val, (int, float)) and math.isfinite(float(val)):
            return float(val)

    return None


def thresholds_status(data: dict[str, Any]) -> tuple[bool | None, list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    overall: bool | None = None

    metrics = data.get("metrics", {})
    if not isinstance(metrics, dict):
        return None, rows

    for metric_name, metric in metrics.items():
        if not isinstance(metric, dict):
            continue

        thresholds = metric.get("thresholds")
        if not isinstance(thresholds, dict):
            continue

        for expr, meta in thresholds.items():
            ok = None
            if isinstance(meta, dict) and isinstance(meta.get("ok"), bool):
                ok = meta["ok"]

            rows.append({
                "metric": metric_name,
                "threshold": expr,
                "ok": ok,
            })

            if ok is not None:
                overall = ok if overall is None else (overall and ok)

    return overall, rows


def result_text(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--out-json", required=True)
    parser.add_argument("--out-md", required=True)
    parser.add_argument("--max-p95-ms", type=float, default=750.0)
    parser.add_argument("--max-failed-rate", type=float, default=0.0)
    parser.add_argument("--min-check-rate", type=float, default=1.0)
    parser.add_argument("--expected-task-id", default="week11-k6-seed-created-001")
    parser.add_argument("--java-commit", default="8bf3971")
    parser.add_argument("--cloud-commit", default="d03f9fb")
    args = parser.parse_args()

    input_path = Path(args.input)
    out_json = Path(args.out_json)
    out_md = Path(args.out_md)

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)

    data = load_json(input_path)

    failed_rate = metric_value(data, "http_req_failed", ["rate", "value"])
    p95_ms = metric_value(data, "http_req_duration", ["p(95)", "p95", "95"])
    check_rate = metric_value(data, "checks", ["rate", "value"])
    checks_passes = metric_value(data, "checks", ["passes"])
    checks_fails = metric_value(data, "checks", ["fails"])
    threshold_overall, threshold_rows = thresholds_status(data)

    failures: list[str] = []

    if failed_rate is None:
        failures.append("missing http_req_failed rate")
    elif failed_rate > args.max_failed_rate:
        failures.append(f"http_req_failed rate {failed_rate} > {args.max_failed_rate}")

    if p95_ms is None:
        failures.append("missing http_req_duration p95")
    elif p95_ms >= args.max_p95_ms:
        failures.append(f"http_req_duration p95 {p95_ms} >= {args.max_p95_ms} ms")

    if check_rate is None:
        failures.append("missing checks rate")
    elif check_rate < args.min_check_rate:
        failures.append(f"checks rate {check_rate} < {args.min_check_rate}")

    if threshold_overall is False:
        failures.append("one or more native k6 thresholds failed")

    passed = len(failures) == 0
    native_threshold_note = "not detected in source summary JSON" if threshold_overall is None else str(threshold_overall)

    summary = {
        "schema_version": "week11_k6_gate_v2",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_summary_json": str(input_path),
        "expected_task_id": args.expected_task_id,
        "java_repo_commit": args.java_commit,
        "cloud_repo_commit": args.cloud_commit,
        "gate": {
            "passed": passed,
            "failure_reasons": failures,
            "max_p95_ms": args.max_p95_ms,
            "max_failed_rate": args.max_failed_rate,
            "min_check_rate": args.min_check_rate,
            "gate_type": "derived_from_k6_summary_metrics",
        },
        "metrics": {
            "http_req_failed_rate": failed_rate,
            "http_req_duration_p95_ms": p95_ms,
            "checks_rate": check_rate,
            "checks_passes": checks_passes,
            "checks_fails": checks_fails,
        },
        "thresholds": {
            "native_k6_threshold_overall": threshold_overall,
            "native_k6_threshold_note": native_threshold_note,
            "items": threshold_rows,
        },
        "interpretation": {
            "scope": "Week11 authenticated seeded media-task query smoke, not production SLO.",
            "business_meaning": (
                "The Java media-task read path can be queried under k6 smoke load "
                "and linked to the seeded task used by the cross-repo eval bridge."
            ),
            "not_verified": [
                "long-duration load",
                "multi-instance Kubernetes rollout under load",
                "database saturation",
                "production alert routing",
                "write-path task orchestration",
            ],
        },
    }

    with out_json.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
        f.write("\n")

    failed_rate_ok = failed_rate is not None and failed_rate <= args.max_failed_rate
    p95_ok = p95_ms is not None and p95_ms < args.max_p95_ms
    checks_ok = check_rate is not None and check_rate >= args.min_check_rate

    status = "PASS" if passed else "FAIL"
    failure_text = "\n".join(f"- {x}" for x in failures) if failures else "- None"

    md_lines = [
        "# Week11 Cloud k6 Benchmark Gate",
        "",
        "## Verdict",
        "",
        f"**{status}**",
        "",
        "This report summarizes the authenticated k6 smoke result for the Week11 seeded media-task query path.",
        "",
        "## Source",
        "",
        f"- Source summary JSON: {input_path}",
        f"- Expected task id: {args.expected_task_id}",
        f"- Java commit: {args.java_commit}",
        f"- Cloud commit: {args.cloud_commit}",
        f"- Generated at UTC: {summary['checked_at_utc']}",
        "",
        "## Derived Gate Criteria",
        "",
        "| Metric | Observed | Required | Result |",
        "|---|---:|---:|---|",
        f"| http_req_failed.rate | {failed_rate} | <= {args.max_failed_rate} | {result_text(failed_rate_ok)} |",
        f"| http_req_duration.p95_ms | {p95_ms} | < {args.max_p95_ms} | {result_text(p95_ok)} |",
        f"| checks.rate | {check_rate} | >= {args.min_check_rate} | {result_text(checks_ok)} |",
        "",
        "## Native k6 Threshold Status",
        "",
        f"- Native k6 threshold status in source summary: {native_threshold_note}",
        "- This report uses a Week11 derived gate because the source summary may not expose native threshold metadata in a stable shape.",
        "- The derived gate is based on observed k6 metrics: HTTP failure rate, p95 latency, and check pass rate.",
        "",
        "## Failure Reasons",
        "",
        failure_text,
        "",
        "## Interpretation Boundary",
        "",
        "This is a Week11 smoke benchmark gate. It verifies that the authenticated Java media-task read path can be queried through the k6 script and linked to the seeded task used by the cross-repo eval bridge.",
        "",
        "It does not verify production SLO, long-duration load, database saturation, multi-instance Kubernetes behavior, write-path orchestration, or real alert routing.",
        "",
        "## Machine-readable Output",
        "",
        "See artifacts/benchmarks/week11_k6_gate_summary.json for the machine-readable gate and threshold details.",
        "",
    ]

    out_md.write_text("\n".join(md_lines), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
