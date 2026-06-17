#!/usr/bin/env python3
import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

def parse_metric_value(metrics_text, metric_name):
    pattern = re.compile(rf"^{re.escape(metric_name)}\{{[^}}]*\}}\s+([-+]?\d+(?:\.\d+)?)$", re.MULTILINE)
    m = pattern.search(metrics_text)
    if not m:
        raise ValueError(f"missing metric: {metric_name}")
    value = float(m.group(1))
    if value.is_integer():
        return int(value)
    return value

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", default="loadtest/reports/week15_temporal_alignment_review_state_registry_backed_platform_index.json")
    parser.add_argument("--metrics", default="observability/prometheus/week15_temporal_alignment_review_state_registry_backed_metrics.prom")
    parser.add_argument("--out", default="loadtest/reports/week15_temporal_alignment_review_state_registry_backed_platform_gate.json")
    args = parser.parse_args()

    index_path = Path(args.index)
    metrics_path = Path(args.metrics)
    out_path = Path(args.out)

    if not index_path.exists():
        raise SystemExit(f"missing index: {index_path}")
    if not metrics_path.exists():
        raise SystemExit(f"missing metrics: {metrics_path}")

    index = json.loads(index_path.read_text(encoding="utf-8"))
    metrics_text = metrics_path.read_text(encoding="utf-8")

    values = {
        "platform_pass": parse_metric_value(metrics_text, "week15_temporal_alignment_review_state_registry_backed_platform_pass"),
        "claim_boundary_ok": parse_metric_value(metrics_text, "week15_temporal_alignment_review_state_claim_boundary_ok"),
        "required_risk_candidate_present": parse_metric_value(metrics_text, "week15_temporal_alignment_review_state_required_risk_candidate_present"),
        "random_port_compatibility_checked": parse_metric_value(metrics_text, "week15_temporal_alignment_review_state_random_port_compatibility_checked"),
        "risk_candidate_count": parse_metric_value(metrics_text, "week15_temporal_alignment_review_state_risk_candidate_count"),
    }

    risk_ids = index.get("riskCandidateIds") or []
    random_port_status = index.get("randomPortCompatibilityBoundary", {}).get("status")

    checks = {
        "platform_decision_pass": index.get("platformDecision") == "PASS_JAVA_REGISTRY_BACKED_REVIEW_STATE_PLATFORM_CONSUMPTION",
        "claim_boundary_index_true": index.get("claimBoundaryOk") is True,
        "required_risk_index_true": index.get("requiredRiskCandidatePresent") is True,
        "required_candidate_id_present": "procedural_v0_0004" in risk_ids,
        "random_port_deferred_carried": random_port_status == "DEFERRED_TERMINAL_SESSION_CRASHED_TWICE",
        "java_source_snapshot_recorded": bool(index.get("sourceSnapshot", {}).get("javaRepoHeadAtConsumption")),
        "java_report_sha256_recorded": len(index.get("sourceSnapshot", {}).get("javaReportSha256", "")) == 64,
        "metric_platform_pass_matches": values["platform_pass"] == 1,
        "metric_claim_boundary_matches": values["claim_boundary_ok"] == 1,
        "metric_required_risk_matches": values["required_risk_candidate_present"] == 1,
        "metric_random_port_checked_matches_boundary": values["random_port_compatibility_checked"] == 0,
        "metric_risk_candidate_count_matches_index": values["risk_candidate_count"] == len(risk_ids),
    }

    decision = "PASS_WEEK15_REGISTRY_BACKED_PLATFORM_GATE" if all(checks.values()) else "FAIL_WEEK15_REGISTRY_BACKED_PLATFORM_GATE"

    report = {
        "schemaVersion": "week15.cloud.temporal-alignment-review-state.registry-backed-platform-gate.v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "indexPath": str(index_path),
        "metricsPath": str(metrics_path),
        "platformDecision": index.get("platformDecision"),
        "riskCandidateIds": risk_ids,
        "randomPortCompatibilityStatus": random_port_status,
        "metricValues": values,
        "checks": checks,
        "claimBoundary": {
            "cloudClaim": index.get("randomPortCompatibilityBoundary", {}).get("platformClaim"),
            "randomPortCompatibilityCheckedMetric": values["random_port_compatibility_checked"],
        },
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    if decision != "PASS_WEEK15_REGISTRY_BACKED_PLATFORM_GATE":
        raise SystemExit(4)

if __name__ == "__main__":
    main()
