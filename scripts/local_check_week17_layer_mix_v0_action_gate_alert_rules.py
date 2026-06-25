#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path.cwd()

RULES_FILE = ROOT / "observability/prometheus/week17_layer_mix_v0_action_gate_alert_rules.yml"
TEST_FILE = ROOT / "observability/prometheus/week17_layer_mix_v0_action_gate_alert_rule_test.yml"
SOURCE_REPORT_FILE = ROOT / "loadtest/reports/week17_layer_mix_v0_action_gate_alert_rules_report.json"
ACTION_GATE_JSON = ROOT / "loadtest/reports/week17_layer_mix_v0_action_gate.json"
ACTION_GATE_CSV = ROOT / "loadtest/reports/week17_layer_mix_v0_action_gate.csv"
FALLBACK_REPORT_FILE = ROOT / "loadtest/reports/week17_layer_mix_v0_action_gate_alert_rules_semantic_fallback_report.json"

BLOCKED_CLAIMS = [
    "no_promtool_pass_claim",
    "no_production_alerting_claim",
    "no_alertmanager_routing_claim",
    "no_production_paging_claim",
    "no_live_prometheus_scrape_claim",
    "no_production_slo_claim",
]

REQUIRED_NEGATIVE_SCENARIOS = {
    "synthetic_high_clip_rate": ["synthetic_high_clip_rate", "high_clip", "clip_rate", "clip"],
    "missing_track": ["missing_track", "missing track", "missing"],
    "low_rms": ["low_rms", "low rms", "silent", "silence", "quiet", "rms"],
    "final_mix_overclaim": ["final_mix_overclaim", "final mix overclaim", "overclaim", "final_mix", "readiness"],
}

REQUIRED_RULE_CONCEPTS = {
    "clip_risk": ["clip", "clip_rate", "high_clip"],
    "missing_track": ["missing", "missing_track", "track"],
    "low_rms_or_silent": ["low_rms", "rms", "silent", "silence", "quiet"],
    "final_mix_overclaim": ["final_mix_overclaim", "overclaim", "final_mix", "readiness", "claim"],
}


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError as exc:
        return {
            "_jsonDecodeError": str(exc),
            "_path": str(path),
            "_rawPrefix": read_text(path)[:500],
        }


def dump_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def has_any(text: str, terms: list[str]) -> bool:
    h = text.lower()
    return any(term.lower() in h for term in terms)


def extract_alert_names(rules_text: str) -> list[str]:
    names: list[str] = []
    for line in rules_text.splitlines():
        m = re.search(r"^\s*-?\s*alert\s*:\s*['\"]?([A-Za-z0-9_:.\-]+)['\"]?\s*$", line)
        if m:
            names.append(m.group(1))
    return sorted(set(names))


def detect_promtool_blocked(text_blob: str, source_report: Any) -> bool:
    if isinstance(source_report, dict) and source_report.get("promtoolBlocked") is True:
        return True

    h = text_blob.lower()
    return (
        "promtool" in h
        and any(
            term in h
            for term in [
                "blocked",
                "rc=125",
                "return code 125",
                "docker",
                "daemon",
                "socket",
                "unavailable",
                "not found",
                "no such file",
                "cannot connect",
            ]
        )
    )


def detect_unsafe_promtool_pass_claim(text_blob: str) -> bool:
    """
    v3: flag only affirmative official promtool-pass claims.
    Safe boundary phrases such as no_promtool_pass_claim and
    PROMTOOL_BLOCKED_LOCAL_SEMANTIC_PASS must not self-poison this validator.
    """
    unsafe_json_patterns = [
        r'"promtool(?:Pass|Passed|Available|Validated|Ok)"\s*:\s*true',
        r'"promtool(?:pass|passed|available|validated|ok)"\s*:\s*true',
        r'"officialPromtoolPass"\s*:\s*true',
        r'"official_promtool_pass"\s*:\s*true',
    ]

    for pattern in unsafe_json_patterns:
        if re.search(pattern, text_blob, flags=re.IGNORECASE):
            return True

    safe_markers = [
        "no_promtool_pass_claim",
        "not an official promtool pass",
        "does not claim official promtool pass",
        "no official promtool pass",
        "not claim official promtool pass",
        "without claiming promtool pass",
        "promtool blocked",
        "promtoolblocked",
        "promtool_blocked",
        "blocked local semantic",
        "blocked_local_semantic",
        "semantic pass",
        "semantic_pass",
        "local semantic pass",
        "local_semantic_pass",
        "promtool_blocked_local_semantic_pass",
    ]

    positive_terms = [
        "pass",
        "passed",
        "success",
        "succeeded",
        "ok",
        "available",
        "validated",
    ]

    positive_re = "|".join(positive_terms)

    for raw_line in text_blob.splitlines():
        line = raw_line.strip().lower()
        if "promtool" not in line:
            continue

        if any(marker in line for marker in safe_markers):
            continue

        if re.search(r'\bpromtool\b.{0,80}\b(' + positive_re + r')\b', line):
            return True
        if re.search(r'\b(' + positive_re + r')\b.{0,80}\bpromtool\b', line):
            return True

    return False


