#!/usr/bin/env python3
import argparse
import json
import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def git_head(repo_path):
    return subprocess.check_output(
        ["git", "-C", str(repo_path), "rev-parse", "--short", "HEAD"],
        text=True,
    ).strip()

def git_origin_main(repo_path):
    return subprocess.check_output(
        ["git", "-C", str(repo_path), "rev-parse", "--short", "origin/main"],
        text=True,
    ).strip()

def bool01(v):
    return 1 if v is True else 0

def metric_line(name, value, labels):
    label_text = ",".join(f'{k}="{str(v).replace(chr(34), chr(92)+chr(34))}"' for k, v in labels.items())
    return f"{name}{{{label_text}}} {value}"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--java-report", required=True)
    parser.add_argument("--out-index", default="loadtest/reports/week15_temporal_alignment_review_state_registry_backed_platform_index.json")
    parser.add_argument("--out-metrics", default="observability/prometheus/week15_temporal_alignment_review_state_registry_backed_metrics.prom")
    args = parser.parse_args()

    java_report_path = Path(args.java_report)
    if not java_report_path.exists():
        raise SystemExit(f"missing java report: {java_report_path}")

    java_repo_root = java_report_path.resolve().parents[2]
    cloud_repo_root = Path.cwd().resolve()
    java_report_sha256 = sha256_file(java_report_path)
    java_repo_head_at_consumption = git_head(java_repo_root)
    java_origin_main_at_consumption = git_origin_main(java_repo_root)
    cloud_input_head = git_head(cloud_repo_root)

    report = json.loads(java_report_path.read_text(encoding="utf-8"))

    decision = report.get("decision")
    source_type = report.get("sourceType")
    risk_ids = report.get("riskCandidateIds") or []

    required_ok = report.get("requiredRiskCandidatePresent") is True
    boundary_ok = report.get("claimBoundaryPreserved") is True
    loader_ok = report.get("registryBackedLoaderContractChecked") is True
    source_ok = source_type == "ARTIFACT_REGISTRY_BACKED"
    random_port_status = report.get("springBootRandomPortCompatibilityStatus", "UNKNOWN")

    pass_gate = (
        decision == "PASS_REGISTRY_BACKED_REVIEW_STATE_CONTRACT"
        and required_ok
        and boundary_ok
        and loader_ok
        and source_ok
    )

    platform_decision = (
        "PASS_JAVA_REGISTRY_BACKED_REVIEW_STATE_PLATFORM_CONSUMPTION"
        if pass_gate
        else "FAIL_JAVA_REGISTRY_BACKED_REVIEW_STATE_PLATFORM_CONSUMPTION"
    )

    index = {
        "schemaVersion": "week15.cloud.temporal-alignment-review-state.registry-backed-platform-index.v1",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "platformDecision": platform_decision,
        "claimBoundaryOk": boundary_ok,
        "sourceSnapshot": {
            "javaRepoRoot": str(java_repo_root),
            "javaRepoHeadAtConsumption": java_repo_head_at_consumption,
            "javaOriginMainAtConsumption": java_origin_main_at_consumption,
            "javaReportSha256": java_report_sha256,
            "cloudInputHead": cloud_input_head,
        },
        "javaContract": {
            "path": str(java_report_path),
            "decision": decision,
            "sourceType": source_type,
            "artifactRegistryBacked": report.get("artifactRegistryBacked"),
            "resourceSafeCheckMode": report.get("resourceSafeCheckMode"),
            "registryBackedLoaderContractChecked": loader_ok,
            "springBootRandomPortCompatibilityChecked": report.get("springBootRandomPortCompatibilityChecked"),
            "springBootRandomPortCompatibilityStatus": random_port_status,
        },
        "riskCandidateIds": risk_ids,
        "requiredRiskCandidatePresent": required_ok,
        "requiredRiskCandidateId": "procedural_v0_0004",
        "randomPortCompatibilityBoundary": {
            "status": random_port_status,
            "platformClaim": "Cloud consumed Java lightweight registry contract only; RANDOM_PORT E2E compatibility is not claimed.",
        },
        "artifactLinks": {
            "javaRegistryBackedContractReport": str(java_report_path),
            "cloudPlatformIndex": args.out_index,
            "cloudPrometheusReadyMetrics": args.out_metrics,
        },
    }

    out_index = Path(args.out_index)
    out_metrics = Path(args.out_metrics)
    out_index.parent.mkdir(parents=True, exist_ok=True)
    out_metrics.parent.mkdir(parents=True, exist_ok=True)

    out_index.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    labels = {
        "week": "week15",
        "source": "java_registry_backed_review_state",
        "random_port_status": random_port_status,
    }
    lines = [
        "# HELP week15_temporal_alignment_review_state_registry_backed_platform_pass Java registry-backed review-state platform consumption pass flag.",
        "# TYPE week15_temporal_alignment_review_state_registry_backed_platform_pass gauge",
        metric_line("week15_temporal_alignment_review_state_registry_backed_platform_pass", bool01(pass_gate), labels),
        "# HELP week15_temporal_alignment_review_state_claim_boundary_ok Claim boundary preservation flag.",
        "# TYPE week15_temporal_alignment_review_state_claim_boundary_ok gauge",
        metric_line("week15_temporal_alignment_review_state_claim_boundary_ok", bool01(boundary_ok), labels),
        "# HELP week15_temporal_alignment_review_state_required_risk_candidate_present Required risk candidate procedural_v0_0004 presence flag.",
        "# TYPE week15_temporal_alignment_review_state_required_risk_candidate_present gauge",
        metric_line("week15_temporal_alignment_review_state_required_risk_candidate_present", bool01(required_ok), labels),
        "# HELP week15_temporal_alignment_review_state_random_port_compatibility_checked RANDOM_PORT compatibility checked flag.",
        "# TYPE week15_temporal_alignment_review_state_random_port_compatibility_checked gauge",
        metric_line(
            "week15_temporal_alignment_review_state_random_port_compatibility_checked",
            bool01(report.get("springBootRandomPortCompatibilityChecked") is True),
            labels,
        ),
        "# HELP week15_temporal_alignment_review_state_risk_candidate_count Number of risk candidates carried from Java contract.",
        "# TYPE week15_temporal_alignment_review_state_risk_candidate_count gauge",
        metric_line("week15_temporal_alignment_review_state_risk_candidate_count", len(risk_ids), labels),
    ]
    out_metrics.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(index, ensure_ascii=False, indent=2))
    if not pass_gate:
        raise SystemExit(3)

if __name__ == "__main__":
    main()
