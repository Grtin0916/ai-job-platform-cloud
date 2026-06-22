#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

OUT_JSON = Path("loadtest/reports/week16_temporal_alignment_failure_taxonomy_three_repo_closure_index.json")
OUT_PROM = Path("observability/prometheus/week16_temporal_alignment_failure_taxonomy_three_repo_closure_metrics.prom")
SCRIPT_PATH = Path("scripts/build_week16_three_repo_failure_taxonomy_closure.py")

SELF_OUTPUTS = {
    str(OUT_JSON),
    str(OUT_PROM),
    str(SCRIPT_PATH),
}
SELF_LOG_PREFIX = "artifacts/logs/week16_three_repo_failure_taxonomy_closure_"
SELF_LOG_SUFFIX = ".log"

def sh(cmd, cwd=None):
    return subprocess.check_output(cmd, text=True, cwd=cwd).strip()

def load_json(path):
    if not path.exists():
        raise SystemExit(f"MISSING_INPUT: {path}")
    return json.loads(path.read_text(encoding="utf-8"))

def is_expected_self_artifact(path, extra_self_outputs=None):
    extra_self_outputs = set(extra_self_outputs or [])
    if path in extra_self_outputs:
        return True
    if path.startswith(SELF_LOG_PREFIX) and path.endswith(SELF_LOG_SUFFIX):
        return True
    return False


def repo_state(repo, extra_self_outputs=None):
    repo = Path(repo).resolve()
    raw_lines = sh(["git", "status", "--porcelain=v1", "-uall"], cwd=repo).splitlines()
    relevant = []
    excluded = []
    for line in raw_lines:
        path = line[3:] if len(line) > 3 else line
        if is_expected_self_artifact(path, extra_self_outputs):
            excluded.append(line)
        else:
            relevant.append(line)
    return {
        "path": str(repo),
        "head": sh(["git", "rev-parse", "--short", "HEAD"], cwd=repo),
        "originMain": sh(["git", "rev-parse", "--short", "origin/main"], cwd=repo),
        "aheadBehind": sh(["git", "rev-list", "--left-right", "--count", "HEAD...origin/main"], cwd=repo),
        "porcelainCount": len(raw_lines),
        "relevantDirtyLines": relevant,
        "excludedSelfArtifactDirtyLines": excluded,
    }

def prom_escape(v):
    return str(v).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")

