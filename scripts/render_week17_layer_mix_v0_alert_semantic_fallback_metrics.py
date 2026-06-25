#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path.cwd()

FALLBACK_REPORT = ROOT / "loadtest/reports/week17_layer_mix_v0_action_gate_alert_rules_semantic_fallback_report.json"
SOURCE_REPORT = ROOT / "loadtest/reports/week17_layer_mix_v0_action_gate_alert_rules_report.json"

METRICS_FILE = ROOT / "observability/prometheus/week17_layer_mix_v0_action_gate_alert_semantic_fallback.prom"
METRICS_REPORT = ROOT / "loadtest/reports/week17_layer_mix_v0_alert_semantic_fallback_metrics_report.json"

EXPECTED_DECISION = "PARTIAL_WEEK17_LAYER_MIX_V0_ALERT_RULES_PROMTOOL_BLOCKED_LOCAL_SEMANTIC_PASS"
EXPECTED_VALIDATOR_VERSION = "v3_structural_semantic_contract_safe_promtool_boundary"

BLOCKED_CLAIMS = [
    "no_promtool_pass_claim",
    "no_production_alerting_claim",
    "no_alertmanager_routing_claim",
    "no_production_paging_claim",
    "no_live_prometheus_scrape_claim",
    "no_production_slo_claim",
]


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing required file: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def bool01(value: Any) -> int:
    return 1 if value is True else 0


def sanitize_label_value(value: Any) -> str:
    text = str(value)
    text = text.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')
    return text


