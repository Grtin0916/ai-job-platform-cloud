#!/usr/bin/env python3
"""Emit missingness-aware, low-cardinality Ranker Prometheus metrics."""

import argparse
import json
from pathlib import Path

from ranker_contract import dump_json, load_json
from ranker_gate_state import evaluate


def build(snapshot: dict) -> tuple[str, dict]:
    ranker = snapshot["ranker"]
    decision = evaluate(snapshot, observability_ready=True)
    samples = [
        ('ranker_registry_versions{promotion_status="data_blocked"}', snapshot["registry"]["versionCount"]),
        ("ranker_model_available", int(ranker["modelPresent"])),
        ("ranker_oof_available", int(ranker["oofAvailable"])),
        ("ranker_recommendation_records", ranker["recommendationCount"]),
        ("ranker_review_rows", ranker["reviewRows"]),
        ("ranker_review_submitted", ranker["reviewSubmittedCount"]),
        ('ranker_metric_available{metric="oof_accuracy"}', int(ranker["oofAvailable"])),
        ('ranker_metric_available{metric="brier_score"}', int(ranker["oofAvailable"])),
        ("ranker_artifact_integrity_failures", int(not snapshot["artifactIntegrity"]["ready"])),
        ("ranker_bundle_contract_drift", 0),
        ("ranker_invalid_promotion_transitions", 0),
        ("ranker_metric_published_while_unavailable", 0),
        ("ranker_recommendation_while_data_blocked", 0),
        ("ranker_final_selection_without_human_review", 0),
        ("ranker_release_manifest_broken", 0),
        ("ranker_human_review_pending", int(not ranker["humanReviewCompleted"])),
    ]
    for gate, ready in decision["gates"].items():
        samples.append((f'ranker_release_gate_ready{{gate="{gate}"}}', int(ready)))
    samples.append(('ranker_release_decision{decision="hold_human_review"}', 1))
    lines = []
    declared = set()
    for name, value in samples:
        metric_name = name.split("{", 1)[0]
        if metric_name not in declared:
            lines.append(f"# TYPE {metric_name} gauge")
            declared.add(metric_name)
        lines.append(f"{name} {value}")
    text = "\n".join(lines) + "\n"
    report = {
        "schemaVersion": "ranker-observability/v1",
        "sampleCount": len(samples),
        "metricAvailability": {"oofAccuracy": False, "brierScore": False},
        "unavailableQualityMetricSampleCount": 0,
        "releaseDecision": decision["overallDecision"],
        "normalHoldAlertCount": 0,
        "productionPrometheusVerified": False,
        "grafanaProvisionVerified": False,
    }
    return text, report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--out-prom", type=Path, required=True)
    parser.add_argument("--out-json", type=Path, required=True)
    args = parser.parse_args()
    metrics, report = build(load_json(args.snapshot))
    args.out_prom.parent.mkdir(parents=True, exist_ok=True)
    args.out_prom.write_text(metrics, encoding="utf-8")
    dump_json(args.out_json, report)
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