def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: build_week16_three_repo_failure_taxonomy_closure.py <mainbase_repo> <java_repo>")

    main_dir = Path(sys.argv[1]).expanduser().resolve()
    java_dir = Path(sys.argv[2]).expanduser().resolve()
    cloud_dir = Path.cwd().resolve()

    main_taxonomy = load_json(main_dir / "artifacts/evals/week16_temporal_alignment_failure_taxonomy_seed.json")
    java_api = load_json(java_dir / "artifacts/manifests/week16_java_failure_taxonomy_api_it_report.json")
    java_consumer = load_json(java_dir / "artifacts/manifests/week16_java_temporal_alignment_failure_taxonomy_consumer_report.json")
    java_payload = load_json(java_dir / "artifacts/manifests/week16_java_temporal_alignment_failure_taxonomy_payload.json")
    cloud_gate = load_json(Path("loadtest/reports/week16_temporal_alignment_failure_taxonomy_platform_gate.json"))

    main_state = repo_state(main_dir)
    java_state = repo_state(java_dir)
    cloud_state = repo_state(cloud_dir, SELF_OUTPUTS)

    blocked_claims = [
        "No live Java service availability claim.",
        "No live Grafana import claim.",
        "No production SLO claim.",
        "No semantic audio quality pass claim.",
        "No human-review pass claim.",
        "No final mix readiness claim.",
    ]

    errors = []

    if main_state["head"] != "1fc18a4":
        errors.append(f"mainbase_head_expected_1fc18a4_got_{main_state['head']}")
    if java_state["head"] != "8b0170f":
        errors.append(f"java_head_expected_8b0170f_got_{java_state['head']}")
    if cloud_state["head"] != "4c48c59":
        errors.append(f"cloud_head_expected_4c48c59_got_{cloud_state['head']}")

    for name, state in [("mainbase", main_state), ("java", java_state), ("cloud", cloud_state)]:
        if state["aheadBehind"] not in {"0\t0", "0 0"}:
            errors.append(f"{name}_ahead_behind_not_zero: {state['aheadBehind']}")
        if state["relevantDirtyLines"]:
            errors.append(f"{name}_relevant_dirty_lines: {state['relevantDirtyLines']}")

    if main_taxonomy.get("decision") != "PASS_WEEK16_TEMPORAL_ALIGNMENT_FAILURE_TAXONOMY_SEED_V3_SOURCE_CLEAN":
        errors.append(f"mainbase_taxonomy_not_pass: {main_taxonomy.get('decision')}")
    if java_consumer.get("decision") != "PASS_WEEK16_JAVA_TEMPORAL_ALIGNMENT_FAILURE_TAXONOMY_CONSUMER":
        errors.append(f"java_consumer_not_pass: {java_consumer.get('decision')}")
    if java_api.get("decision") != "PASS_WEEK16_JAVA_FAILURE_TAXONOMY_API_RANDOM_PORT_IT":
        errors.append(f"java_api_it_not_pass: {java_api.get('decision')}")
    if cloud_gate.get("decision") != "PASS_WEEK16_CLOUD_FAILURE_TAXONOMY_PLATFORM_GATE":
        errors.append(f"cloud_gate_not_pass: {cloud_gate.get('decision')}")

    summary = cloud_gate.get("summary", {})
    signals = cloud_gate.get("platformSignals", {})

    if summary.get("candidateTotal") != 10:
        errors.append(f"candidate_total_expected_10_got_{summary.get('candidateTotal')}")
    if summary.get("p1RegressionFixtureIds") != ["procedural_v0_0004", "procedural_v0_0010"]:
        errors.append(f"unexpected_p1_ids: {summary.get('p1RegressionFixtureIds')}")
    if summary.get("thresholdFixtureIds") != ["procedural_v0_0007"]:
        errors.append(f"unexpected_threshold_ids: {summary.get('thresholdFixtureIds')}")
    if summary.get("passControlCount") != 7:
        errors.append(f"pass_control_expected_7_got_{summary.get('passControlCount')}")
    if signals.get("dashboardReady") is not True or signals.get("metricsReady") is not True:
        errors.append(f"cloud_dashboard_or_metrics_not_ready: {signals}")

    decision = (
        "PASS_WEEK16_THREE_REPO_FAILURE_TAXONOMY_CLOSURE"
        if not errors
        else "FAIL_WEEK16_THREE_REPO_FAILURE_TAXONOMY_CLOSURE"
    )

    closure = {
        "schemaVersion": "week16.temporal_alignment.failure_taxonomy.three_repo_closure.v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "decision": decision,
        "decisionErrors": errors,
        "repositories": {
            "mainbase": main_state,
            "java": java_state,
            "cloud": cloud_state,
        },
        "sourceOfTruth": {
            "mainbaseTaxonomy": "artifacts/evals/week16_temporal_alignment_failure_taxonomy_seed.json",
            "javaConsumerReport": "artifacts/manifests/week16_java_temporal_alignment_failure_taxonomy_consumer_report.json",
            "javaApiItReport": "artifacts/manifests/week16_java_failure_taxonomy_api_it_report.json",
            "cloudPlatformGate": "loadtest/reports/week16_temporal_alignment_failure_taxonomy_platform_gate.json",
            "cloudMetrics": "observability/prometheus/week16_temporal_alignment_failure_taxonomy_metrics.prom",
        },
        "summary": {
            "candidateTotal": summary.get("candidateTotal"),
            "bucketCounts": summary.get("bucketCounts"),
            "p1RegressionFixtureIds": summary.get("p1RegressionFixtureIds"),
            "thresholdFixtureIds": summary.get("thresholdFixtureIds"),
            "passControlCount": summary.get("passControlCount"),
            "javaApiEndpoint": java_api.get("apiEndpoint"),
            "javaApiRandomPortEvidence": java_api.get("randomHttpPort"),
            "cloudPlatformSignals": signals,
            "blockedClaims": blocked_claims,
        },
        "handoff": {
            "w16NextInput": [
                "Use procedural_v0_0004 and procedural_v0_0010 as paired original-FAIL/remediated-PASS regression fixtures.",
                "Use procedural_v0_0007 as near-miss threshold-margin fixture.",
                "Use the seven pass controls as numeric-margin distribution baseline.",
                "Do not promote semantic quality, human review, final mix, live Java service, live Grafana, or production SLO claims."
            ]
        },
        "boundary": blocked_claims,
    }

    OUT_JSON.write_text(json.dumps(closure, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    labels = {
        "decision": decision,
        "mainbase_head": main_state["head"],
        "java_head": java_state["head"],
        "cloud_head": cloud_state["head"],
    }
    label_text = ",".join(f'{k}="{prom_escape(v)}"' for k, v in labels.items())

    metric_lines = [
        "# HELP week16_three_repo_failure_taxonomy_closure_pass W16 three-repo failure taxonomy closure pass flag.",
        "# TYPE week16_three_repo_failure_taxonomy_closure_pass gauge",
        f"week16_three_repo_failure_taxonomy_closure_pass{{{label_text}}} {1 if not errors else 0}",
        "# HELP week16_three_repo_failure_taxonomy_candidate_total W16 closure candidate total.",
        "# TYPE week16_three_repo_failure_taxonomy_candidate_total gauge",
        f"week16_three_repo_failure_taxonomy_candidate_total {summary.get('candidateTotal')}",
        "# HELP week16_three_repo_failure_taxonomy_p1_regression_fixture_total W16 closure P1 regression fixture total.",
        "# TYPE week16_three_repo_failure_taxonomy_p1_regression_fixture_total gauge",
        f"week16_three_repo_failure_taxonomy_p1_regression_fixture_total {len(summary.get('p1RegressionFixtureIds', []))}",
        "# HELP week16_three_repo_failure_taxonomy_threshold_fixture_total W16 closure threshold fixture total.",
        "# TYPE week16_three_repo_failure_taxonomy_threshold_fixture_total gauge",
        f"week16_three_repo_failure_taxonomy_threshold_fixture_total {len(summary.get('thresholdFixtureIds', []))}",
        "# HELP week16_three_repo_failure_taxonomy_pass_control_total W16 closure pass control total.",
        "# TYPE week16_three_repo_failure_taxonomy_pass_control_total gauge",
        f"week16_three_repo_failure_taxonomy_pass_control_total {summary.get('passControlCount')}",
        "# HELP week16_three_repo_failure_taxonomy_blocked_claim_total W16 closure blocked claim total.",
        "# TYPE week16_three_repo_failure_taxonomy_blocked_claim_total gauge",
        f"week16_three_repo_failure_taxonomy_blocked_claim_total {len(blocked_claims)}",
    ]

    OUT_PROM.write_text("\n".join(metric_lines) + "\n", encoding="utf-8")

    print(json.dumps({
        "decision": decision,
        "decisionErrors": errors,
        "closure": str(OUT_JSON),
        "metrics": str(OUT_PROM),
        "summary": closure["summary"],
    }, ensure_ascii=False, indent=2))

    if errors:
        raise SystemExit(2)

if __name__ == "__main__":
    main()