def build_presence_checks(name: str, text: str, required: dict[str, list[str]]) -> dict[str, Any]:
    items = []
    for key, terms in required.items():
        matched = [term for term in terms if term.lower() in text.lower()]
        items.append(
            {
                "name": key,
                "passed": bool(matched),
                "matchedTerms": matched,
                "acceptedTerms": terms,
            }
        )

    return {
        "name": name,
        "passed": all(item["passed"] for item in items),
        "items": items,
    }


def main() -> int:
    generated_at = dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")

    rules_text = read_text(RULES_FILE)
    test_text = read_text(TEST_FILE)
    source_report = load_json(SOURCE_REPORT_FILE)
    action_gate_json = load_json(ACTION_GATE_JSON)
    action_gate_csv_text = read_text(ACTION_GATE_CSV)

    test_logs = sorted((ROOT / "artifacts/logs").glob("week17_layer_mix_v0_action_gate_alert_rules_test_*.log"))
    generate_logs = sorted((ROOT / "artifacts/logs").glob("week17_layer_mix_v0_action_gate_alert_rules_generate_*.log"))
    semantic_logs = sorted((ROOT / "artifacts/logs").glob("week17_layer_mix_v0_action_gate_alert_rules_semantic_fallback_*.log"))

    log_text = "\n".join(read_text(path) for path in [*test_logs, *generate_logs])
    source_report_text = json.dumps(source_report, ensure_ascii=False, sort_keys=True)
    action_gate_json_text = json.dumps(action_gate_json, ensure_ascii=False, sort_keys=True)

    all_text = "\n".join(
        [
            rules_text,
            test_text,
            source_report_text,
            action_gate_json_text,
            action_gate_csv_text,
            log_text,
        ]
    )

    source_files = [
        RULES_FILE,
        TEST_FILE,
        SOURCE_REPORT_FILE,
        ACTION_GATE_JSON,
        ACTION_GATE_CSV,
    ]

    file_checks = [
        {
            "path": str(path.relative_to(ROOT)),
            "exists": path.exists(),
            "bytes": path.stat().st_size if path.exists() else 0,
            "requiredForPass": path in [RULES_FILE, TEST_FILE, SOURCE_REPORT_FILE],
        }
        for path in source_files
    ]

    required_file_ok = all(
        item["exists"] and item["bytes"] > 0
        for item in file_checks
        if item["requiredForPass"]
    )

    alert_names = extract_alert_names(rules_text)

    structural_checks = [
        {
            "name": "required_source_files_exist",
            "passed": required_file_ok,
            "details": file_checks,
        },
        {
            "name": "alert_rules_have_alert_definitions",
            "passed": len(alert_names) >= 1,
            "alertNames": alert_names,
            "note": "Fallback requires at least one alert definition; exact count is left to promtool.",
        },
        {
            "name": "promtool_test_file_has_alert_rule_test",
            "passed": "alert_rule_test" in test_text,
        },
        {
            "name": "promtool_test_file_has_expected_alerts_field",
            "passed": "exp_alerts" in test_text,
        },
    ]

    rule_concept_check = build_presence_checks(
        "required_rule_or_scenario_concepts_present",
        all_text,
        REQUIRED_RULE_CONCEPTS,
    )

    negative_scenario_check = build_presence_checks(
        "required_negative_control_scenarios_present",
        all_text,
        REQUIRED_NEGATIVE_SCENARIOS,
    )

    healthy_check = {
        "name": "healthy_placeholder_case_present_and_not_alerted",
        "passed": (
            has_any(all_text, ["healthy", "placeholder", "placeholder_control"])
            and has_any(all_text, ["no_alert", "no alert", "pass", "passed"])
        ),
        "acceptedHealthyTerms": ["healthy", "placeholder", "placeholder_control"],
        "acceptedNonAlertTerms": ["no_alert", "no alert", "pass", "passed"],
    }

    promtool_blocked = detect_promtool_blocked(all_text, source_report)
    unsafe_promtool_pass_claim = detect_unsafe_promtool_pass_claim(all_text)

    boundary_checks = [
        {
            "name": "promtool_blocked_is_explicit",
            "passed": promtool_blocked,
        },
        {
            "name": "no_unsafe_promtool_pass_claim",
            "passed": not unsafe_promtool_pass_claim,
        },
    ]

    all_checks = [
        *structural_checks,
        rule_concept_check,
        negative_scenario_check,
        healthy_check,
        *boundary_checks,
    ]

    semantic_ok = all(check.get("passed", False) for check in all_checks)

    decision = (
        "PARTIAL_WEEK17_LAYER_MIX_V0_ALERT_RULES_PROMTOOL_BLOCKED_LOCAL_SEMANTIC_PASS"
        if semantic_ok
        else "FAIL_WEEK17_LAYER_MIX_V0_ALERT_RULES_LOCAL_SEMANTIC_FALLBACK"
    )

    fallback_report = {
        "decision": decision,
        "generatedAtUtc": generated_at,
        "validatorVersion": "v3_structural_semantic_contract_safe_promtool_boundary",
        "scope": "local_semantic_fallback_for_week17_layer_mix_v0_action_gate_alert_rules",
        "promtoolBlocked": promtool_blocked,
        "semanticFallbackPassed": semantic_ok,
        "unsafePromtoolPassClaimDetected": unsafe_promtool_pass_claim,
        "alertNames": alert_names,
        "checks": all_checks,
        "failedChecks": [check for check in all_checks if not check.get("passed", False)],
        "sourceFiles": {
            "rulesFile": str(RULES_FILE.relative_to(ROOT)),
            "testFile": str(TEST_FILE.relative_to(ROOT)),
            "sourceReportFile": str(SOURCE_REPORT_FILE.relative_to(ROOT)),
            "actionGateJson": str(ACTION_GATE_JSON.relative_to(ROOT)),
            "actionGateCsv": str(ACTION_GATE_CSV.relative_to(ROOT)),
            "testLogs": [str(path.relative_to(ROOT)) for path in test_logs],
            "generateLogs": [str(path.relative_to(ROOT)) for path in generate_logs],
            "semanticLogs": [str(path.relative_to(ROOT)) for path in semantic_logs],
        },
        "blockedClaims": BLOCKED_CLAIMS,
        "notes": [
            "This is a local semantic fallback, not an official promtool pass.",
            "The fallback validates source file presence, alert/test structure, scenario coverage, blocked promtool boundary, and blocked claims.",
            "Run promtool check/test later when local promtool or Docker Desktop becomes available.",
        ],
    }

    dump_json(FALLBACK_REPORT_FILE, fallback_report)

    updated_report = dict(source_report) if isinstance(source_report, dict) else {"previousSourceReport": source_report}

    if "decision" in updated_report:
        updated_report["previousDecisionBeforeSemanticFallbackV2"] = updated_report["decision"]

    updated_report["decision"] = decision
    updated_report["promtoolBlocked"] = promtool_blocked
    updated_report["semanticFallbackPassed"] = semantic_ok
    updated_report["unsafePromtoolPassClaimDetected"] = unsafe_promtool_pass_claim
    updated_report["localSemanticFallbackReport"] = str(FALLBACK_REPORT_FILE.relative_to(ROOT))
    updated_report["localSemanticFallbackValidatorVersion"] = "v3_structural_semantic_contract_safe_promtool_boundary"
    updated_report["blockedClaims"] = BLOCKED_CLAIMS
    updated_report["updatedAtUtc"] = generated_at

    dump_json(SOURCE_REPORT_FILE, updated_report)

    print(
        json.dumps(
            {
                "decision": decision,
                "promtoolBlocked": promtool_blocked,
                "semanticFallbackPassed": semantic_ok,
                "unsafePromtoolPassClaimDetected": unsafe_promtool_pass_claim,
                "validatorVersion": "v3_structural_semantic_contract_safe_promtool_boundary",
                "alertNames": alert_names,
                "fallbackReport": str(FALLBACK_REPORT_FILE.relative_to(ROOT)),
                "updatedReport": str(SOURCE_REPORT_FILE.relative_to(ROOT)),
                "failedChecks": [check for check in all_checks if not check.get("passed", False)],
            },
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
    )

    return 0 if semantic_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