def metric_line(name: str, value: int | float, labels: dict[str, Any] | None = None) -> str:
    labels = labels or {}
    if labels:
        label_text = ",".join(f'{k}="{sanitize_label_value(v)}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_text}}} {value}"
    return f"{name} {value}"


def validate_prom_text(text: str) -> list[str]:
    errors: list[str] = []
    help_seen: set[str] = set()
    type_seen: set[str] = set()

    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue

        if line.startswith("# HELP "):
            parts = line.split(maxsplit=3)
            if len(parts) < 4:
                errors.append(f"line {line_no}: malformed HELP line")
                continue
            metric = parts[2]
            if metric in help_seen:
                errors.append(f"line {line_no}: duplicate HELP for {metric}")
            help_seen.add(metric)
            continue

        if line.startswith("# TYPE "):
            parts = line.split()
            if len(parts) != 4:
                errors.append(f"line {line_no}: malformed TYPE line")
                continue
            metric = parts[2]
            if metric in type_seen:
                errors.append(f"line {line_no}: duplicate TYPE for {metric}")
            type_seen.add(metric)
            continue

        if line.startswith("#"):
            continue

        if not re.match(r"^[a-zA-Z_:][a-zA-Z0-9_:]*(\{[^{}]*\})?\s+[-+]?[0-9]+(\.[0-9]+)?$", line):
            errors.append(f"line {line_no}: malformed metric sample: {line}")

    missing_type = sorted(help_seen - type_seen)
    missing_help = sorted(type_seen - help_seen)
    for metric in missing_type:
        errors.append(f"missing TYPE for {metric}")
    for metric in missing_help:
        errors.append(f"missing HELP for {metric}")

    if not text.endswith("\n"):
        errors.append("metrics file must end with newline")

    return errors


def main() -> int:
    generated_at = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")

    fallback = load_json(FALLBACK_REPORT)
    source = load_json(SOURCE_REPORT)

    decision = fallback.get("decision")
    validator_version = fallback.get("validatorVersion")
    promtool_blocked = fallback.get("promtoolBlocked")
    semantic_passed = fallback.get("semanticFallbackPassed")
    unsafe_claim = fallback.get("unsafePromtoolPassClaimDetected")
    failed_checks = fallback.get("failedChecks", [])
    alert_names = fallback.get("alertNames", [])
    blocked_claims = fallback.get("blockedClaims", [])

    guard_errors: list[str] = []
    if decision != EXPECTED_DECISION:
        guard_errors.append(f"unexpected decision: {decision}")
    if validator_version != EXPECTED_VALIDATOR_VERSION:
        guard_errors.append(f"unexpected validatorVersion: {validator_version}")
    if promtool_blocked is not True:
        guard_errors.append(f"promtoolBlocked must be true, got {promtool_blocked}")
    if semantic_passed is not True:
        guard_errors.append(f"semanticFallbackPassed must be true, got {semantic_passed}")
    if unsafe_claim is not False:
        guard_errors.append(f"unsafePromtoolPassClaimDetected must be false, got {unsafe_claim}")
    if failed_checks != []:
        guard_errors.append(f"failedChecks must be [], got {failed_checks}")

    labels = {
        "scope": "week17_layer_mix_v0_action_gate_alert_rules",
        "validator_version": validator_version,
        "decision": decision,
    }

    metric_blocks = [
        (
            "week17_layer_mix_v0_alert_semantic_fallback_pass",
            "Whether local semantic fallback passed for Week17 layer mix v0 alert rules.",
            [
                metric_line(
                    "week17_layer_mix_v0_alert_semantic_fallback_pass",
                    bool01(semantic_passed),
                    labels,
                )
            ],
        ),
        (
            "week17_layer_mix_v0_alert_promtool_blocked",
            "Whether official promtool validation is blocked by local environment.",
            [
                metric_line(
                    "week17_layer_mix_v0_alert_promtool_blocked",
                    bool01(promtool_blocked),
                    labels,
                )
            ],
        ),
        (
            "week17_layer_mix_v0_alert_unsafe_promtool_pass_claim",
            "Whether an unsafe affirmative promtool pass claim was detected.",
            [
                metric_line(
                    "week17_layer_mix_v0_alert_unsafe_promtool_pass_claim",
                    bool01(unsafe_claim),
                    labels,
                )
            ],
        ),
        (
            "week17_layer_mix_v0_alert_failed_checks_total",
            "Number of failed local semantic fallback checks.",
            [
                metric_line(
                    "week17_layer_mix_v0_alert_failed_checks_total",
                    len(failed_checks),
                    labels,
                )
            ],
        ),
        (
            "week17_layer_mix_v0_alert_rules_total",
            "Number of alert rules visible in local semantic fallback evidence.",
            [
                metric_line(
                    "week17_layer_mix_v0_alert_rules_total",
                    len(alert_names),
                    labels,
                )
            ],
        ),
        (
            "week17_layer_mix_v0_alert_blocked_claims_total",
            "Number of explicitly blocked production or promtool claims.",
            [
                metric_line(
                    "week17_layer_mix_v0_alert_blocked_claims_total",
                    len(blocked_claims),
                    labels,
                )
            ],
        ),
        (
            "week17_layer_mix_v0_alert_blocked_claim_present",
            "Blocked claim presence by claim name.",
            [
                metric_line(
                    "week17_layer_mix_v0_alert_blocked_claim_present",
                    1,
                    {**labels, "claim": claim},
                )
                for claim in blocked_claims
            ],
        ),
    ]

    lines: list[str] = []
    for name, help_text, samples in metric_blocks:
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} gauge")
        lines.extend(samples)

    metrics_text = "\n".join(lines) + "\n"
    metric_errors = validate_prom_text(metrics_text)

    metrics_ready = not guard_errors and not metric_errors

    report = {
        "decision": (
            "PASS_WEEK17_LAYER_MIX_V0_ALERT_SEMANTIC_FALLBACK_METRICS_READY"
            if metrics_ready
            else "FAIL_WEEK17_LAYER_MIX_V0_ALERT_SEMANTIC_FALLBACK_METRICS_READY"
        ),
        "generatedAtUtc": generated_at,
        "metricsReady": metrics_ready,
        "sourceFallbackReport": str(FALLBACK_REPORT.relative_to(ROOT)),
        "sourceAlertRulesReport": str(SOURCE_REPORT.relative_to(ROOT)),
        "metricsFile": str(METRICS_FILE.relative_to(ROOT)),
        "guardErrors": guard_errors,
        "metricFormatErrors": metric_errors,
        "sourceDecision": decision,
        "validatorVersion": validator_version,
        "promtoolBlocked": promtool_blocked,
        "semanticFallbackPassed": semantic_passed,
        "unsafePromtoolPassClaimDetected": unsafe_claim,
        "failedChecksTotal": len(failed_checks),
        "alertRulesTotal": len(alert_names),
        "blockedClaims": blocked_claims or BLOCKED_CLAIMS,
        "blockedClaimsPreserved": all(claim in (blocked_claims or []) for claim in BLOCKED_CLAIMS),
        "blockedOperationalClaims": [
            "no_official_promtool_pass",
            "no_live_prometheus_scrape",
            "no_alertmanager_routing",
            "no_production_paging",
            "no_production_slo",
        ],
        "sourceReportDecision": source.get("decision"),
        "notes": [
            "This metrics file is metrics-ready evidence only.",
            "It does not claim live Prometheus scrape.",
            "It does not claim official promtool pass.",
            "It does not claim production alerting or Alertmanager routing.",
        ],
    }

    METRICS_FILE.parent.mkdir(parents=True, exist_ok=True)
    METRICS_FILE.write_text(metrics_text, encoding="utf-8")

    METRICS_REPORT.parent.mkdir(parents=True, exist_ok=True)
    METRICS_REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")

    print(json.dumps({
        "decision": report["decision"],
        "metricsReady": metrics_ready,
        "metricsFile": report["metricsFile"],
        "metricsReport": str(METRICS_REPORT.relative_to(ROOT)),
        "guardErrors": guard_errors,
        "metricFormatErrors": metric_errors,
        "alertRulesTotal": len(alert_names),
        "blockedClaimsTotal": len(blocked_claims),
    }, indent=2, ensure_ascii=False, sort_keys=True))

    return 0 if metrics_ready else 2


if __name__ == "__main__":
    raise SystemExit(main())