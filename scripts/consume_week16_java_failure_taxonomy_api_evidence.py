#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

def sh(cmd, cwd=None):
    return subprocess.check_output(cmd, text=True, cwd=cwd).strip()

def load_json(path):
    if not path.exists():
        raise SystemExit(f"MISSING_INPUT: {path}")
    return json.loads(path.read_text(encoding="utf-8"))

def prom_escape(value):
    return str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: consume_week16_java_failure_taxonomy_api_evidence.py <java_repo_dir>")

    java_dir = Path(sys.argv[1]).expanduser().resolve()
    api_report_path = java_dir / "artifacts/manifests/week16_java_failure_taxonomy_api_it_report.json"
    payload_path = java_dir / "artifacts/manifests/week16_java_temporal_alignment_failure_taxonomy_payload.json"
    consumer_report_path = java_dir / "artifacts/manifests/week16_java_temporal_alignment_failure_taxonomy_consumer_report.json"

    api_report = load_json(api_report_path)
    payload = load_json(payload_path)
    consumer_report = load_json(consumer_report_path)

    out_gate = Path("loadtest/reports/week16_temporal_alignment_failure_taxonomy_platform_gate.json")
    out_metrics = Path("observability/prometheus/week16_temporal_alignment_failure_taxonomy_metrics.prom")

    regression = payload.get("regressionFixtures", [])
    threshold = payload.get("thresholdFixtures", [])
    pass_controls = payload.get("passControlFixtures", [])
    bucket = payload.get("bucketCounts", {})

    errors = []
    if api_report.get("decision") != "PASS_WEEK16_JAVA_FAILURE_TAXONOMY_API_RANDOM_PORT_IT":
        errors.append(f"api_report_not_pass: {api_report.get('decision')}")
    if api_report.get("mavenExitCode") != 0:
        errors.append(f"api_it_maven_exit_code_not_0: {api_report.get('mavenExitCode')}")
    if not api_report.get("randomHttpPort"):
        errors.append("api_it_random_port_missing")
    if payload.get("candidateTotal") != 10:
        errors.append(f"payload_candidate_total_expected_10_got_{payload.get('candidateTotal')}")
    if [x.get("candidateId") for x in regression] != ["procedural_v0_0004", "procedural_v0_0010"]:
        errors.append(f"unexpected_regression_ids: {[x.get('candidateId') for x in regression]}")
    if [x.get("candidateId") for x in threshold] != ["procedural_v0_0007"]:
        errors.append(f"unexpected_threshold_ids: {[x.get('candidateId') for x in threshold]}")
    if len(pass_controls) != 7:
        errors.append(f"pass_control_count_expected_7_got_{len(pass_controls)}")
    if any(x.get("hasWaveformEvidence") is not True for x in regression):
        errors.append("all_regression_fixtures_must_have_waveform_evidence")
    if consumer_report.get("decision") != "PASS_WEEK16_JAVA_TEMPORAL_ALIGNMENT_FAILURE_TAXONOMY_CONSUMER":
        errors.append(f"consumer_report_not_pass: {consumer_report.get('decision')}")

    decision = (
        "PASS_WEEK16_CLOUD_FAILURE_TAXONOMY_PLATFORM_GATE"
        if not errors
        else "FAIL_WEEK16_CLOUD_FAILURE_TAXONOMY_PLATFORM_GATE"
    )

    gate = {
        "schemaVersion": "week16.cloud.temporal_alignment.failure_taxonomy.platform_gate.v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "decisionErrors": errors,
        "sourceMode": "java_week16_failure_taxonomy_api_it_artifact",
        "java": {
            "repo": str(java_dir),
            "head": sh(["git", "rev-parse", "--short", "HEAD"], cwd=java_dir),
            "originMain": sh(["git", "rev-parse", "--short", "origin/main"], cwd=java_dir),
            "apiReport": str(api_report_path),
            "payload": str(payload_path),
            "consumerReport": str(consumer_report_path),
            "apiEndpoint": api_report.get("apiEndpoint"),
            "apiDecision": api_report.get("decision"),
            "randomHttpPortEvidence": api_report.get("randomHttpPort"),
        },
        "cloudGit": {
            "head": sh(["git", "rev-parse", "--short", "HEAD"]),
            "originMain": sh(["git", "rev-parse", "--short", "origin/main"]),
            "aheadBehind": sh(["git", "rev-list", "--left-right", "--count", "HEAD...origin/main"]),
        },
        "summary": {
            "candidateTotal": payload.get("candidateTotal"),
            "bucketCounts": bucket,
            "p1RegressionFixtureIds": [x.get("candidateId") for x in regression],
            "thresholdFixtureIds": [x.get("candidateId") for x in threshold],
            "passControlCount": len(pass_controls),
            "blockedClaims": payload.get("blockedClaims", []),
        },
        "platformSignals": {
            "apiEvidencePass": api_report.get("decision") == "PASS_WEEK16_JAVA_FAILURE_TAXONOMY_API_RANDOM_PORT_IT",
            "p1RegressionFixtureCount": len(regression),
            "thresholdFixtureCount": len(threshold),
            "passControlCount": len(pass_controls),
            "blockedClaimCount": len(payload.get("blockedClaims", [])),
            "dashboardReady": len(errors) == 0,
            "metricsReady": len(errors) == 0,
        },
        "boundary": [
            "Cloud consumes Java W16 API IT evidence and normalized payload artifacts.",
            "Does not claim live Java service availability.",
            "Does not claim live Grafana import.",
            "Does not claim production SLO.",
            "Does not claim semantic audio quality pass.",
            "Does not claim human-review pass.",
            "Does not claim final mix readiness."
        ],
    }

    out_gate.write_text(json.dumps(gate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    labels = {
        "decision": decision,
        "source_mode": gate["sourceMode"],
        "java_head": gate["java"]["head"],
    }
    label_text = ",".join(f'{k}="{prom_escape(v)}"' for k, v in labels.items())

    metric_lines = [
        "# HELP week16_temporal_alignment_failure_taxonomy_platform_gate_pass Platform gate pass flag for W16 failure taxonomy.",
        "# TYPE week16_temporal_alignment_failure_taxonomy_platform_gate_pass gauge",
        f"week16_temporal_alignment_failure_taxonomy_platform_gate_pass{{{label_text}}} {1 if not errors else 0}",
        "# HELP week16_temporal_alignment_failure_taxonomy_candidate_total Candidate total consumed by Cloud.",
        "# TYPE week16_temporal_alignment_failure_taxonomy_candidate_total gauge",
        f"week16_temporal_alignment_failure_taxonomy_candidate_total {payload.get('candidateTotal')}",
        "# HELP week16_temporal_alignment_failure_taxonomy_p1_regression_fixture_total P1 regression fixture count.",
        "# TYPE week16_temporal_alignment_failure_taxonomy_p1_regression_fixture_total gauge",
        f"week16_temporal_alignment_failure_taxonomy_p1_regression_fixture_total {len(regression)}",
        "# HELP week16_temporal_alignment_failure_taxonomy_threshold_fixture_total Threshold fixture count.",
        "# TYPE week16_temporal_alignment_failure_taxonomy_threshold_fixture_total gauge",
        f"week16_temporal_alignment_failure_taxonomy_threshold_fixture_total {len(threshold)}",
        "# HELP week16_temporal_alignment_failure_taxonomy_pass_control_total Pass-control fixture count.",
        "# TYPE week16_temporal_alignment_failure_taxonomy_pass_control_total gauge",
        f"week16_temporal_alignment_failure_taxonomy_pass_control_total {len(pass_controls)}",
        "# HELP week16_temporal_alignment_failure_taxonomy_blocked_claim_total Blocked claim count.",
        "# TYPE week16_temporal_alignment_failure_taxonomy_blocked_claim_total gauge",
        f"week16_temporal_alignment_failure_taxonomy_blocked_claim_total {len(payload.get('blockedClaims', []))}",
    ]

    metric_lines.extend([
        "# HELP week16_temporal_alignment_failure_taxonomy_bucket_count Bucket count by taxonomy class.",
        "# TYPE week16_temporal_alignment_failure_taxonomy_bucket_count gauge",
    ])
    for name, value in bucket.items():
        metric_lines.append(
            f'week16_temporal_alignment_failure_taxonomy_bucket_count{{bucket="{prom_escape(name)}"}} {value}'
        )

    out_metrics.write_text("\n".join(metric_lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "decision": decision,
        "decisionErrors": errors,
        "gate": str(out_gate),
        "metrics": str(out_metrics),
        "summary": gate["summary"],
        "platformSignals": gate["platformSignals"],
    }, ensure_ascii=False, indent=2))

    if errors:
        raise SystemExit(2)

if __name__ == "__main__":
    main()
